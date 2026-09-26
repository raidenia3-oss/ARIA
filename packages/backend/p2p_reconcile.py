"""AURA P2P Offline Sync & Conflict Resolution Engine (Bloque 50).

Conciliacion peer-to-peer entre el host de la PC y el buffer offline de la
tarjeta SD del cliente movil AME, 100% local (red LAN / WebSocket / mDNS),
sin intermediarios en la nube (sin Firebase, iCloud ni servidores de sync).

Protocolo de sincronizacion diferencial (payload por documento):

    {
      "doc_id": "w1/character/hero",
      "type": "character",            # character | canon | chapter | note
      "work_id": "w1",
      "base_hash": "sha256:...",      # hash de la ultima version sincronizada
      "base_updated_at": 1700000000.0,
      "sd": {"hash": "...", "updated_at": ..., "version": 2, "payload": {...}, "metadata": {...}},
      "pc": {"hash": "...", "updated_at": ..., "version": 1, "payload": {...}, "metadata": {...}}
    }

Matriz de decision (three-way merge por hash):
1. sd.hash == pc.hash                        -> in_sync (sin accion)
2. sd.hash == base_hash  (SD sin cambios)    -> push_to_sd (gana PC)
3. pc.hash == base_hash  (PC sin cambios)    -> pull_from_sd (gana SD)
4. ambos divergen del base y entre si        -> conflict:
   - lww (default): gana el updated_at mas reciente; el perdedor se respalda.
   - merge: fusión de metadatos (claves no conflictivas se unen; conflictivas
     -> gana el mas nuevo); el perdedor se respalda.
   - pc_wins / sd_wins: resolucion explicita.
   Todo conflicto genera una copia de respaldo automatica en JSON dentro de
   ``<AURA_SYNC_DIR>/p2p_backups/`` antes de aplicar la resolucion.

Notificacion: el resultado se emite por el WebSocket Gateway local
(``sync_reconciled``) de forma best-effort, sin bloquear la respuesta REST.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException

logger = logging.getLogger("AURA.P2P.Reconcile")

router = APIRouter(prefix="/api/sync/reconcile", tags=["p2p_sync"])

SYNC_DIR_ENV = "AURA_SYNC_DIR"
STATE_FILENAME = "p2p_sync_state.json"
BACKUP_DIRNAME = "p2p_backups"
MAX_DOCS = 1000
_lock = threading.Lock()

# Estrategias de resolucion soportadas
STRATEGIES = ("lww", "merge", "pc_wins", "sd_wins")


def _sync_dir() -> Path:
    """Directorio de sync (lee el env en cada llamada para aislar tests)."""
    return Path(os.getenv(SYNC_DIR_ENV, os.path.join(os.getcwd(), "data")))


def _state_file() -> Path:
    return _sync_dir() / STATE_FILENAME


def _backups_dir() -> Path:
    return _sync_dir() / BACKUP_DIRNAME


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    tmp.replace(path)


def doc_hash(payload: Any) -> str:
    """Hash SHA-256 estable de un payload de documento (canonical JSON)."""
    try:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        raw = str(payload)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _as_epoch(value: Any) -> float:
    """Normaliza timestamps (epoch float o ISO-8601) a float comparable."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    try:
        return float(text)
    except ValueError:
        pass
    try:
        from datetime import datetime
        iso = text.replace("Z", "+00:00")
        return datetime.fromisoformat(iso).timestamp()
    except Exception:  # noqa: BLE001
        return 0.0


def _sanitize_doc_id(doc_id: str) -> str:
    """Sanitiza el doc_id para usarlo como nombre de directorio de backup."""
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", str(doc_id)).strip("._")
    return safe[:120] or "unknown_doc"


def _merge_metadata(pc_meta: Optional[Dict[str, Any]],
                    sd_meta: Optional[Dict[str, Any]],
                    pc_updated_at: float, sd_updated_at: float) -> Tuple[Dict[str, Any], List[str]]:
    """Fusiona metadatos de ambas versiones.
    - Claves presentes en un solo lado -> se conservan.
    - Claves con valores identicos -> se conservan.
    - Claves con valores distintos -> gana el lado con updated_at mas reciente;
      la clave se reporta en ``conflicts``.
    """
    pc_meta = dict(pc_meta or {})
    sd_meta = dict(sd_meta or {})
    merged: Dict[str, Any] = {}
    conflicts: List[str] = []
    for key in sorted(set(pc_meta) | set(sd_meta)):
        in_pc, in_sd = key in pc_meta, key in sd_meta
        if in_pc and in_sd:
            if pc_meta[key] == sd_meta[key]:
                merged[key] = pc_meta[key]
            else:
                merged[key] = pc_meta[key] if pc_updated_at >= sd_updated_at else sd_meta[key]
                conflicts.append(key)
        elif in_pc:
            merged[key] = pc_meta[key]
        else:
            merged[key] = sd_meta[key]
    return merged, conflicts


