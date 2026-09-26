"""BLOQUE 91 - AURA Local Autonomous Code Refactoring & Dynamic Hot-Patching Engine.

Motor 100% local de refactorización autónoma de código y hot-patching dinámico.
Complementa el Bloque 70 (autoevolución) con:
- Análisis estático con AST para detección de code smells
- Síntesis de refactorizaciones seguras (rename, extract method, simplify)
- Hot-patching dinámico en caliente (reload de módulos sin reiniciar)
- Auditoría de todos los cambios con hash y rollback

Almacenamiento: data/refactoring91/{patches, backups, logs, metrics/}
"""

from __future__ import annotations

import ast
import hashlib
import importlib
import json
import logging
import os
import re
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
import asyncio
from pydantic import BaseModel

from backend.refactoring.integration import (
    emit_fusion,
    fusion_snapshot,
    governor_gate,
    master_probe,
)
from backend.refactoring.models import (
    HotPatchRecord,
    ModuleState,
    PatchProposal,
    PatchStatus,
    RefactoringFinding,
    RefactoringMetrics,
    RefactoringType,
    _now_ts,
    _utcnow_iso,
)

from backend.refactoring.integration import (
    emit_fusion,
    fusion_snapshot,
    governor_gate,
    master_probe,
)

logger = logging.getLogger("AURA.Refactoring")

DATA_DIR = Path(
    os.getenv("AURA_REFACTORING91_DIR",
              os.path.join(os.getcwd(), "data", "refactoring91"))
)
for _sub in ("patches", "backups", "logs", "metrics", "modules"):
    (DATA_DIR / _sub).mkdir(parents=True, exist_ok=True)

# Directorios autorizados para refactorización.
AUTHORIZED_PREFIXES = ("backend/", "tests/")
FORBIDDEN_DIRS = (
    "backend/evolution/",
    "backend/refactoring/",
    "backend/security/",
    "backend/main.py",
    ".env",
)
MAX_PATCH_SIZE = 20000
MAX_FILE_SIZE = 500000


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    if not path.exists():
        return ""
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def _sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _is_authorized(path: str) -> bool:
    """Autoriza rutas dentro del proyecto local excluyendo directorios prohibidos."""
    try:
        resolved = Path(path).resolve()
    except Exception:
        return False
    root = Path(os.getcwd()).resolve()
    try:
        rel = resolved.relative_to(root)
    except ValueError:
        return False
    norm = str(rel).replace(os.sep, "/")
    for forbidden in FORBIDDEN_DIRS:
        f_norm = forbidden.replace(os.sep, "/")
        if norm == f_norm or norm.startswith(f_norm.rstrip("/") + "/"):
            return False
    for prefix in AUTHORIZED_PREFIXES:
        p_norm = prefix.replace(os.sep, "/")
        if norm.startswith(p_norm):
            return True
    return False


def _syntax_ok(code: str) -> Tuple[bool, str]:
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as exc:
        return False, str(exc)


def _uid(prefix: str = "refac") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ─── Code Auditor — detección de code smells con AST ──────────────────────────

class CodeAuditor:
    """Auditor estático de código usando AST para detección de code smells."""

    def __init__(self, long_function_threshold: int = 20) -> None:
        self.long_function_threshold = long_function_threshold

    def audit(self, file_path: str) -> List[RefactoringFinding]:
        """Audita un archivo Python y retorna hallazgos."""
        if not _is_authorized(file_path):
            return []
        path = Path(file_path)
        if not path.exists() or path.suffix != ".py":
            return []
        if path.stat().st_size > MAX_FILE_SIZE:
            return []
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError) as exc:
            return [RefactoringFinding(
                file_path=file_path, line=0, severity="error",
                category="syntax", message=f"Error de parsing: {exc}",
                confidence=1.0)
            ]
        findings: List[RefactoringFinding] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end_line = getattr(node, 'end_lineno', node.lineno)
                length = end_line - node.lineno + 1
                if length > self.long_function_threshold:
                    findings.append(RefactoringFinding(
                        file_path=file_path, line=node.lineno,
                        severity="warning", category="complexity",
                        message=f"Función '{node.name}' tiene {length} líneas",
                        confidence=0.9))
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                findings.append(RefactoringFinding(
                    file_path=file_path, line=node.lineno,
                    severity="warning", category="style",
                    message="Bare except detectado", confidence=0.8))
        return findings

    def audit_directory(self, root: str, max_files: int = 200) -> List[RefactoringFinding]:
        """Audita todos los archivos .py en un directorio."""
        findings: List[RefactoringFinding] = []
        root_path = Path(root)
        count = 0
        for py_file in root_path.rglob("*.py"):
            if count >= max_files:
                break
            findings.extend(self.audit(str(py_file)))
            count += 1
        return findings


