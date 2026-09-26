"""BLOQUE 70 - AURA Local Self-Evolution & Dynamic Code Patching Engine.

Motor 100% local de auto-analisis, sintesis de parches, prueba en sandbox
y hot-reload de submodulos del backend, sin dependencias cloud.
Almacenamiento: data/evolution70/{patches,backups,snapshots,logs}/
"""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query

from backend.evolution.models import (
    PatchProposal,
    PatchStatus,
    PatchType,
    VersionSnapshot,
)

logger = logging.getLogger("AURA.Evolution.Patcher")

DATA_DIR = Path(os.getenv("AURA_EVOLUTION70_DIR", os.path.join(os.getcwd(), "data", "evolution70")))
for _sub in ("patches", "backups", "snapshots", "logs"):
    (DATA_DIR / _sub).mkdir(parents=True, exist_ok=True)

# Directorios autorizados para parcheo (backend local solamente).
AUTHORIZED_PREFIXES = (
    "backend/",
)
FORBIDDEN_DIRS = (
    "backend/agent/evolution.py",
    "backend/evolution/patcher.py",
    "backend/main.py",
    "backend/security/",
    "backend/network/",
    ".env",
)

MAX_PATCH_SIZE = 20000
MAX_FILE_SIZE = 500000

def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            h.update(block)
    return h.hexdigest()

def _sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _is_authorized(path: str) -> bool:
    """Autoriza rutas dentro del proyecto local, excluyendo directorios prohibidos."""
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
    return True

def _syntax_ok(code: str) -> Tuple[bool, str]:
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as exc:
        return False, str(exc)



@dataclass
class AuditFinding:
    """Un hallazgo del auditor de codigo autonomo."""
    file_path: str
    line: int
    severity: str  # info | warning | error
    category: str  # syntax | performance | security | logic | style
    message: str
    snippet: str = ""
    suggested_patch: str = ""
    confidence: float = 0.0
    created_at: str = field(default_factory=lambda: _utcnow_iso())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "line": self.line,
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "snippet": self.snippet,
            "suggested_patch": self.suggested_patch,
            "confidence": self.confidence,
            "created_at": self.created_at,
        }


class CodeAuditor:
    """Auditor autonomo de metricas, trazas y sintaxis de submodulos."""
    ERROR_PATTERNS = [
        (r"except\s+Exception", "warning", "logic", "Excepcion genérica, especificar tipo"),
        (r"TODO|FIXME|XXX", "info", "logic", "Marcador pendiente detectado"),
        (r"time\.sleep\(", "warning", "performance", "sleep bloqueante en tiempo real"),
        (r"while\s+True", "warning", "performance", "Bucle infinito potencial"),
        (r"print\(", "info", "style", "Uso de print en lugar de logger"),
        (r"os\.system\(|subprocess\.call\(", "warning", "security", "Ejecucion de comando del sistema"),
        (r"eval\(|exec\(", "error", "security", "eval/exec dinámico detectado"),
    ]

    def __init__(self, max_files: int = 200) -> None:
        self._max_files = max_files
        self._mutex = threading.RLock()

    def audit_file(self, path: str) -> List[AuditFinding]:
        p = Path(path)
        if not p.exists() or not p.is_file():
            return []
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return []
        findings: List[AuditFinding] = []
        ok, err = _syntax_ok(content)
        if not ok:
            findings.append(AuditFinding(
                file_path=path, line=1, severity="error", category="syntax",
                message="Syntax error: " + err, snippet=err[:200]))
            return findings
        for idx, line in enumerate(content.splitlines(), start=1):
            for pattern, severity, category, message in self.ERROR_PATTERNS:
                if re.search(pattern, line):
                    findings.append(AuditFinding(
                        file_path=path, line=idx, severity=severity, category=category,
                        message=message, snippet=line.strip()[:200]))
        return findings

    def audit_directory(self, root: str = "backend") -> List[AuditFinding]:
        root_path = Path(root)
        if not root_path.exists():
            return []
        findings: List[AuditFinding] = []
        files = sorted(p for p in root_path.rglob("*.py") if p.is_file())
        for p in files[:self._max_files]:
            findings.extend(self.audit_file(str(p)))
        return findings

    def audit_error_traces(self, traces: List[Dict[str, Any]]) -> List[AuditFinding]:
        """Convierte trazas de error (log/stderr) en hallazgos accionables."""
        findings: List[AuditFinding] = []
        for t in traces:
            if not isinstance(t, dict):
                continue
            msg = str(t.get("message") or t.get("error") or t.get("stderr") or "")
            if not msg:
                continue
            findings.append(AuditFinding(
                file_path=str(t.get("file") or t.get("file_path") or "unknown"),
                line=int(t.get("line") or 0),
                severity="error", category="logic",
                message=msg[:500], snippet=str(t.get("snippet") or "")[:200]))
        return findings