def _validate_doc(doc: Any) -> Tuple[bool, str]:
    """Valida la forma minima de un documento a conciliar."""
    if not isinstance(doc, dict):
        return False, "document must be an object"
    if not str(doc.get("doc_id", "")).strip():
        return False, "missing doc_id"
    sd = doc.get("sd")
    pc = doc.get("pc")
    if not isinstance(sd, dict) and not isinstance(pc, dict):
        return False, "document requires at least one side (sd or pc)"
    for side in (sd, pc):
        if isinstance(side, dict) and not str(side.get("hash", "")).strip():
            return False, "side without hash"
    return True, ""


def _decide(doc: Dict[str, Any], strategy: str) -> Tuple[str, str]:
    """Aplica la matriz three-way. Retorna (decision, winner)."""
    sd = doc.get("sd") or {}
    pc = doc.get("pc") or {}
    sd_hash = str(sd.get("hash", ""))
    pc_hash = str(pc.get("hash", ""))
    base_hash = str(doc.get("base_hash", ""))

    if sd_hash and pc_hash and sd_hash == pc_hash:
        return "in_sync", ""
    if not pc_hash:
        return "pull_from_sd", "sd"          # documento solo existe en la SD
    if not sd_hash:
        return "push_to_sd", "pc"            # documento solo existe en la PC
    if sd_hash == base_hash:
        return "push_to_sd", "pc"            # SD sin cambios desde el base
    if pc_hash == base_hash:
        return "pull_from_sd", "sd"          # PC sin cambios desde el base

    # Ambos lados divergen del base: edicion concurrente -> conflicto.
    if strategy == "pc_wins":
        return "conflict", "pc"
    if strategy == "sd_wins":
        return "conflict", "sd"
    if _as_epoch(pc.get("updated_at")) >= _as_epoch(sd.get("updated_at")):
        return "conflict", "pc"              # lww / merge: gana el mas nuevo
    return "conflict", "sd"