# ─── HotReloadController — hot-patching dinámico ──────────────────────────────

class HotReloadController:
    """Controla el hot-patching en caliente de módulos Python."""

    def reload_module(self, module_name: str) -> bool:
        """Recarga un módulo en caliente."""
        try:
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)
            return True
        except Exception as exc:
            logger.error(f"Error al reload de módulo {module_name}: {exc}")
            return False

    def reload_directory(self, root: str) -> Dict[str, bool]:
        """Recarga todos los módulos `.py` de un directorio."""
        results: Dict[str, bool] = {}
        root_path = Path(root)
        for file_path in root_path.rglob("*.py"):
            if not _is_authorized(str(file_path)):
                continue
            module_name = file_path.stem
            results[module_name] = self.reload_module(module_name)
        return results


# ─── Sandbox Tester ───────────────────────────────────────────────────────────

class SandboxTester:
    """Valida parches en sandbox (sintaxis AST)."""

    def test_patch(self, patch: PatchProposal) -> Dict[str, Any]:
        """Valida que el parche produzca código sintácticamente correcto."""
        path = Path(patch.target_file)
        if not path.exists():
            return {"passed": False, "error": "target_file_not_found"}
        try:
            source = path.read_text(encoding="utf-8")
        except Exception as exc:
            return {"passed": False, "error": str(exc)}
        if patch.old_snippet and patch.old_snippet not in source:
            return {"passed": False, "error": "old_snippet_not_found"}
        new_source = source.replace(patch.old_snippet, patch.new_snippet, 1)
        ok, err = _syntax_ok(new_source)
        if not ok:
            return {"passed": False, "error": "syntax_error: " + str(err)}
        old_hash = _sha256_file(path)
        return {"passed": True, "syntax_valid": True, "old_hash": old_hash}


# ─── PatchSynthesizer — síntesis de propuestas de refactorización ─────────────

class PatchSynthesizer:
    """Sintetiza propuestas de parches a partir de código y hallazgos."""

    def propose_rename(self, target_file: str, old_name: str, new_name: str,
                       context: str = "") -> Optional[PatchProposal]:
        """Propone un rename de variable/función."""
        if not _is_authorized(target_file):
            return None
        path = Path(target_file)
        if not path.exists():
            return None
        source = path.read_text(encoding="utf-8")
        pattern = re.compile(r'\b' + re.escape(old_name) + r'\b')
        new_source = pattern.sub(new_name, source)
        if new_source == source:
            return None
        ok, err = _syntax_ok(new_source)
        if not ok:
            return None
        return PatchProposal(
            patch_id=_uid("patch"),
            target_file=target_file,
            old_snippet=old_name,
            new_snippet=new_name,
            refactoring_type=RefactoringType.RENAME,
            description=f"Rename '{old_name}' -> '{new_name}'",
            rationale=f"Renombrado de {old_name} a {new_name} en {target_file}.",
            confidence=0.95 if not context else 0.85,
            metadata={"old_name": old_name, "new_name": new_name, "context": context},
        )

    def propose_manual(self, target_file: str, old_snippet: str,
                       new_snippet: str, description: str,
                       rtype: RefactoringType = RefactoringType.FIX_SMELL,
                       metadata: Optional[Dict[str, Any]] = None) -> Optional[PatchProposal]:
        """Propone un parche manual con validación de sintaxis."""
        if not _is_authorized(target_file):
            return None
        path = Path(target_file)
        if not path.exists():
            return None
        source = path.read_text(encoding="utf-8")
        if old_snippet not in source:
            return None
        new_source = source.replace(old_snippet, new_snippet, 1)
        ok, err = _syntax_ok(new_source)
        if not ok:
            return None
        return PatchProposal(
            patch_id=_uid("patch"),
            target_file=target_file,
            old_snippet=old_snippet,
            new_snippet=new_snippet,
            refactoring_type=rtype,
            description=description,
            confidence=0.9,
            metadata=metadata or {},
        )

    def synthesize_from_findings(self, findings: List[RefactoringFinding]) -> List[PatchProposal]:
        """Genera propuestas a partir de hallazgos de code smells."""
        proposals: List[PatchProposal] = []
        for f in findings:
            if f.category == "style" and "except" in f.message.lower():
                path = Path(f.file_path)
                if not path.exists():
                    continue
                source = path.read_text(encoding="utf-8")
                lines = source.splitlines()
                if f.line - 1 < len(lines):
                    old_line = lines[f.line - 1]
                    new_line = old_line.replace("except:", "except Exception:")
                    if old_line != new_line:
                        proposals.append(PatchProposal(
                            patch_id=_uid("patch"),
                            target_file=f.file_path,
                            old_snippet=old_line.strip(),
                            new_snippet=new_line.strip(),
                            refactoring_type=RefactoringType.FIX_SMELL,
                            description="Reemplazar bare except con except Exception",
                            confidence=f.confidence,
                            metadata={"line": f.line, "category": "style"},
                        ))
        return proposals


