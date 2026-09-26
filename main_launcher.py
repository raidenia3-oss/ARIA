#!/usr/bin/env python3
"""
AURA Main Launcher - Orquestador Central
Levanta: Backend FastAPI + Swarm + WebSockets + Telemetría
"""

import subprocess
import sys
import time
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent


def check_dependencies():
    """Verifica que FastAPI, uvicorn, etc. estén instalados."""
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
        import websockets  # noqa: F401
        print("[OK] Dependencias core presentes")
        return True
    except ImportError as e:
        print(f"[FAIL] Falta dependencia: {e}")
        print("   Ejecutando: pip install -r requirements.txt")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
        return True


def start_backend():
    """Levanta FastAPI en puerto 8000."""
    print("\n>> Iniciando Backend FastAPI...")
    os.chdir(PROJECT_ROOT)

    cmd = [
        sys.executable, "-m", "uvicorn",
        "backend.main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
    ]

    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def start_frontend():
    """Levanta frontend React (si existe)."""
    frontend_dir = PROJECT_ROOT / "frontend" / "web_dashboard"
    if not frontend_dir.exists():
        print("[WARN] Frontend no encontrado en", frontend_dir)
        return None

    print("\n>> Iniciando Frontend React...")
    os.chdir(frontend_dir)

    if not (frontend_dir / "node_modules").exists():
        print("   Instalando dependencias npm...")
        subprocess.run(["npm", "install"], check=True)

    cmd = ["npm", "run", "dev"]
    if sys.platform == "win32":
        return subprocess.Popen(cmd, shell=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return subprocess.Popen(cmd)


def main():
    print("========================================")
    print("  AURA NUCLEUS OS - MAIN LAUNCHER")
    print("  Multi-Agent AI Core + Sci-Fi Dashboard")
    print("========================================\n")

    # Verificar dependencias
    check_dependencies()

    # Levantar backend
    backend_proc = start_backend()
    print("[OK] Backend iniciado (PID:", backend_proc.pid, ")")

    # Esperar a que FastAPI levante
    time.sleep(3)

    # Verificar que el backend está activo
    try:
        import requests
        resp = requests.get("http://localhost:8000/health", timeout=5)
        if resp.status_code == 200:
            print("[OK] Backend respondiendo en http://localhost:8000")
    except Exception:
        print("[WARN] Backend aún no responde, continuando...")

    # Levantar frontend
    frontend_proc = start_frontend()
    if frontend_proc:
        print("[OK] Frontend iniciado (PID:", frontend_proc.pid, ")")

    print("\n========================================")
    print("  SISTEMA ONLINE")
    print("  Backend:  http://localhost:8000")
    print("  Frontend: http://localhost:5173 (si npm está activo)")
    print("  Dashboard: http://localhost:8000/dashboard")
    print("========================================\n")

    try:
        backend_proc.wait()
    except KeyboardInterrupt:
        print("\nCerrando...")
        backend_proc.terminate()
        if frontend_proc:
            frontend_proc.terminate()


if __name__ == "__main__":
    main()