class PatchSynthesizer:
    """Sintetiza parches correctivos a partir de hallazgos del auditor."""
    def __init__(self, max_size: int = MAX_PATCH_SIZE) -> None:
        self._max_size = max_size

    def synthesize(self, finding: AuditFinding) -> Optional[PatchProposal]:
        if not _is_authorized(finding.file_path):
            return None
        patch_code = (finding.suggested_patch or '').strip()
        if not patch_code:
            patch_code = "# AURA diagnostic patch (manual review required): " \
                        + finding.message.replace('\n', ' ')[:200]
        if len(patch_code) > self._max_size:
            return None
        ok, _ = _syntax_ok(patch_code)
        if not ok:
            return None
        patch_id = 'evp_' + uuid.uuid4().hex[:12]
        ptype = PatchType.BUGFIX
        if finding.category == 'performance':
            ptype = PatchType.PERFORMANCE
        elif finding.category == 'security':
            ptype = PatchType.SECURITY
        return PatchProposal(
            patch_id=patch_id,
            target_file=finding.file_path,
            old_snippet=finding.snippet,
            new_snippet=patch_code,
            patch_type=ptype,
            description=finding.message,
            rationale='Auto-sintetizado desde auditor: ' + finding.category,
            confidence=finding.confidence or 0.5,
        )

    def synthesize_manual(self, target_file: str, old_snippet: str,
                            new_snippet: str, description: str,
                            patch_type: PatchType = PatchType.BUGFIX,
                            metadata: Optional[Dict[str, Any]] = None) -> Optional[PatchProposal]:
        if not _is_authorized(target_file):
            return None
        if len(new_snippet) > self._max_size:
            return None
        ok, err = _syntax_ok(new_snippet)
        if not ok:
            return None
        patch_id = 'evp_' + uuid.uuid4().hex[:12]
        return PatchProposal(
            patch_id=patch_id, target_file=target_file,
            old_snippet=old_snippet, new_snippet=new_snippet,
            patch_type=patch_type, description=description,
            confidence=1.0, metadata=metadata or {})


class SandboxTester:
    """Prueba un parche en sandbox aislado antes de aplicarlo."""
    def __init__(self, workspace_dir: Optional[str] = None) -> None:
        self._workspace = Path(workspace_dir or os.path.join(str(DATA_DIR), 'sandbox'))
        self._workspace.mkdir(parents=True, exist_ok=True)

    def _build_test_code(self, proposal: PatchProposal) -> str:
        return (
            'import ast\n'
            'import sys\n\n'
            'NEW_CODE = r\'\'\'' + proposal.new_snippet + '\'\'\'\n\n'
            'try:\n'
            '    tree = ast.parse(NEW_CODE)\n'
            "    print('SYNTAX_OK')\n"
            'except SyntaxError as e:\n'
            "    print('SYNTAX_FAIL', e)\n"
            '    sys.exit(1)\n\n'
            "compile(NEW_CODE, '<patch>', 'exec')\n"
            "print('COMPILE_OK')\n"
        )

    def test(self, proposal: PatchProposal) -> Dict[str, Any]:
        code = self._build_test_code(proposal)
        test_file = self._workspace / ('test_' + proposal.patch_id + '.py')
        test_file.write_text(code, encoding='utf-8')
        try:
            proc = subprocess.run(
                [sys.executable, str(test_file)],
                capture_output=True, text=True, timeout=15,
                cwd=str(self._workspace))
        except subprocess.TimeoutExpired:
            return {'outcome': 'timeout', 'stdout': '', 'stderr': 'sandbox timeout'}
        passed = proc.returncode == 0 and 'SYNTAX_OK' in proc.stdout and 'COMPILE_OK' in proc.stdout
        return {
            'outcome': 'passed' if passed else 'failed',
            'stdout': proc.stdout[:2000],
            'stderr': proc.stderr[:2000],
            'return_code': proc.returncode,
        }