# ─── RefactoringEngine — motor integrado ──────────────────────────────────────

class RefactoringEngine:
    """Motor integrado de refactorización autónoma y hot-patching."""

    def __init__(self) -> None:
        self.auditor = CodeAuditor()
        self.synthesizer = PatchSynthesizer()
        self.sandbox = SandboxTester()
        self.hot_reload = HotReloadController()
        self._proposals: Dict[str, PatchProposal] = {}
        self._lock = threading.Lock()
        self._metrics = RefactoringMetrics()
        self.auto_hotswap: bool = True

    def audit_file(self, file_path: str) -> List[RefactoringFinding]:
        findings = self.auditor.audit(file_path)
        with self._lock:
            self._metrics.findings_detected += len(findings)
            self._metrics.last_run = _utcnow_iso()
        return findings

    def audit_directory(self, root: str, max_files: int = 200) -> List[RefactoringFinding]:
        findings = self.auditor.audit_directory(root, max_files)
        with self._lock:
            self._metrics.findings_detected += len(findings)
            self._metrics.last_run = _utcnow_iso()
        return findings

    def propose_patch(self, target_file: str, old_snippet: str,
                      new_snippet: str, description: str,
                      rtype: RefactoringType = RefactoringType.FIX_SMELL,
                      metadata: Optional[Dict[str, Any]] = None) -> Optional[PatchProposal]:
        gate = governor_gate()
        if not gate.get("allowed", True):
            logger.warning("propose_patch bloqueado por gobernador: %s", gate)
            emit_fusion("refactoring.governor_block",
                        {"phase": "propose", "target": target_file,
                         "decision": gate.get("decision")}, severity="medium")
            return None
        patch = self.synthesizer.propose_manual(
            target_file, old_snippet, new_snippet, description, rtype, metadata)
        if patch is None:
            return None
        with self._lock:
            self._proposals[patch.patch_id] = patch
            self._metrics.total_proposals += 1
        self._persist_proposal(patch)
        emit_fusion("refactoring.proposed",
                    {"patch_id": patch.patch_id, "target": patch.target_file,
                     "type": patch.refactoring_type.value}, severity="info")
        return patch

    def propose_autonomous(self, target_file: str) -> List[PatchProposal]:
        findings = self.audit_file(target_file)
        proposals = self.synthesizer.synthesize_from_findings(findings)
        with self._lock:
            for p in proposals:
                self._proposals[p.patch_id] = p
                self._metrics.total_proposals += 1
        return proposals

    def test_patch(self, patch_id: str) -> Optional[Dict[str, Any]]:
        patch = self.get_patch(patch_id)
        if patch is None:
            return None
        result = self.sandbox.test_patch(patch)
        with self._lock:
            patch.sandbox_result = result
            if result["passed"]:
                patch.status = PatchStatus.SANDBOX_PASSED
            else:
                patch.status = PatchStatus.SANDBOX_FAILED
        self._persist_proposal(patch)
        return result


    def apply_patch(self, patch_id: str, run_sandbox: bool = True) -> Optional[PatchProposal]:
        patch = self.get_patch(patch_id)
        if patch is None:
            return None
        gate = governor_gate()
        if not gate.get("allowed", True):
            patch.status = PatchStatus.REJECTED
            patch.error = f"governor_block: {gate.get('decision')} {gate.get('reasons')}"
            self._persist_proposal(patch)
            emit_fusion("refactoring.governor_block",
                        {"phase": "apply", "patch_id": patch_id,
                         "decision": gate.get("decision")}, severity="high")
            return patch
        if run_sandbox:
            result = self.sandbox.test_patch(patch)
            if not result["passed"]:
                patch.status = PatchStatus.SANDBOX_FAILED
                patch.error = result.get("error")
                self._persist_proposal(patch)
                return patch
            patch.status = PatchStatus.SANDBOX_PASSED
        path = Path(patch.target_file)
        if not path.exists():
            patch.status = PatchStatus.REJECTED
            patch.error = "target_file_not_found"
            return patch
        backup_path = self._create_backup(path, patch.patch_id)
        try:
            source = path.read_text(encoding="utf-8")
            new_source = source.replace(patch.old_snippet, patch.new_snippet, 1)
            ok, err = _syntax_ok(new_source)
            if not ok:
                self._restore_backup(backup_path, path)
                patch.status = PatchStatus.SANDBOX_FAILED
                patch.error = err
                self._persist_proposal(patch)
                return patch
            path.write_text(new_source, encoding="utf-8")
            emit_fusion("refactoring.applied",
                        {"patch_id": patch.patch_id, "target": patch.target_file},
                        severity="info")
            patch.status = PatchStatus.APPLIED
            patch.applied_at = _utcnow_iso()
            with self._lock:
                self._metrics.patches_applied += 1
            if self.auto_hotswap:
                module = Path(patch.target_file).stem
                self.hot_reload.reload_module(module)
        except Exception as exc:
            self._restore_backup(backup_path, path)
            patch.status = PatchStatus.REJECTED
            patch.error = str(exc)
            emit_fusion("refactoring.rejected",
                        {"patch_id": patch.patch_id, "error": str(exc)},
                        severity="medium")
        self._persist_proposal(patch)
        return patch

    def rollback_patch(self, patch_id: str) -> Optional[PatchProposal]:
        patch = self.get_patch(patch_id)
        if patch is None:
            return None
        if patch.status != PatchStatus.APPLIED:
            return patch
        path = Path(patch.target_file)
        backup_path = DATA_DIR / "backups" / f"{path.name}.{patch.patch_id}.bak"
        if backup_path.exists():
            try:
                path.write_text(backup_path.read_text(encoding="utf-8"), encoding="utf-8")
                patch.status = PatchStatus.ROLLED_BACK
                patch.rolled_back_at = _utcnow_iso()
                emit_fusion("refactoring.rolled_back",
                            {"patch_id": patch.patch_id, "target": patch.target_file},
                            severity="info")
                with self._lock:
                    self._metrics.patches_rolled_back += 1
            except Exception as exc:
                patch.error = str(exc)
        else:
            patch.error = "backup_not_found"
        self._persist_proposal(patch)
        return patch

    def get_patch(self, patch_id: str) -> Optional[PatchProposal]:
        with self._lock:
            return self._proposals.get(patch_id)

    def list_patches(self, status: Optional[PatchStatus] = None) -> List[PatchProposal]:
        with self._lock:
            items = list(self._proposals.values())
        if status:
            items = [p for p in items if p.status == status]
        return items

    def _create_backup(self, path: Path, patch_id: str = "") -> Path:
        backup_dir = DATA_DIR / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        hint = patch_id or patch_id_hint()
        backup_path = backup_dir / f"{path.name}.{hint}.bak"
        backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        return backup_path

    def _restore_backup(self, backup_path: Path, target: Path) -> None:
        if backup_path.exists():
            target.write_text(backup_path.read_text(encoding="utf-8"), encoding="utf-8")

    def _persist_proposal(self, patch: PatchProposal) -> None:
        patch_dir = DATA_DIR / "patches"
        patch_dir.mkdir(parents=True, exist_ok=True)
        patch_path = patch_dir / f"{patch.patch_id}.json"
        patch_path.write_text(json.dumps(patch.to_dict(), indent=2, default=str), encoding="utf-8")

    def get_metrics(self) -> Dict[str, Any]:
        with self._lock:
            base = self._metrics.to_dict()
        try:
            base["governor"] = governor_gate()
        except Exception:
            base["governor"] = {"allowed": True}
        try:
            base["fusion"] = fusion_snapshot()
        except Exception:
            base["fusion"] = {"state": "unknown"}
        try:
            base["master"] = master_probe()
        except Exception:
            base["master"] = {"master_state": "unknown"}
        return base

    def reset(self) -> None:
        with self._lock:
            self._proposals.clear()
            self._metrics = RefactoringMetrics()


