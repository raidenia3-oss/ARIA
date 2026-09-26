"""AURA Desktop Launcher - Backend Process Management (Bloque 59).

Gestor del ciclo de vida del backend Python (FastAPI/uvicorn) desde la
aplicacion de escritorio nativa. Proporciona:
- Arranque/confirmacion/parada del backend como subproceso
- Verificacion de salud via /health
- Estado del proceso y metricas de arranque

100% local: no depende de servicios externos ni nubes.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURA.Desktop.Launcher")


@dataclass
class BackendProcessInfo:
    """Informacion sobre el proceso backend."""
    pid: int = 0
    return_code: Optional[int] = None
    started_at: float = 0.0
    stopped_at: float = 0.0
    command: List[str] = field(default_factory=list)
    stderr_lines: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        running = self.return_code is None and self.pid != 0
        if self.started_at and running:
            duration = time.time() - self.started_at
        elif self.started_at and self.stopped_at:
            duration = self.stopped_at - self.started_at
        else:
            duration = 0.0
        return {
            "pid": self.pid,
            "running": running,
            "return_code": self.return_code,
            "started_at": round(self.started_at, 2) if self.started_at else 0,
            "stopped_at": round(self.stopped_at, 2) if self.stopped_at else 0,
            "uptime_seconds": round(duration, 2),
            "command": self.command,
            "stderr_lines": self.stderr_lines[:50],
        }


class DesktopBackendLauncher:
    """Controla el proceso backend Python que alimenta la UI de escritorio."""

    def __init__(
        self,
        backend_module: str = "backend.main",
        uvicorn_host: str = "127.0.0.1",
        uvicorn_port: int = 8000,
        python_executable: Optional[str] = None,
        project_root: Optional[Path] = None,
    ) -> None:
        self._backend_module = backend_module
        self._host = uvicorn_host
        self._port = uvicorn_port
        self._python_executable = python_executable or sys.executable
        self._project_root = project_root or Path.cwd()
        self._process: Optional[subprocess.Popen] = None
        self._info: Optional[BackendProcessInfo] = None
        self._lock = threading.Lock()
        self._health_url = f"http://{self._host}:{self._port}"

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    @property
    def base_url(self) -> str:
        return self._health_url

    def start(self, timeout: float = 30.0) -> bool:
        """Inicia el proceso backend. Retorna True si /health responde."""
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                logger.info("Backend ya esta corriendo (pid=%s)", self._process.pid)
                return True

            cmd = [
                self._python_executable,
                "-m", "uvicorn",
                self._backend_module,
                "--host", self._host,
                "--port", str(self._port),
            ]
            if os.getenv("AURA_DEV_MODE", "0") == "1":
                cmd.append("--reload")

            logger.info("Iniciando backend: %s", " ".join(cmd))
            try:
                self._process = subprocess.Popen(
                    cmd,
                    cwd=str(self._project_root),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    env=os.environ.copy(),
                )
            except FileNotFoundError as exc:
                logger.error("No se encontro el ejecutable: %s", exc)
                return False

            self._info = BackendProcessInfo(
                pid=self._process.pid,
                started_at=time.time(),
                command=cmd,
            )
            logger.info("Backend iniciado con pid=%s", self._process.pid)

        return self._wait_for_health(timeout)


    def _wait_for_health(self, timeout: float = 30.0) -> bool:
        """Espera a que el backend responda /health."""
        import urllib.request
        url = f"{self._health_url}/health"
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=3) as resp:
                    if resp.status == 200:
                        logger.info("Backend health check OK")
                        return True
            except Exception:
                time.sleep(1.0)
        logger.error("Backend no respondio en %ss", timeout)
        return False

    def stop(self) -> bool:
        """Detiene el proceso backend."""
        with self._lock:
            if self._process is None:
                return True
            pid = self._process.pid
            if self._process.poll() is None:
                try:
                    if sys.platform == "win32":
                        self._process.send_signal(signal.CTRL_BREAK_EVENT)
                    else:
                        self._process.send_signal(signal.SIGTERM)
                except Exception:
                    self._process.kill()
                try:
                    self._process.wait(timeout=5.0)
                except Exception:
                    self._process.kill()
                    self._process.wait(timeout=2.0)
            if self._info:
                self._info.return_code = self._process.returncode
                self._info.stopped_at = time.time()
            logger.info("Backend detenido (pid=%s, rc=%s)", pid, self._process.returncode)
            self._process = None
            return True

    def restart(self, timeout: float = 30.0) -> bool:
        """Reinicia el proceso backend."""
        self.stop()
        time.sleep(1.0)
        return self.start(timeout)

    def get_info(self) -> Dict[str, Any]:
        with self._lock:
            if self._info is None:
                return {"running": False}
            return self._info.to_dict()

    def is_running(self) -> bool:
        with self._lock:
            return self._process is not None and self._process.poll() is None


_launcher: Optional[DesktopBackendLauncher] = None


def get_launcher() -> DesktopBackendLauncher:
    """Retorna el launcher singleton, creandolo si es necesario."""
    global _launcher
    if _launcher is None:
        _launcher = DesktopBackendLauncher()
    return _launcher


def reset_launcher() -> None:
    """Reinicia el launcher singleton y detiene el backend si esta activo."""
    global _launcher
    if _launcher and _launcher.is_running():
        _launcher.stop()
    _launcher = None


__all__ = [
    "BackendProcessInfo",
    "DesktopBackendLauncher",
    "get_launcher",
    "reset_launcher",
]
