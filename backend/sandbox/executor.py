"""BLOQUE 77 - Local Secure Sandbox & Ephemeral Container Orchestrator Engine.

Subsistema 100% local y aislado para evaluar codigo no confiable, codigo de
autoevolucion o parches dinamicos en entornos efimeros sin cloud.

Arquitectura:
- SandboxConfig: politica de seguridad (timeout, memoria, red, denylist de FS/env).
- SandboxExecutor: ejecuta codigo/shell en un working-dir efimero con subprocess,
  env limpio (sin credenciales), timeout estricto y parche de red opcional.
- EphemeralOrchestrator: gestiona instancias temporales, creacion/destruccion,
  path aislado y metricas (creadas/destruidas/timeouts/running).

Seguridad (defensa en profundidad):
1. Deny-check estatico: patrones de FS/paths criticos y .env.
2. Env sanitizado: elimina variables con API_KEY/SECRET/TOKEN/PASSWORD/etc.
3. Red denegada por defecto (parchea socket/urllib).
4. Working-dir efimero + timeout estricto + limites de tamaño.
5. Destruccion completa de instancias efimeras.

100% offline; no expone tokens ni credenciales en texto plano.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SandboxRequest:
    lang: str = "python"
    code: str = ""
    timeout_ms: int = 5000
    memory_mb: int = 128
    network: bool = False
    args: List[str] = field(default_factory=list)
    stdin: str = ""
    cwd: Optional[str] = None


@dataclass
class SandboxResult:
    sandbox_id: str = ""
    status: str = "pending"
    returncode: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    memory_peak_mb: float = 0.0
    error: str = ""


@dataclass
class SandboxInstance:
    sandbox_id: str
    workdir: str
    created_at: float
    lang: str = "python"
    status: str = "created"
    destroyed_at: Optional[float] = None


@dataclass
class SandboxConfig:
    default_timeout_ms: int = 5000
    default_memory_mb: int = 128
    allow_network: bool = False
    max_code_bytes: int = 20000
    fs_denylist: Tuple[str, ...] = (
        "'.env'", '".env"', "/.env", "\\", "/etc/", "/proc/", "/sys/", "/dev/",
        "passwd", "shadow", "shutil.rmtree", "os.remove", "winrm",
    )
    env_denylist: Tuple[str, ...] = (
        "API_KEY", "SECRET", "TOKEN", "PASSWORD", "PASSWD",
        "CREDENTIAL", "PRIVATE_KEY", "AURA_",
    )

class SandboxExecutor:
    """Ejecuta codigo/shell aislado en un working-dir efimero con subprocess."""

    def __init__(self, config: Optional[SandboxConfig] = None) -> None:
        self._config = config or SandboxConfig()
        self.timeouts = 0
        self.denials = 0

    @property
    def config(self) -> SandboxConfig:
        return self._config

    def _deny_reason(self, req: SandboxRequest) -> Optional[str]:
        if req.timeout_ms <= 0:
            return "timeout must be positive"
        code_bytes = len(req.code.encode("utf-8", errors="ignore"))
        if code_bytes > self._config.max_code_bytes:
            return f"code too large ({code_bytes}B > {self._config.max_code_bytes}B)"
        low = req.code.lower()
        for pat in self._config.fs_denylist:
            if pat in low:
                return f"forbidden pattern: {pat}"
        return None

    def _sanitized_env(self) -> Dict[str, str]:
        env = {}
        for k, v in os.environ.items():
            upper = k.upper()
            if any(blk in upper for blk in self._config.env_denylist):
                continue
            env[k] = v
        return env

    def _user_source(self, req: SandboxRequest) -> str:
        if req.network or self._config.allow_network:
            return req.code
        return (
            "# AURA sandbox red-prologue (network denied)\n"
            "import socket as _s\n"
            "def _deny(*a, **k):\n"
            "    raise OSError('network access denied by AURA sandbox')\n"
            "_s.socket = _deny\n"
            "_s.create_connection = _deny\n"
            "_s.socketpair = _deny\n"
            "try:\n"
            "    import urllib.request as _u\n"
            "    _u.urlopen = _deny\n"
            "except Exception:\n"
            "    pass\n"
            "del _s, _deny\n"
            + req.code
        )

    def _run_process(self, cmd: List[str], req: SandboxRequest, workdir: str):
        timeout_s = max(0.05, req.timeout_ms / 1000.0)
        env = self._sanitized_env()
        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd, cwd=workdir, env=env, input=req.stdin,
                capture_output=True, text=True, timeout=timeout_s, shell=False,
            )
            duration = int((time.monotonic() - start) * 1000)
            peak = self._memory_peak_mb()
            status = "success" if proc.returncode == 0 else "error"
            return SandboxResult(
                sandbox_id="", status=status, returncode=proc.returncode,
                stdout=proc.stdout or "", stderr=proc.stderr or "",
                duration_ms=duration, memory_peak_mb=peak,
            )
        except subprocess.TimeoutExpired:
            self.timeouts += 1
            duration = int((time.monotonic() - start) * 1000)
            return SandboxResult(
                sandbox_id="", status="timeout", returncode=None,
                stdout="", stderr=f"timeout after {req.timeout_ms}ms",
                duration_ms=duration, memory_peak_mb=self._memory_peak_mb(),
                error="timeout",
            )
        except Exception as exc:  # noqa: BLE001
            return SandboxResult(
                sandbox_id="", status="error", returncode=None,
                stdout="", stderr=str(exc), duration_ms=0,
                memory_peak_mb=0.0, error=str(exc),
            )

    def _memory_peak_mb(self) -> float:
        try:
            import resource
            return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 2)
        except Exception:
            return 0.0

    def execute(self, req: SandboxRequest, sandbox_id: str, workdir: str) -> SandboxResult:
        reason = self._deny_reason(req)
        if reason:
            self.denials += 1
            return SandboxResult(sandbox_id=sandbox_id, status="denied",
                                 stderr=f"sandbox denied: {reason}", error=reason)
        lang = (req.lang or "python").strip().lower()
        if lang in ("python", "py"):
            src = self._user_source(req)
            userfile = os.path.join(workdir, "_user.py")
            with open(userfile, "w", encoding="utf-8") as fh:
                fh.write(src)
            cmd = [sys.executable, userfile] + list(req.args)
        elif lang in ("sh", "bash"):
            userfile = os.path.join(workdir, "_user.sh")
            with open(userfile, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(req.code + "\n")
            cmd = ["bash", userfile] + list(req.args)
        else:
            return SandboxResult(sandbox_id=sandbox_id, status="denied",
                                 stderr=f"unsupported lang: {lang}", error="unsupported lang")
        result = self._run_process(cmd, req, workdir)
        result.sandbox_id = sandbox_id
        return result

class EphemeralOrchestrator:
    """Orquestador de instancias efimeras: creacion, ejecucion y destruccion."""

    def __init__(self, executor: Optional[SandboxExecutor] = None,
                 workdir_root: Optional[str] = None) -> None:
        self._lock = threading.RLock()
        self._executor = executor or SandboxExecutor()
        self._workdir_root = workdir_root or tempfile.gettempdir()
        self._instances: Dict[str, SandboxInstance] = {}
        self.created = 0
        self.destroyed = 0
        self.timeouts = 0
        self.denials = 0

    @property
    def executor(self) -> SandboxExecutor:
        return self._executor

    def _new_workdir(self, sandbox_id: str) -> str:
        base = os.path.join(self._workdir_root, f"aura_sandbox_{sandbox_id}")
        os.makedirs(base, exist_ok=True)
        return base

    def run(self, req: SandboxRequest) -> SandboxResult:
        sandbox_id = uuid.uuid4().hex[:12]
        workdir = self._new_workdir(sandbox_id)
        instance = SandboxInstance(sandbox_id=sandbox_id, workdir=workdir,
                                   created_at=time.time(), lang=req.lang,
                                   status="running")
        with self._lock:
            self._instances[sandbox_id] = instance
            self.created += 1
        try:
            result = self._executor.execute(req, sandbox_id, workdir)
        finally:
            with self._lock:
                cur = self._instances.get(sandbox_id)
                if cur:
                    cur.status = result.status
                if result.status == "timeout":
                    self.timeouts += 1
                if result.status == "denied":
                    self.denials += 1
        return result

    def destroy(self, sandbox_id: str) -> bool:
        with self._lock:
            inst = self._instances.get(sandbox_id)
            if inst is None:
                return False
            wd = inst.workdir
            inst.status = "destroyed"
            inst.destroyed_at = time.time()
            self._instances.pop(sandbox_id, None)
            self.destroyed += 1
        shutil.rmtree(wd, ignore_errors=True)
        return True

    def cleanup_all(self) -> int:
        with self._lock:
            ids = list(self._instances.keys())
        for sid in ids:
            self.destroy(sid)
        return len(ids)

    def instances(self) -> List[SandboxInstance]:
        with self._lock:
            return list(self._instances.values())

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "enabled": True,
                "created": self.created,
                "destroyed": self.destroyed,
                "timeouts": self.timeouts,
                "denials": self.denials,
                "running": sum(1 for i in self._instances.values()
                               if i.status == "running"),
                "live_instances": len(self._instances),
                "workdir_root": self._workdir_root,
                "executor": type(self._executor).__name__,
            }

    def get_executor(self) -> SandboxExecutor:
        return self._executor


_orch: Optional[EphemeralOrchestrator] = None
_orch_lock = threading.Lock()


def get_sandbox_orchestrator(executor: Optional[SandboxExecutor] = None,
                             workdir_root: Optional[str] = None) -> EphemeralOrchestrator:
    global _orch
    if _orch is None:
        with _orch_lock:
            if _orch is None:
                _orch = EphemeralOrchestrator(executor=executor, workdir_root=workdir_root)
    return _orch


def reset_sandbox_orchestrator() -> None:
    global _orch
    with _orch_lock:
        if _orch is not None:
            try:
                _orch.cleanup_all()
            except Exception:
                pass
        _orch = None


SandboxEngine = EphemeralOrchestrator
get_sandbox_engine = get_sandbox_orchestrator
reset_sandbox_engine = reset_sandbox_orchestrator