def patch_id_hint() -> str:
    """Genera un sufijo corto para backups."""
    return uuid.uuid4().hex[:12]


# ─── Singleton ────────────────────────────────────────────────────────────────

_engine: Optional[RefactoringEngine] = None
_L = threading.Lock()


def get_engine() -> RefactoringEngine:
    global _engine
    with _L:
        if _engine is None:
            _engine = RefactoringEngine()
        return _engine


def reset_engine() -> None:
    global _engine
    with _L:
        if _engine is not None:
            _engine.reset()
        _engine = None


def set_engine(engine: Optional[RefactoringEngine]) -> None:
    global _engine
    with _L:
        _engine = engine


def enable_autostart() -> None:
    return None


# Alias para compatibilidad con el import de __init__.py
HotPatchController = HotReloadController
DynamicRefactorizer = RefactoringEngine


# ─── REST Router ──────────────────────────────────────────────────────────────

router = APIRouter(prefix="/api/refactoring", tags=["refactoring"])


class AuditRequest(BaseModel):
    file_path: str = ""
    directory: str = ""
    max_files: int = 200


class PatchRequest(BaseModel):
    target_file: str
    old_snippet: str = ""
    new_snippet: str = ""
    description: str = ""
    patch_type: str = "fix_smell"


@router.get("/status")
async def status() -> Dict[str, Any]:
    e = get_engine()
    return {"status": "ok", "metrics": e.get_metrics(),
            "proposals": len(e.list_patches()), "offline_only": True}


