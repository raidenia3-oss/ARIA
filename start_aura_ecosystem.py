#!/usr/bin/env python3
"""
AURA Ecosystem Orchestrator
Levanta simultáneamente:
- Backend FastAPI
- Frontend React/Vite
- Quickshell Bridge
- Cliente Móvil Flet
"""

import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
BACKEND_DIR = PROJECT_ROOT
FRONTEND_DIR = PROJECT_ROOT / "frontend" / "web_dashboard"
MOBILE_DIR = PROJECT_ROOT / "mobile_client"

processes = []
shutdown_event = threading.Event()


def _start_process(name: str, cmd, cwd=None, env=None):
    use_shell = sys.platform == "win32"
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        shell=use_shell,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    processes.append((name, proc))
    return proc


def _tail_process(name: str, proc: subprocess.Popen) -> None:
    try:
        for line in proc.stdout:
            if shutdown_event.is_set():
                break
            print(f"[{name}] {line.rstrip()}")
    except Exception:
        pass


def start_backend() -> subprocess.Popen:
    print("[ORCH] Starting Backend FastAPI...")
    if sys.platform == "win32":
        cmd = "python -m uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload"
    else:
        cmd = [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]
    return _start_process("backend", cmd, cwd=BACKEND_DIR)


def start_frontend() -> subprocess.Popen:
    print("[ORCH] Starting Frontend Web...")
    cmd = "npm run dev" if sys.platform == "win32" else ["npm", "run", "dev"]
    return _start_process("frontend", cmd, cwd=FRONTEND_DIR)


def start_quickshell_bridge():
    print("[ORCH] Starting Quickshell Bridge...")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "quickshell_bridge",
        str(PROJECT_ROOT / "backend" / "services" / "quickshell_bridge.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.start_bridge()
    while not shutdown_event.is_set():
        time.sleep(1)


def start_mobile() -> subprocess.Popen:
    print("[ORCH] Starting Mobile Client...")
    cmd = "python app.py" if sys.platform == "win32" else [sys.executable, "app.py"]
    return _start_process("mobile", cmd, cwd=MOBILE_DIR)


def wait_for_backend(timeout: int = 30) -> bool:
    import requests
    start = time.time()
    while time.time() - start < timeout:
        try:
            requests.get("http://localhost:8001/health", timeout=2)
            return True
        except Exception:
            time.sleep(1)
    return False


def shutdown(signum=None, frame=None):
    print("\n[ORCH] Shutting down ecosystem...")
    shutdown_event.set()
    for name, proc in reversed(processes):
        try:
            if proc.poll() is None:
                print(f"[ORCH] Stopping {name}...")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        except Exception:
            pass
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, shutdown)

    print("========================================")
    print("  AURA NUCLEUS OS - ECOSYSTEM LAUNCHER")
    print("========================================\n")

    backend_proc = start_backend()
    frontend_proc = start_frontend()
    mobile_proc = start_mobile()

    threading.Thread(
        target=_tail_process,
        args=("backend", backend_proc),
        daemon=True,
    ).start()
    threading.Thread(
        target=_tail_process,
        args=("frontend", frontend_proc),
        daemon=True,
    ).start()
    threading.Thread(
        target=_tail_process,
        args=("mobile", mobile_proc),
        daemon=True,
    ).start()

    qs_thread = threading.Thread(target=start_quickshell_bridge, daemon=True)
    qs_thread.start()

    print("[ORCH] Waiting for backend to become healthy...")
    ok = wait_for_backend(timeout=30)
    if ok:
        print("[ORCH] Backend is healthy.\n")
    else:
        print("[WARN] Backend did not respond in time, continuing anyway.\n")

    print("========================================")
    print("  ECOSYSTEM ONLINE")
    print("  Backend API : http://localhost:8001")
    print("  Health      : http://localhost:8001/health")
    print("  Dashboard   : http://localhost:8001/dashboard")
    print("  Frontend    : http://localhost:5173 (Vite dev)")
    print("  Mobile      : Flet window (desktop sim)")
    print("========================================")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