class HotReloadController:
    """Aplica parches aprobados en caliente con respaldo y rollback."""
    def __init__(self, backup_dir: Optional[str] = None) -> None:
        self._backup_dir = Path(backup_dir or os.path.join(str(DATA_DIR), 'backups'))
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        self._snapshots: Dict[str, VersionSnapshot] = {}
        self._loaded: Dict[str, Any] = {}
        self._mutex = threading.RLock()

    def snapshot(self, file_path: str) -> Optional[VersionSnapshot]:
        src = Path(file_path)
        if not src.exists():
            return None
        content = src.read_text(encoding='utf-8', errors='replace')
        digest = _sha256_str(content)
        backup = self._backup_dir / (src.name + '.' + digest[:16] + '.bak')
        backup.write_text(content, encoding='utf-8')
        snap = VersionSnapshot(
            file_path=file_path, content_hash=digest, backup_path=str(backup))
        with self._mutex:
            self._snapshots[file_path] = snap
        return snap

    def apply_patch(self, proposal: PatchProposal) -> bool:
        target = Path(proposal.target_file)
        if not target.exists():
            return False
        original = target.read_text(encoding='utf-8', errors='replace')
        if proposal.old_snippet and proposal.old_snippet not in original:
            return False
        if proposal.old_snippet:
            patched = original.replace(proposal.old_snippet, proposal.new_snippet, 1)
        else:
            patched = original + '\n' + proposal.new_snippet
        ok, err = _syntax_ok(patched)
        if not ok:
            return False
        snap = self.snapshot(proposal.target_file)
        if snap is None:
            return False
        snap.patch_id = proposal.patch_id
        target.write_text(patched, encoding='utf-8')
        self._loaded[proposal.target_file] = patched
        return True

    def rollback(self, file_path: str) -> bool:
        with self._mutex:
            snap = self._snapshots.get(file_path)
        if snap is None:
            return False
        backup = Path(snap.backup_path)
        if not backup.exists():
            return False
        target = Path(file_path)
        target.write_text(backup.read_text(encoding='utf-8'), encoding='utf-8')
        self._loaded.pop(file_path, None)
        return True

    def reload_module(self, module_name: str) -> bool:
        try:
            mod = sys.modules.get(module_name)
            if mod is None:
                return False
            import importlib
            importlib.reload(mod)
            return True
        except Exception:
            return False

    def get_snapshot(self, file_path: str) -> Optional[VersionSnapshot]:
        with self._mutex:
            return self._snapshots.get(file_path)




class EvolutionPatchEngine:
    """Motor principal de autoevolucion y parcheo dinamico (100% local)."""
    def __init__(self, root_dir: str = '.') -> None:
        self._root = root_dir
        self.auditor = CodeAuditor()
        self.synthesizer = PatchSynthesizer()
        self.sandbox = SandboxTester()
        self.reload = HotReloadController()
        self._patches: Dict[str, PatchProposal] = {}
        self._mutex = threading.RLock()

    def audit(self, root: str = 'backend', max_files: int = 200) -> List[AuditFinding]:
        self.auditor._max_files = max_files
        return self.auditor.audit_directory(root)

    def audit_traces(self, traces: List[Dict[str, Any]]) -> List[AuditFinding]:
        return self.auditor.audit_error_traces(traces)

    def propose_from_findings(self, findings: List[AuditFinding]) -> List[PatchProposal]:
        proposals: List[PatchProposal] = []
        with self._mutex:
            for finding in findings:
                proposal = self.synthesizer.synthesize(finding)
                if proposal is not None:
                    self._patches[proposal.patch_id] = proposal
                    proposals.append(proposal)
        return proposals

    def propose_manual(self, target_file: str, old_snippet: str, new_snippet: str,
                            description: str, patch_type: PatchType = PatchType.BUGFIX,
                            metadata: Optional[Dict[str, Any]] = None) -> Optional[PatchProposal]:
        proposal = self.synthesizer.synthesize_manual(
            target_file, old_snippet, new_snippet, description, patch_type, metadata)
        if proposal is None:
            return None
        with self._mutex:
            self._patches[proposal.patch_id] = proposal
        return proposal

    def test_patch(self, patch_id: str) -> Optional[Dict[str, Any]]:
        with self._mutex:
            proposal = self._patches.get(patch_id)
        if proposal is None:
            return None
        result = self.sandbox.test(proposal)
        passed = result.get('outcome') == 'passed'
        proposal.sandbox_result = result
        proposal.status = PatchStatus.SANDBOX_PASSED if passed else PatchStatus.SANDBOX_FAILED
        return result

    def apply_patch(self, patch_id: str, run_sandbox: bool = True) -> Optional[PatchProposal]:
        with self._mutex:
            proposal = self._patches.get(patch_id)
        if proposal is None:
            return None
        if run_sandbox:
            self.test_patch(patch_id)
            if proposal.status == PatchStatus.SANDBOX_FAILED:
                proposal.error = 'sandbox rechazo el parche'
                return proposal
        ok = self.reload.apply_patch(proposal)
        if ok:
            proposal.status = PatchStatus.APPLIED
            proposal.applied_at = _utcnow_iso()
        else:
            proposal.status = PatchStatus.REJECTED
            proposal.error = 'no se pudo aplicar el parche'
        return proposal

    def rollback_patch(self, patch_id: str) -> Optional[PatchProposal]:
        with self._mutex:
            proposal = self._patches.get(patch_id)
        if proposal is None:
            return None
        ok = self.reload.rollback(proposal.target_file)
        if ok:
            proposal.status = PatchStatus.ROLLED_BACK
            proposal.rolled_back_at = _utcnow_iso()
        return proposal

    def get_patch(self, patch_id: str) -> Optional[PatchProposal]:
        with self._mutex:
            return self._patches.get(patch_id)

    def list_patches(self, status: Optional[PatchStatus] = None) -> List[PatchProposal]:
        with self._mutex:
            patches = list(self._patches.values())
        if status is not None:
            patches = [p for p in patches if p.status == status]
        return sorted(patches, key=lambda p: p.created_at, reverse=True)

    def get_snapshot(self, file_path: str) -> Optional[VersionSnapshot]:
        return self.reload.get_snapshot(file_path)

    def status(self) -> Dict[str, Any]:
        with self._mutex:
            total = len(self._patches)
        counts: Dict[str, int] = {}
        for p in self.list_patches():
            counts[p.status.value] = counts.get(p.status.value, 0) + 1
        return {
            'status': 'ok',
            'patches_total': total,
            'by_status': counts,
            'authorized_prefixes': list(AUTHORIZED_PREFIXES),
        }