@router.post("/audit")
async def audit(req: AuditRequest) -> Dict[str, Any]:
    e = get_engine()
    if req.directory:
        findings = e.audit_directory(req.directory, req.max_files)
    elif req.file_path:
        findings = e.audit_file(req.file_path)
    else:
        findings = []
    return {"count": len(findings), "findings": [f.to_dict() for f in findings],
            "offline_only": True}


@router.post("/propose")
async def propose(req: PatchRequest) -> Dict[str, Any]:
    try:
        rtype = RefactoringType(req.patch_type)
    except ValueError:
        raise HTTPException(400, f"patch_type invalido: {req.patch_type}")
    patch = get_engine().propose_patch(req.target_file, req.old_snippet,
                                       req.new_snippet, req.description, rtype)
    if patch is None:
        raise HTTPException(400, "parche no autorizado o invalido")
    return patch.to_dict()


@router.post("/propose/autonomous")
async def propose_autonomous(file_path: str = Query(...)) -> Dict[str, Any]:
    proposals = get_engine().propose_autonomous(file_path)
    return {"count": len(proposals), "proposals": [p.to_dict() for p in proposals],
            "offline_only": True}


@router.post("/{patch_id}/test")
async def test_patch(patch_id: str) -> Dict[str, Any]:
    result = get_engine().test_patch(patch_id)
    if result is None:
        raise HTTPException(404, "patch_not_found")
    return result


@router.post("/{patch_id}/apply")
async def apply_patch(patch_id: str, run_sandbox: bool = True) -> Dict[str, Any]:
    patch = get_engine().apply_patch(patch_id, run_sandbox=run_sandbox)
    if patch is None:
        raise HTTPException(404, "patch_not_found")
    return patch.to_dict()