class P2PReconciler:
    """Pipeline de conciliacion P2P PC <-> SD con respaldo ante conflictos."""

    def __init__(self) -> None:
        self._state_lock = threading.Lock()

    # -- estado persistente ---------------------------------------------------

    def _load_state(self) -> Dict[str, Any]:
        return _load_json(_state_file(), {"last_reconcile": None, "reconcile_count": 0, "docs": {}})

    def _save_state(self, state: Dict[str, Any]) -> None:
        _save_json(_state_file(), state)

    # -- respaldos ------------------------------------------------------------

    def _write_backup(self, doc: Dict[str, Any], winner: str, strategy: str) -> Dict[str, Any]:
        """Copia de respaldo automatica de una edicion concurrente.
        Guarda base + pc + sd completos para que ninguna edicion se pierda.
        Nunca incluye tokens ni claves; solo contenido de documentos literarios.
        """
        doc_id = str(doc.get("doc_id", "unknown"))
        ts = time.time()
        backup_dir = _backups_dir() / _sanitize_doc_id(doc_id)
        record = {
            "doc_id": doc_id,
            "type": doc.get("type", ""),
            "work_id": doc.get("work_id", ""),
            "winner": winner,
            "strategy": strategy,
            "reason": "concurrent_edit",
            "base_hash": doc.get("base_hash", ""),
            "base": doc.get("base") or {},
            "pc": doc.get("pc") or {},
            "sd": doc.get("sd") or {},
            "backed_up_at": ts,
            "backed_up_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(ts)),
        }
        filename = f"{int(ts)}_{_sanitize_doc_id(doc_id)}.json"
        path = backup_dir / filename
        try:
            _save_json(path, record)
            record["backup_path"] = str(path)
        except OSError as exc:  # noqa: BLE001
            logger.warning("No se pudo escribir backup de %s: %s", doc_id, exc)
            record["backup_path"] = None
        return record

    def list_backups(self, doc_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lista los respaldos existentes (mas recientes primero)."""
        root = _backups_dir()
        if not root.exists():
            return []
        pattern = _sanitize_doc_id(doc_id) if doc_id else "*"
        out: List[Dict[str, Any]] = []
        for path in sorted(root.glob(f"{pattern}/*.json"), reverse=True):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                out.append({
                    "doc_id": data.get("doc_id"),
                    "winner": data.get("winner"),
                    "strategy": data.get("strategy"),
                    "backed_up_iso": data.get("backed_up_iso"),
                    "backup_path": str(path),
                })
            except (json.JSONDecodeError, OSError):
                continue
        return out

    # -- resolucion -------------------------------------------------------------

    def _resolve_doc(self, doc: Dict[str, Any], strategy: str) -> Dict[str, Any]:
        """Resuelve un documento y retorna su resultado individual."""
        decision, winner = _decide(doc, strategy)
        sd = doc.get("sd") or {}
        pc = doc.get("pc") or {}
        doc_id = str(doc.get("doc_id", ""))

        result: Dict[str, Any] = {
            "doc_id": doc_id,
            "type": doc.get("type", ""),
            "work_id": doc.get("work_id", ""),
            "decision": decision,
            "winner": winner,
            "strategy": strategy,
            "backup_path": None,
        }

        if decision == "in_sync":
            return result

        if decision == "conflict":
            backup = self._write_backup(doc, winner, strategy)
            result["backup_path"] = backup.get("backup_path")
            result["reason"] = "concurrent_edit"
            if strategy == "merge":
                merged_meta, meta_conflicts = _merge_metadata(
                    pc.get("metadata"), sd.get("metadata"),
                    _as_epoch(pc.get("updated_at")), _as_epoch(sd.get("updated_at")),
                )
                result["merged_metadata"] = merged_meta
                result["metadata_conflicts"] = meta_conflicts
                result["resolution"] = "merged"
                # El contenido textual divergente se resuelve por LWW; los
                # metadatos se fusionan. El perdedor queda en el backup.
                result["content_winner"] = winner
            else:
                result["resolution"] = "lww" if strategy == "lww" else strategy
                result["content_winner"] = winner
            return result

        result["reason"] = {
            "pull_from_sd": "pc_adopted_sd_version",
            "push_to_sd": "sd_adopted_pc_version",
        }[decision]
        return result

    # -- pipeline principal -------------------------------------------------------

    def reconcile(self, documents: List[Dict[str, Any]], device_id: str,
                  strategy: str = "lww") -> Dict[str, Any]:
        """Concilia un lote de documentos y retorna el informe completo."""
        if strategy not in STRATEGIES:
            raise ValueError(f"unsupported strategy: {strategy}")

        rejected: List[Dict[str, str]] = []
        valid: List[Dict[str, Any]] = []
        for doc in documents:
            ok, reason = _validate_doc(doc)
            if not ok:
                rejected.append({"doc_id": str((doc or {}).get("doc_id", "?")), "reason": reason})
            else:
                valid.append(doc)

        results: List[Dict[str, Any]] = []
        counters = {"in_sync": 0, "push_to_sd": 0, "pull_from_sd": 0, "conflict": 0}
        backups_created = 0
        adopted: Dict[str, Any] = {}

        with self._state_lock:
            state = self._load_state()
            registry: Dict[str, Any] = dict(state.get("docs", {}))

            for doc in valid:
                res = self._resolve_doc(doc, strategy)
                results.append(res)
                counters[res["decision"]] = counters.get(res["decision"], 0) + 1
                if res["decision"] == "conflict":
                    backups_created += 1

                # Registro de la version ganadora para la proxima conciliacion.
                winner_side = (doc.get("sd") or {}) if res.get("winner") == "sd" else (doc.get("pc") or {})
                if res.get("winner") == "sd":
                    adopted[res["doc_id"]] = doc.get("sd") or {}

                if winner_side:
                    registry[res["doc_id"]] = {
                        "hash": winner_side.get("hash", ""),
                        "updated_at": winner_side.get("updated_at"),
                        "version": winner_side.get("version", 0),
                        "source": res.get("winner", ""),
                    }

            state["docs"] = registry
            state["reconcile_count"] = int(state.get("reconcile_count", 0)) + 1
            state["last_reconcile"] = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())
            state["last_device"] = device_id
            state["last_summary"] = {
                "received": len(documents),
                "rejected": len(rejected),
                "conflicts": counters.get("conflict", 0),
                "backups": backups_created,
            }
            self._save_state(state)

        report = {
            "status": "ok",
            "device_id": device_id,
            "strategy": strategy,
            "received": len(documents),
            "reconciled": len(results),
            "rejected": rejected,
            "in_sync": counters["in_sync"],
            "pushed_to_sd": counters["push_to_sd"],
       
            "pulled_to_pc": counters["pull_from_sd"],
            "conflicts": counters["conflict"],
            "backups_created": backups_created,
            "adopted_from_sd": sorted(adopted.keys()),
            "documents": results,
        }
        _notify_ws(report)
        return report


def _notify_ws(report: Dict[str, Any]) -> None:
    """Emite el resultado por el WebSocket Gateway local (best-effort).
    Nunca lanza excepciones: si no hay event loop, gateway o conexiones activas,
    la notificacion se omite silenciosamente y la respuesta REST no se afecta.
    """
    try:
        from backend.websocket_manager import ws_gateway
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.debug("Sin event loop; notificacion WS omitida")
            return
        event_id = f"reconcile-{int(time.time() * 1000)}"
        ws_payload = {
            "eventId": event_id,
            "device_id": report.get("device_id"),
            "strategy": report.get("strategy"),
            "reconciled": report.get("reconciled", 0),
            "in_sync": report.get("in_sync", 0),
            "pulled_to_pc": report.get("pulled_to_pc", 0),
            "pushed_to_sd": report.get("pushed_to_sd", 0),
            "conflicts": report.get("conflicts", 0),
            "backups_created": report.get("backups_created", 0),
            "summary": (
                f"reconcile: {report.get('reconciled', 0)} docs, "
                f"{report.get('conflicts', 0)} conflictos, "
                f"{report.get('backups_created', 0)} respaldos"
            ),
        }
        loop.create_task(ws_gateway.broadcast("sync_reconciled", ws_payload))
    except Exception as exc:  # noqa: BLE001
        logger.debug("Notificacion WS no enviada: %s", exc)


# ---------------------------------------------------------------------------
# Endpoints REST del pipeline P2P
# ---------------------------------------------------------------------------

_reconciler: Optional[P2PReconciler] = None
_reconciler_lock = threading.Lock()


def get_p2p_reconciler() -> P2PReconciler:
    """Singleton del reconciliador."""
    global _reconciler
    if _reconciler is None:
        with _reconciler_lock:
            if _reconciler is None:
                _reconciler = P2PReconciler()
    return _reconciler


@router.post("")
async def reconcile_documents(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Concilia los buffers de la SD de AME contra los documentos de la PC.
    Esquema del payload:
    - device_id: ID del dispositivo movil
    - strategy:  lww (default) | merge | pc_wins | sd_wins
    - documents: lista de {doc_id, type, work_id, base_hash, base_updated_at,
                  sd: {hash, updated_at, version, payload, metadata},
                  pc: {hash, updated_at, version, payload, metadata}}
    Toda edicion concurrente genera un respaldo automatico (sin perdida de
    datos) y emite un evento ``sync_reconciled`` por el WebSocket local.
    """
    documents = payload.get("documents") or []
    device_id = str(payload.get("device_id", "unknown"))
    strategy = str(payload.get("strategy", "lww") or "lww")
    if not isinstance(documents, list):
        raise HTTPException(status_code=422, detail="documents must be a list")
    if len(documents) > MAX_DOCS:
        raise HTTPException(status_code=413, detail=f"too many documents (max {MAX_DOCS})")
    if strategy not in STRATEGIES:
        raise HTTPException(status_code=422, detail=f"unsupported strategy: {strategy}")

    try:
        return get_p2p_reconciler().reconcile(documents, device_id, strategy=strategy)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/status")
async def reconcile_status() -> Dict[str, Any]:
    """Estado de la ultima conciliacion P2P (para el panel de AME)."""
    state = _load_json(_state_file(), {})
    backups = get_p2p_reconciler().list_backups()
    return {
        "status": "ok",
        "last_reconcile": state.get("last_reconcile"),
        "reconcile_count": state.get("reconcile_count", 0),
        "last_device": state.get("last_device"),
        "last_summary": state.get("last_summary", {}),
        "tracked_docs": len(state.get("docs", {})),
        "backups_count": len(backups),
    }


@router.get("/backups")
async def reconcile_backups(doc_id: Optional[str] = None) -> Dict[str, Any]:
    """Lista los respaldos automaticos generados por conflictos P2P."""
    backups = get_p2p_reconciler().list_backups(doc_id=doc_id)
    return {"status": "ok", "count": len(backups), "backups": backups}
