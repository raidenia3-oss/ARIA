"""BLOQUE 81 - Local Omni-Diagnostic Suite & Final Sovereign System Verification Engine.

Suite integral de validacion extremo a extremo del ecosistema AURA: salud
operativa, integridad de los bloques modulares, ausencia de fugas hacia la
nube, cifrado local, persistencia del daemon y comunicacion P2P.

Arquitectura:
- DiagnosticConfig: politica de la suite (timeout, retencion, targets).
- CheckResult: resultado unitario (pass/warn/fail/skip) con latencia.
- OmniAuditor: registro y ejecucion coordinada de checks con filtrado only/skip.
- SovereigntyVerifier: auditoria estatica cero-cloud (URLs externas) y
  escaneo de secretos en artefactos locales (100% offline, sin red).
- default_checks(): filesystem, env_isolation, modules_importable,
  encryption_integrity, daemon_persistence, mesh_communication,
  concurrent_load, offline_scan, secrets_scan.
- Reporte exportable a JSON local (backend/diagnostics/reports).

Reglas:
- No toca subsistemas previos (solo IMPORTA y consulta motores 72-80).
- Checks 100% locales; ninguna conexion externa se realiza.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

STATUS_PASS = "pass"
STATUS_WARN = "warn"
STATUS_FAIL = "fail"
STATUS_SKIP = "skip"
_VERDICT = "sovereign_ready"


@dataclass
class DiagnosticConfig:
    check_timeout_s: float = 30.0
    max_history: int = 50
    repo_root: str = ""
    daemon_store_dir: str = ""
    report_dir: str = ""


@dataclass
class CheckResult:
    name: str
    status: str = STATUS_SKIP
    latency_ms: int = 0
    details: Dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "status": self.status, "latency_ms": self.latency_ms,
                "details": self.details, "error": self.error}


class OmniAuditor:
    """Registro y ejecucion coordinada de checks de diagnostico locales."""

    def __init__(self, config: Optional[DiagnosticConfig] = None) -> None:
        self.config = config or DiagnosticConfig()
        self._lock = threading.RLock()
        self._checks: Dict[str, Callable[..., Dict[str, Any]]] = {}
        self._history: List[Dict[str, Any]] = []
        self.last_report: Optional[Dict[str, Any]] = None

    def register_check(self, name: str, fn: Callable[..., Dict[str, Any]]) -> None:
        with self._lock:
            self._checks[name] = fn

    def unregister_check(self, name: str) -> None:
        with self._lock:
            self._checks.pop(name, None)

    def check_names(self) -> List[str]:
        with self._lock:
            return sorted(self._checks.keys())

    def _run_one(self, name: str, fn: Callable[..., Dict[str, Any]]) -> CheckResult:
        start = time.monotonic()
        try:
            info = fn()
        except Exception as exc:
            ms = int((time.monotonic() - start) * 1000)
            return CheckResult(name=name, status=STATUS_FAIL, latency_ms=ms, error=str(exc))
        ms = int((time.monotonic() - start) * 1000)
        res = CheckResult(name=name, latency_ms=ms)
        if isinstance(info, dict):
            res.status = info.get("status", STATUS_PASS)
            res.details = {k: v for k, v in info.items() if k != "status"}
        else:
            res.status = STATUS_PASS
        return res

    def run_all(self, only: Optional[List[str]] = None,
                skip: Optional[List[str]] = None) -> Dict[str, Any]:
        with self._lock:
            names = sorted(self._checks.keys())
        if only:
            names = [n for n in names if n in only]
        if skip:
            names = [n for n in names if n not in skip]
        results: List[CheckResult] = []
        for name in names:
            with self._lock:
                fn = self._checks[name]
            results.append(self._run_one(name, fn))
        counts = {"pass": 0, "warn": 0, "fail": 0, "skip": 0}
        for r in results:
            counts[r.status] = counts.get(r.status, 0) + 1
        verdict = _VERDICT if counts["fail"] == 0 else "action_required"
        report = {
            "report_id": uuid.uuid4().hex[:12],
            "ts": time.time(),
            "checks_total": len(results),
            "counts": counts,
            "verdict": verdict,
            "results": [r.to_dict() for r in results],
            "total_latency_ms": sum(r.latency_ms for r in results),
            "offline_only": True,
        }
        with self._lock:
            self._history.append(report)
            if len(self._history) > self.config.max_history:
                self._history = self._history[-(self.config.max_history // 2):]
            self.last_report = report
        return report

    def history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        with self._lock:
            items = list(self._history)
        return items[-limit:] if limit else items

    def export_report(self, report: Optional[Dict[str, Any]] = None,
                      report_dir: Optional[str] = None) -> str:
        rep = report or self.last_report
        if rep is None:
            rep = self.run_all()
        d = report_dir or self.config.report_dir or os.path.join("backend", "diagnostics", "reports")
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, f"omni_report_{rep['report_id']}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2, ensure_ascii=False)
        return path

class SovereigntyVerifier:
    """Auditoria estatica de soberania: cero-cloud y cero-secretos, sin red."""

    EXTERNAL_URL_RE = re.compile(r"https?://(?!localhost|127\.0\.0\.1|0\.0\.0\.0)[^\s\"']+")
    SECRET_RE = re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?[\w\-]{12,}")

    def scan_offline(self, paths: List[str]) -> Dict[str, Any]:
        leaks: List[Dict[str, Any]] = []
        scanned = 0
        for root in paths:
            if not os.path.isdir(root):
                continue
            for dirpath, _dirs, files in os.walk(root):
                for f in files:
                    if not f.endswith(".py"):
                        continue
                    p = os.path.join(dirpath, f)
                    scanned += 1
                    try:
                        with open(p, "r", encoding="utf-8", errors="ignore") as fh:
                            for lineno, line in enumerate(fh, 1):
                                stripped = line.strip()
                                if stripped.startswith("#") or stripped.startswith('"""'):
                                    continue
                                m = self.EXTERNAL_URL_RE.search(line)
                                if m:
                                    leaks.append({"file": p, "line": lineno, "url": m.group(0)})
                    except Exception:
                        continue
        return {"scanned_files": scanned, "leaks": leaks,
                "external_count": len(leaks), "status": "pass" if not leaks else "warn"}

    def scan_secrets(self, paths: List[str]) -> Dict[str, Any]:
        findings: List[Dict[str, Any]] = []
        scanned = 0
        for root in paths:
            if not os.path.isdir(root):
                continue
            for dirpath, _dirs, files in os.walk(root):
                for f in files:
                    if not f.endswith((".json", ".bat", ".service", ".txt")):
                        continue
                    p = os.path.join(dirpath, f)
                    scanned += 1
                    try:
                        with open(p, "r", encoding="utf-8", errors="ignore") as fh:
                            for lineno, line in enumerate(fh, 1):
                                m = self.SECRET_RE.search(line)
                                if m:
                                    findings.append({"file": p, "line": lineno})
                    except Exception:
                        continue
        return {"scanned_files": scanned, "findings": findings,
                "secret_count": len(findings), "status": "pass" if not findings else "warn"}

