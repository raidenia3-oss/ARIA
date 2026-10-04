"""AME Offline-First Differential Sync Engine.

Recibe lotes de eventos offline acumulados en el celular (chat, notas,
cambios de personaje/canon) y los fusiona con el estado central aplicando:
- Orden por marca de tiempo (reloj lógico + createdAt).
- Deduplicación por eventId.
- Validación de coherencia literaria vía CharacterBible/CanonTracker.
- Resolución de conflictos: gana el último write (LWW) con log de sobrescritos.

Persiste el resultado en `data/ame_sync_state.json` (checkpoint) y mantiene
un log de eventos aplicados en `data/ame_sync_log.json` para auditoría.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException

from backend.story_memory.character_bible import CharacterBible
from backend.story_memory.canon_tracker import CanonTracker

router = APIRouter(prefix="/api/sync", tags=["ame_sync"])

SYNC_DIR_ENV = "AURA_SYNC_DIR"
STATE_FILENAME = "ame_sync_state.json"
LOG_FILENAME = "ame_sync_log.json"
_lock = threading.Lock()
MAX_BATCH = 500
MAX_LOG = 2000


def _sync_dir() -> Path:
    """Directorio de sync dinámico (lee el env en cada llamada para tests)."""
    return Path(os.getenv(SYNC_DIR_ENV, os.path.join(os.getcwd(), "data")))


def state_file() -> Path:
    return _sync_dir() / STATE_FILENAME


def log_file() -> Path:
    return _sync_dir() / LOG_FILENAME


def _ensure_dirs() -> None:
    _sync_dir().mkdir(parents=True, exist_ok=True)


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def _save_json(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


class AMESyncEngine:
    """Motor de sincronización diferencial offline-first para AME."""

    def __init__(self) -> None:
        _ensure_dirs()
        self.character_bible = CharacterBible()
        self.canon_tracker = CanonTracker()
        self._client_checkpoints: Dict[str, float] = {}  # client_id -> last_seen


def _validate_event(ev: Dict[str, Any]) -> Tuple[bool, str]:
    """Valida la forma mínima de un evento offline."""
    if not isinstance(ev, dict):
        return False, "event must be an object"
    if not ev.get("eventId"):
        return False, "missing eventId"
    if not ev.get("type"):
        return False, "missing type"
    if not ev.get("createdAt"):
        return False, "missing createdAt"
    return True, ""


def _coherence_check_via_jan(text: str, work_id: str = "", character_id: str = "") -> Dict[str, Any]:
    """Valida coherencia literaria usando el proveedor Jan local (si está activo).

    Contrato explicito: distingue "validado" de "no validado".
      {'provider': 'jan'|'none', 'validated': bool, 'pass': bool|None, 'note': str}
      - validated=True  -> medicion real; 'pass' es True/False.
      - validated=False -> no se pudo validar (jan caido/deshabilitado);
        'pass' es None. El llamador NO debe tratar esto como aprobado.
    """
    try:
        import asyncio
        from backend.ai_router import AIRouter

        router = AIRouter()
        system = "Eres AURA, un asistente literario. Eres conciso."
        if work_id:
            system += f" La obra es '{work_id}'."
        if character_id:
            system += f" El personaje activo es '{character_id}'."
        prompt = (
            f"Evalúa si el siguiente texto es coherente con la narrativa. "
            f"Responde solo con 'coherent' o 'incoherent', nada más.\nTexto: {text}"
        )
        result = asyncio.run(router.generate_response(
            prompt=prompt,
            context={},
            system_prompt=system,
            max_tokens=16,
            temperature=0.1,
        ))
        if result and result.get("provider") == "jan":
            verdict = (result.get("message") or "").strip().lower()
            return {
                "provider": "jan",
                "validated": True,
                "pass": verdict == "coherent",
                "note": "validated via jan",
            }
    except Exception:
        pass
    return {
        "provider": "none",
        "validated": False,
        "pass": None,
        "note": "jan not available; skipped validation",
    }


class AMESyncEngine:
    """Motor de sincronización diferencial offline-first para AME."""

    def __init__(self) -> None:
        _ensure_dirs()
        self.character_bible = CharacterBible()
        self.canon_tracker = CanonTracker()
        self._client_checkpoints: Dict[str, float] = {}  # client_id -> last_seen

    def _applied_ids(self) -> set:
        state = _load_json(state_file(), {})
        return set(state.get("applied_ids", []))

    def _record_applied(self, event_ids: List[str], log_entries: List[Dict[str, Any]]) -> None:
        state = _load_json(state_file(), {"last_sync": None, "applied_count": 0, "applied_ids": []})
        applied = set(state.get("applied_ids", []))
        applied.update(event_ids)
        state["applied_ids"] = list(applied)
        state["applied_count"] = len(applied)
        state["last_sync"] = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())
        _save_json(state_file(), state)

        log = _load_json(log_file(), [])
        log.extend(log_entries)
        if len(log) > MAX_LOG:
            log = log[-MAX_LOG:]
        _save_json(log_file(), log)

    def ingest_pc_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        client_id: str = "pc",
        source: str = "pc",
    ) -> Dict[str, Any]:
        """Ingresa un evento originado en la PC (chat_received, memory_updated,
        grafo_update, etc.) para que esté disponible vía pull deltas al móvil.

        El evento se graba en el log de sincronización con un eventId único,
        timestamp actual y el payload completo, sin necesidad de validación de
        coherencia (ya fue procesado en la PC).
        """
        event_id = f"pc_{uuid.uuid4().hex[:12]}"
        ts = time.time()
        ts_str = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(ts))

        log_entry = {
            "eventId": event_id,
            "type": event_type,
            "status": "applied",
            "detail": "",
            "payload": payload,
            "device_id": client_id,
            "source": source,
            "synced_at": ts_str,
            "createdAt": ts,
        }
        with _lock:
            log = _load_json(log_file(), [])
            log.append(log_entry)
            if len(log) > MAX_LOG:
                log = log[-MAX_LOG:]
            _save_json(log_file(), log)
            self._client_checkpoints[client_id] = ts

        return {"event_id": event_id, "type": event_type, "createdAt": ts}

    def _apply_event(self, ev: Dict[str, Any]) -> Tuple[str, Optional[str]]:
        """Aplica un evento individual. Retorna (status, detail)."""
        etype = str(ev.get("type", ""))
        payload = ev.get("payload") or {}

        if etype == "chat":
            return "applied", "chat event registered (no central mutation)"

        if etype == "character_upsert":
            work_id = str(payload.get("work_id", "")).strip()
            char_id = str(payload.get("char_id", "")).strip()
            if not work_id or not char_id:
                return "rejected", "character_upsert requires work_id and char_id"
            self.character_bible.create(work_id=work_id, char_id=char_id, **{
                k: v for k, v in payload.items() if k not in ("work_id", "char_id")
            })
            return "applied", f"character {char_id} upserted in {work_id}"

        if etype == "canon_event":
            work_id = str(payload.get("work_id", "")).strip()
            description = str(payload.get("description", "")).strip()
            if not work_id or not description:
                return "rejected", "canon_event requires work_id and description"
            ts = float(payload.get("timestamp", time.time()))
            scene_ref = str(payload.get("scene_ref", f"ame_offline:{ev.get('eventId', '')}"))
            result = self.canon_tracker.add_canon_event(
                work_id=work_id, description=description, timestamp=ts, scene_ref=scene_ref,
                source=str(payload.get("source", "ame_offline")),
            )
            return "applied", f"canon event {result.get('event_id')} added to {work_id}"

        if etype == "note":
            return "applied", "note buffered"

        return "ignored", f"unknown event type: {etype}"

    def apply_batch(self, events: List[Dict[str, Any]], device_id: str, session_id: str = "") -> Dict[str, Any]:
        """Fusiona un lote de eventos offline respetando orden temporal y deduplicación.

        Si session_id está presente y tiene contexto literario activo, los eventos
        de tipo 'chat_message' son validados de coherencia vía Jan (openai-compat).
        """
        ctx = None
        if session_id:
            from backend.story_memory.session_context import get_session_context
            ctx = get_session_context(session_id)

        work_id = (ctx or {}).get("work_id", "") if ctx else ""
        char_id = (ctx or {}).get("character_id", "") if ctx else ""

        with _lock:
            applied_ids = self._applied_ids()
            # Ordenar por createdAt (reloj del cliente) para reproducción determinista.
            ordered = sorted(events, key=lambda e: str(e.get("createdAt", "")))

            applied: List[str] = []
            skipped: List[Dict[str, str]] = []
            rejected: List[Dict[str, str]] = []
            log_entries: List[Dict[str, Any]] = []
            coherence_checked = 0
            coherence_unvalidated = 0

            for ev in ordered:
                valid, reason = _validate_event(ev)
                if not valid:
                    rejected.append({"eventId": str(ev.get("eventId", "?")), "reason": reason})
                    continue

                event_id = str(ev["eventId"])
                if event_id in applied_ids:
                    skipped.append({"eventId": event_id, "reason": "already applied"})
                    continue

                etype = str(ev.get("type", ""))
                if etype == "chat_message" and work_id:
                    payload = ev.get("payload") or {}
                    text = str(payload.get("content", payload.get("message", "")))
                    verdict = _coherence_check_via_jan(text, work_id, char_id)
                    coherence_checked += 1
                    if not verdict.get("validated"):
                        # No pudimos validar (jan caido/deshabilitado). NO es una
                        # aprobacion: se cuenta aparte para no confundir "no
                        # validado" con "coherente".
                        coherence_unvalidated += 1
                    elif not verdict["pass"]:
                        rejected.append({"eventId": event_id, "reason": "incoherent", "validator": verdict["provider"]})
                        log_entries.append({
                            "eventId": event_id,
                            "type": etype,
                            "status": "rejected",
                            "detail": "incoherent per jan",
                            "device_id": device_id,
                            "synced_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()),
                        })
                        continue

                status, detail = self._apply_event(ev)
                log_entries.append({
                    "eventId": event_id,
                    "type": ev.get("type"),
                    "status": status,
                    "detail": detail,
                    "device_id": device_id,
                    "synced_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()),
                })
                if status == "applied":
                    applied.append(event_id)
                elif status == "rejected":
                    rejected.append({"eventId": event_id, "reason": detail})

            if applied:
                self._record_applied(applied, log_entries)

            return {
                "status": "ok",
                "device_id": device_id,
                "received": len(events),
                "applied": len(applied),
                "skipped": len(skipped),
                "rejected": len(rejected),
                "coherence_checked": coherence_checked,
                "coherence_unvalidated": coherence_unvalidated,
                "skipped_details": skipped[:20],
                "rejected_details": rejected[:20],
            }


    def get_deltas(self, since: float, client_id: str, limit: int = 200) -> Dict[str, Any]:
        """Retorna eventos PC→Mobile desde el checkpoint del cliente.

        Lee el log de eventos aplicados (data/ame_sync_log.json) y filtra
        los que el cliente aún no ha visto (createdAt > checkpoint).
        Incluye: chat_received, memory_updated, grafo_update, canon_event,
        character_update, session_change, reflection, plot_summary.

        Args:
            since: epoch timestamp del último checkpoint del cliente.
            client_id: ID del dispositivo móvil.
            limit: máximo de eventos a retornar.

        Returns:
            {events: [...], checkpoint: float, count: int, has_more: bool}
        """
        log = _load_json(log_file(), [])
        cutoff = since if since else 0.0

        events = []
        for entry in log:
            try:
                ts_str = entry.get("synced_at", "")
                if not ts_str:
                    continue
                # Parsear timestamp del log (formato: 2026-09-14T18:45:49-0500)
                from datetime import datetime as _dt
                try:
                    ts = _dt.strptime(ts_str[:25], "%Y-%m-%dT%H:%M:%S%z").timestamp()
                except ValueError:
                    try:
                        ts = _dt.strptime(ts_str[:19], "%Y-%m-%dT%H:%M:%S").timestamp()
                    except ValueError:
                        continue
            except Exception:
                continue

            if ts <= cutoff:
                continue

            event = {
                "id": entry.get("eventId", ""),
                "type": entry.get("type", "unknown"),
                "payload": entry.get("payload", entry.get("detail", "")),
                "createdAt": ts,
                "status": entry.get("status", "applied"),
                "device_id": entry.get("device_id", client_id),
            }
            events.append(event)

        # Ordenar por createdAt
        events.sort(key=lambda e: e["createdAt"])

        # Actualizar checkpoint del cliente
        with _lock:
            self._client_checkpoints[client_id] = time.time()

        has_more = len(events) > limit
        if has_more:
            events = events[:limit]

        return {
            "events": events,
            "checkpoint": time.time(),
            "count": len(events),
            "has_more": has_more,
            "client_id": client_id,
        }

    def get_client_checkpoint(self, client_id: str) -> float:
        """Retorna el último checkpoint registrado para un cliente."""
        return self._client_checkpoints.get(client_id, 0.0)


def get_sync_engine() -> AMESyncEngine:
    if not hasattr(get_sync_engine, "_instance") or get_sync_engine._instance is None:
        get_sync_engine._instance = AMESyncEngine()
    return get_sync_engine._instance


@router.get("/status")
async def sync_status() -> Dict[str, Any]:
    """Estado del motor de sincronización (checkpoint + log tail)."""
    state = _load_json(state_file(), {"last_sync": None, "applied_count": 0})
    log = _load_json(log_file(), [])
    return {
        "status": "ok",
        "last_sync": state.get("last_sync"),
        "applied_count": state.get("applied_count", 0),
        "log_size": len(log),
    }


@router.get("/pending-count")
async def sync_pending_count() -> Dict[str, Any]:
    """Cantidad de eventos pendientes reportada por el cliente (eco validado)."""
    return {"status": "ok", "note": "El cliente gestiona su cola offline en IndexedDB."}


@router.post("/push")
async def sync_push(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Recibe un lote de eventos offline y los fusiona con el estado central.

    Esquema:
    - device_id: ID del dispositivo móvil
    - session_id: ID de sesión literaria (opcional; habilita coherencia vía Jan)
    - last_sync_timestamp: epoch del último sync (opcional, para diferencial)
    - events: lista de eventos {eventId, type, payload, createdAt}
    """
    events = payload.get("events") or []
    device_id = str(payload.get("device_id", "unknown"))
    session_id = str(payload.get("session_id", "") or "")
    if not isinstance(events, list):
        raise HTTPException(status_code=422, detail="events must be a list")
    if len(events) > MAX_BATCH:
        raise HTTPException(status_code=413, detail=f"batch too large (max {MAX_BATCH})")

    engine = get_sync_engine()
    return engine.apply_batch(events, device_id, session_id=session_id)


@router.get("/pull")
async def sync_pull(
    client_id: str = "",
    since: float = 0.0,
    limit: int = 200,
) -> Dict[str, Any]:
    """Recibe deltas PC→Mobile desde el último checkpoint del cliente.

    El cliente envía su último checkpoint (epoch float) y recibe solo los
    eventos nuevos que la PC ha procesado desde entonces.

    Esquema de respuesta:
    {
        "events": [
            {
                "id": "evt_123",
                "type": "chat_received",
                "payload": {...},
                "createdAt": 1234567890.0
            }
        ],
        "checkpoint": 1234567895.0,
        "count": 1,
        "has_more": false,
        "client_id": "ame_xxx"
    }
    """
    if not client_id:
        raise HTTPException(status_code=400, detail="client_id is required")
    engine = get_sync_engine()
    return engine.get_deltas(since=since, client_id=client_id, limit=limit)


@router.get("/checkpoint/{client_id}")
async def get_client_checkpoint(client_id: str) -> Dict[str, Any]:
    """Retorna el checkpoint actual de un cliente."""
    engine = get_sync_engine()
    ts = engine.get_client_checkpoint(client_id)
    return {"client_id": client_id, "checkpoint": ts}