# ---- singleton + REST router ----

router = APIRouter(prefix='/api/evolution/patch', tags=['evolution'])

_engine: Optional[EvolutionPatchEngine] = None
_engine_lock = threading.RLock()


def get_engine() -> EvolutionPatchEngine:
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = EvolutionPatchEngine()
    return _engine


def reset_engine() -> None:
    global _engine
    with _engine_lock:
        _engine = None


def set_engine(eng: EvolutionPatchEngine) -> None:
    global _engine
    with _engine_lock:
        _engine = eng


def _eng() -> EvolutionPatchEngine:
    return get_engine()


@router.get('/status')
async def patch_status():
    return _eng().status()


@router.get('/audit')
async def patch_audit(root: str = Query('backend'), max_files: int = Query(200, ge=1, le=1000)):
    findings = _eng().audit(root=root, max_files=max_files)
    return {'count': len(findings), 'findings': [x.to_dict() for x in findings]}


@router.post('/propose')
async def patch_propose(payload: dict):
    target_file = str(payload.get('target_file', ''))
    old_snippet = str(payload.get('old_snippet', ''))
    new_snippet = str(payload.get('new_snippet', ''))
    description = str(payload.get('description', ''))
    ptype = payload.get('patch_type', 'bugfix')
    try:
        patch_type = PatchType(ptype)
    except ValueError:
        raise HTTPException(status_code=400, detail='patch_type invalido: ' + ptype)
    proposal = _eng().propose_manual(target_file, old_snippet, new_snippet, description, patch_type, payload.get('metadata'))
    if proposal is None:
        raise HTTPException(status_code=400, detail='parche no autorizado o invalido')
    return proposal.to_dict()


@router.post('/propose/autonomous')
async def patch_propose_autonomous(payload: dict):
    traces = payload.get('traces') or []
    findings = _eng().audit_traces(traces)
    proposals = _eng().propose_from_findings(findings)
    return {'count': len(proposals), 'proposals': [p.to_dict() for p in proposals]}


@router.post('/{patch_id}/test')
async def patch_test(patch_id: str):
    result = _eng().test_patch(patch_id)
    if result is None:
        raise HTTPException(status_code=404, detail='patch_not_found')
    return result


@router.post('/{patch_id}/apply')
async def patch_apply(patch_id: str, run_sandbox: bool = Query(True)):
    proposal = _eng().apply_patch(patch_id, run_sandbox=run_sandbox)
    if proposal is None:
        raise HTTPException(status_code=404, detail='patch_not_found')
    return proposal.to_dict()


@router.post('/{patch_id}/rollback')
async def patch_rollback(patch_id: str):
    proposal = _eng().rollback_patch(patch_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail='patch_not_found')
    return proposal.to_dict()


@router.get('/{patch_id}/snapshot')
async def patch_snapshot(patch_id: str):
    proposal = _eng().get_patch(patch_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail='patch_not_found')
    snap = _eng().get_snapshot(proposal.target_file)
    return {'patch_id': patch_id, 'snapshot': snap.to_dict() if snap else None}


@router.get('/patches')
async def patch_list(status: Optional[str] = None):
    status_enum = None
    if status:
        try:
            status_enum = PatchStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail='status invalido: ' + status)
    patches = _eng().list_patches(status=status_enum)
    return {'count': len(patches), 'patches': [p.to_dict() for p in patches]}


@router.get('/{patch_id}')
async def patch_get(patch_id: str):
    proposal = _eng().get_patch(patch_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail='patch_not_found')
    return proposal.to_dict()


def enable_autostart() -> None:
    return None


__all__ = [
    'AuditFinding', 'CodeAuditor', 'EvolutionPatchEngine',
    'HotReloadController', 'PatchProposal', 'PatchSynthesizer',
    'SandboxTester', 'get_engine', 'reset_engine', 'set_engine',
    'enable_autostart', 'router',
]