@router.post("/{patch_id}/rollback")
async def rollback_patch(patch_id: str) -> Dict[str, Any]:
    patch = get_engine().rollback_patch(patch_id)
    if patch is None:
        raise HTTPException(404, "patch_not_found")
    return patch.to_dict()


@router.get("/patches")
async def list_patches(status: Optional[str] = None) -> Dict[str, Any]:
    status_enum = None
    if status:
        try:
            status_enum = PatchStatus(status)
        except ValueError:
            raise HTTPException(400, f"status invalido: {status}")
    patches = get_engine().list_patches(status_enum)
    return {"count": len(patches), "patches": [p.to_dict() for p in patches],
            "offline_only": True}


@router.post("/hot-reload")
async def hot_reload(module_name: str = Query(...)) -> Dict[str, Any]:
    ok = get_engine().hot_reload.reload_module(module_name)
    return {"reloaded": ok, "module_name": module_name, "offline_only": True}


@router.post("/reset")
async def reset() -> Dict[str, Any]:
    reset_engine()
    return {"reset": True, "offline_only": True}


@router.get("/contracts")
async def contracts() -> Dict[str, Any]:
    return {
        "block": 91,
        "prefix": router.prefix,
        "endpoints": [
            {"method": "GET", "path": "/api/refactoring/status"},
            {"method": "GET", "path": "/api/refactoring/contracts"},
            {"method": "GET", "path": "/api/refactoring/audit"},
            {"method": "POST", "path": "/api/refactoring/propose"},
            {"method": "POST", "path": "/api/refactoring/propose/autonomous"},
            {"method": "POST", "path": "/api/refactoring/{patch_id}/test"},
            {"method": "POST", "path": "/api/refactoring/{patch_id}/apply"},
            {"method": "POST", "path": "/api/refactoring/{patch_id}/rollback"},
            {"method": "GET", "path": "/api/refactoring/patches"},
            {"method": "GET", "path": "/api/refactoring/{patch_id}"},
            {"method": "POST", "path": "/api/refactoring/hot-reload"},
            {"method": "GET", "path": "/api/refactoring/governor-gate"},
            {"method": "GET", "path": "/api/refactoring/fusion-context"},
            {"method": "GET", "path": "/api/refactoring/master-probe"},
            {"method": "POST", "path": "/api/refactoring/reset"},
            {"method": "WS", "path": "/api/refactoring/ws"},
        ],
        "compatibility": {
            "71_governor": "backend.telemetry.governor.get_governor (fail-open)",
            "83_fusion": "backend.fusion.sensory.get_fusion_engine (fail-soft)",
            "100_master": "backend.core.aura_master_runtime.get_master_runtime (probe)",
        },
        "offline_only": True,
    }


@router.get("/governor-gate")
async def governor_gate_ep() -> Dict[str, Any]:
    return governor_gate()


@router.get("/fusion-context")
async def fusion_context_ep(window_s: float = 30.0) -> Dict[str, Any]:
    return fusion_snapshot(window_s=window_s)


@router.get("/master-probe")
async def master_probe_ep() -> Dict[str, Any]:
    e = get_engine()
    return {"refactoring": {"patches": len(e.list_patches()),
                            "metrics": e.get_metrics()},
            "master": master_probe(), "offline_only": True}


@router.get("/{patch_id}")
async def get_patch(patch_id: str) -> Dict[str, Any]:
    patch = get_engine().get_patch(patch_id)
    if patch is None:
        raise HTTPException(404, "patch_not_found")
    return patch.to_dict()


class _WSConn:
    def __init__(self) -> None:
        self.active: set = set()
_ws = _WSConn()


@router.websocket("/ws")
async def refactoring_ws(websocket: "WebSocket") -> None:
    """Canal WebSocket: heartbeat con métricas del motor de refactoring."""
    await websocket.accept()
    _ws.active.add(websocket)
    try:
        while True:
            e = get_engine()
            await websocket.send_json({"event": "heartbeat",
                                       "metrics": e.get_metrics(),
                                       "patches": len(e.list_patches()),
                                       "offline_only": True})
            await asyncio.sleep(2.0)
    except (WebSocketDisconnect, Exception):
        _ws.active.discard(websocket)

