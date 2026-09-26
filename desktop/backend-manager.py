#!/usr/bin/env python3
"""
AURA Backend Process Manager for Desktop App Shell (Bloque 59).

Manages the lifecycle of the Python FastAPI backend process from the
native desktop wrapper. Starts, monitors, and stops the backend
transparently when the desktop app is launched or closed.

100% local: no cloud dependencies, no telemetry, no external services.
"""

import os
import sys
import signal
import subprocess
import time
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8000
PID_FILE = Path(__file__).resolve().parent / "backend.pid"
HEALTH_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}/health"

logger = logging.getLogger("AURA.BackendManager")


def get_python_executable() -> str:
    """Return the Python executable to use for the backend."""
    venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def is_backend_running() -> bool:
    """Check if the backend is already running and healthy."""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, ValueError):
            PID_FILE.unlink(missing_ok=True)
    return False


def wait_for_backend(timeout: float = 15.0) -> bool:
    """Poll the backend health endpoint until it responds or timeout."""
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=2) as resp:
                data = json.loads(resp.read())
                if data.get("status") == "healthy":
                    logger.info("Backend healthy at %s", HEALTH_URL)
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def start_backend() -> Optional[subprocess.Popen]:
    """Start the FastAPI backend as a detached child process."""
    if is_backend_running():
        logger.info("Backend already running")
        return None

    python_exe = get_python_executable()
    cmd = [
        python_exe, "-m", "uvicorn",
        "backend.main:app",
        "--host", BACKEND_HOST,
        "--port", str(BACKEND_PORT),
    ]

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    creationflags = 0
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    proc = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )

    PID_FILE.write_text(str(proc.pid))
    logger.info("Backend started (PID=%d)", proc.pid)
    return proc


def stop_backend() -> bool:
    """Stop the backend process gracefully."""
    if not PID_FILE.exists():
        return False

    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        time.sleep(1)
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        PID_FILE.unlink(missing_ok=True)
        logger.info("Backend stopped (PID=%d)", pid)
        return True
    except (ProcessLookupError, ValueError) as exc:
        logger.debug("Backend stop cleanup: %s", exc)
        PID_FILE.unlink(missing_ok=True)
        return False


def get_backend_status() -> Dict[str, Any]:
    """Return current backend status information."""
    running = is_backend_running()
    return {
        "running": running,
        "host": BACKEND_HOST,
        "port": BACKEND_PORT,
        "health_url": HEALTH_URL,
        "pid_file": str(PID_FILE),
    }


def ensure_backend() -> bool:
    """Ensure the backend is running; start it if necessary."""
    if not is_backend_running():
        start_backend()
    return wait_for_backend()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) > 1 and sys.argv[1] == "stop":
        stop_backend()
    else:
        if ensure_backend():
            print("Backend is running")
        else:
            print("Backend failed to start")
            sys.exit(1)