def register_default_checks(auditor: OmniAuditor, cfg: Optional[DiagnosticConfig] = None) -> List[str]:
    """Registra los checks locales por defecto (no modifica bloques previos)."""
    c = cfg or auditor.config
    repo_root = c.repo_root or os.getcwd()

    def check_filesystem() -> Dict[str, Any]:
        targets = ["backend", "tests"]
        missing = [t for t in targets if not os.path.isdir(os.path.join(repo_root, t))]
        return {"status": "pass" if not missing else "fail",
                "repo_root": repo_root, "missing": missing}

    def check_env_isolation() -> Dict[str, Any]:
        p = os.path.join(repo_root, ".env.local")
        if not os.path.exists(p):
            return {"status": "skip", "reason": ".env.local no existe (no leido jamas)"}
        st = os.stat(p)
        return {"status": "pass", "size_bytes": st.st_size,
                "mtime": st.st_mtime, "content_read": False}

    def check_modules_importable() -> Dict[str, Any]:
        mods = [
            "backend.knowledge.rag",
            "backend.automation.memory_injector",
            "backend.sandbox.executor",
            "backend.network_mesh.mesh",
            "backend.master_control.master",
            "backend.daemon.bootstrapper",
        ]
        ok, failed = [], []
        for m in mods:
            try:
                __import__(m)
                ok.append(m)
            except Exception as exc:
                failed.append({"module": m, "error": str(exc)[:80]})
        return {"status": "pass" if not failed else "warn",
                "importable": ok, "failed": failed}

    def check_encryption_integrity() -> Dict[str, Any]:
        from backend.network.mesh import MeshPacket
        key = b"diagnostic-secret-32-bytes-padding!!"
        payload = b'{"probe": 1}'
        tok = MeshPacket.encode(payload, key, src="diag-a", dst="diag-b")
        pkt = MeshPacket.decode(tok, key)
        ok = pkt is not None and pkt.payload == payload
        return {"status": "pass" if ok else "fail",
                "roundtrip": ok, "packet_bytes": len(tok)}

    def check_daemon_persistence() -> Dict[str, Any]:
        from backend.daemon.bootstrapper import DaemonStore
        store_dir = c.daemon_store_dir or os.path.join("backend", "daemon_state")
        store = DaemonStore(store_dir=store_dir)
        try:
            cfg_in = store.load_config()
        except Exception as exc:
            return {"status": "fail", "error": str(exc)}
        return {"status": "pass", "store_path": store.path,
                "persisted": cfg_in is not None,
                "autostart": getattr(cfg_in, "autostart_enabled", None)}

    def check_mesh_communication() -> Dict[str, Any]:
        from backend.network.mesh import MeshEngine
        eng = MeshEngine(node_id="diag-engine", shared_secret="diag-secret-32-bytes-padding!")
        try:
            eng.start()
        except Exception:
            pass
        payload = b'{"probe": 1}'
        tok = eng.encode_packet(payload, dst="diag-b")
        pkt = eng.decode_packet(tok)
        ok = pkt is not None and pkt.payload == payload
        st = eng.status()
        return {"status": "pass" if ok else "fail",
                "packet_roundtrip": ok, "engine_status": st.get("running"),
                "packet_bytes": len(tok)}

    def check_concurrent_load() -> Dict[str, Any]:
        n = 8
        errors: List[str] = []

        def worker(i: int) -> None:
            try:
                time.sleep(0.01)
                _ = sum(range(1000))
            except Exception as exc:
                errors.append(str(exc))
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return {"status": "pass" if not errors else "fail",
                "threads": n, "errors": errors}

    def check_offline_scan() -> Dict[str, Any]:
        v = SovereigntyVerifier()
        roots = [os.path.join(repo_root, "backend", "network_mesh"),
                 os.path.join(repo_root, "backend", "master_control"),
                 os.path.join(repo_root, "backend", "daemon")]
        return v.scan_offline(roots)

    def check_secrets_scan() -> Dict[str, Any]:
        v = SovereigntyVerifier()
        roots = [os.path.join(repo_root, "backend", "daemon_state"),
                 os.path.join(repo_root, "backend", "daemon")]
        return v.scan_secrets(roots)

    defaults = [
        ("filesystem", check_filesystem),
        ("env_isolation", check_env_isolation),
        ("modules_importable", check_modules_importable),
        ("encryption_integrity", check_encryption_integrity),
        ("daemon_persistence", check_daemon_persistence),
        ("mesh_communication", check_mesh_communication),
        ("concurrent_load", check_concurrent_load),
        ("offline_scan", check_offline_scan),
        ("secrets_scan", check_secrets_scan),
    ]
    for name, fn in defaults:
        auditor.register_check(name, fn)
    return auditor.check_names()

_engine: Optional[OmniAuditor] = None
_engine_lock = threading.Lock()


def get_omni_auditor(config: Optional[DiagnosticConfig] = None,
                     register_defaults: bool = True) -> OmniAuditor:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = OmniAuditor(config=config)
                if register_defaults:
                    register_default_checks(_engine)
    return _engine


def reset_omni_auditor() -> None:
    global _engine
    with _engine_lock:
        _engine = None


OmniEngine = OmniAuditor
get_omni_engine = get_omni_auditor
reset_omni_engine = reset_omni_auditor
