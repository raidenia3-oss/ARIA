#!/usr/bin/env python3
"""
start_aura.py — Script maestro que inicia TODO: AURA Core + Cloudflare Tunnel + Godot Bridge.
Monitorea cada servicio cada 10s y reinicia automáticamente si alguno cae.
"""

import os
import sys
import time
import json
import subprocess
import threading
import platform
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
URLS_FILE = ROOT_DIR / "aura_urls.json"
STATUS_FILE = ROOT_DIR / "aura_status.json"


class ServiceManager:
    def __init__(self):
        self.processes = {}
        self.config = self._load_config()
        self.running = True

    def _load_config(self) -> dict:
        """Carga aura_urls.json si existe."""
        if URLS_FILE.exists():
            with open(URLS_FILE) as f:
                return json.load(f)
        return {"mode": "trycloudflare", "urls": {}}

    def _start_service(self, name, cmd, cwd=None):
        try:
            p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.processes[name] = {
                "process": p,
                "restarts": 0,
                "started": datetime.now().isoformat(),
                "cmd": cmd,
                "cwd": cwd,
            }
            print(f"  ✅ {name} iniciado (PID: {p.pid})")
            return True
        except Exception as e:
            print(f"  ❌ Error iniciando {name}: {e}")
            return False

    def _is_alive(self, name) -> bool:
        return self.processes[name]["process"].poll() is None

    def _restart_service(self, name, cmd, cwd=None):
        print(f"  🔄 Reiniciando {name}...")
        old = self.processes[name]
        try:
            old["process"].terminate()
            old["process"].wait(timeout=5)
        except Exception:
            try:
                old["process"].kill()
            except Exception:
                pass
        old["restarts"] += 1
        self._start_service(name, cmd, cwd)

    def start_all(self):
        print("\n🚀 Iniciando servicios AURA Core...\n")

        # 1) cloudflared
        config_path = str(ROOT_DIR / "cloudflared" / "config.yml")
        self._start_service(
            "cloudflared", ["cloudflared", "tunnel", "run", "--config", config_path]
        )

        # 2) event_bus.py (placeholder - puerta 8765)
        # self._start_service("event_bus", [sys.executable, str(ROOT_DIR / "AURA_Core" / "event_bus.py")])

        # 3) godot_bridge.py
        self._start_service(
            "godot_bridge", [sys.executable, str(ROOT_DIR / "AURA_Core" / "godot_bridge.py")]
        )

        # 4) servidor_ame.py
        self._start_service(
            "servidor_ame", [sys.executable, str(ROOT_DIR / "AME_Core" / "servidor_ame.py")]
        )

        # 5) Godot File Watcher (para hot-reload automático)
        self.start_godot_watcher()

        # 6) N8N keep-alive (ping cada 10 min)
        self._start_service(
            "n8n_alive", [sys.executable, str(ROOT_DIR / "scripts" / "keep_n8n_alive.py")]
        )

    def start_godot_watcher(self):
        """Inicia el watcher de Godot para hot-reload automático."""
        try:
            print("👁️ Iniciando Godot File Watcher...")

            # Verificar que Godot esté instalado
            if not self.check_godot_installed():
                print("⚠️ No se puede iniciar el watcher de Godot sin Godot instalado")
                return False

            # Verificar que el proyecto Godot exista
            godot_project = os.path.join(os.getcwd(), "godot_game")
            if not os.path.exists(godot_project):
                print(f"⚠️ El proyecto Godot no existe en: {godot_project}")
                print("🔧 Crea el proyecto Godot en la carpeta 'godot_game'")
                return False

            # Iniciar el watcher en un hilo separado
            import scripts.godot_file_watcher as watcher_module

            watcher = watcher_module.GodotFileWatcher(project_path="godot_game/")
            watcher_thread = threading.Thread(target=watcher.start)
            watcher_thread.daemon = True
            watcher_thread.start()

            print("✅ Godot File Watcher iniciado correctamente")
            return True

        except Exception as e:
            print(f"❌ Error al iniciar Godot File Watcher: {e}")
            import traceback

            traceback.print_exc()
            return False

    def check_godot_installed(self) -> bool:
        """Verifica si Godot está instalado."""
        try:
            result = subprocess.run(
                ["godot", "--version"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                print("✅ Godot está instalado correctamente")
                return True
            else:
                print("❌ Godot no está instalado")
                print("🔧 Instrucciones para instalar Godot 4.x (gratis):")
                print("1. Descarga Godot desde: https://godotengine.org/download")
                print("2. Instálalo en una ruta estándar (ej: C:\\Program Files\\Godot)")
                print("3. Asegúrate de que Godot esté en tu PATH")
                return False
        except Exception as e:
            print(f"❌ Error al verificar Godot: {e}")
            return False

    def monitor(self):
        """Monitorea cada servicio cada 10s, reinicia si cae."""
        print("\n📡 Monitoreo activo (Ctrl+C para detener)...\n")
        while self.running:
            all_ok = True
            for name, svc in self.processes.items():
                if not self._is_alive(name):
                    all_ok = False
                    print(f"  ⚠️  {name} caído. Reiniciando...")
                    cmd = svc.get("cmd")
                    cwd = svc.get("cwd")
                    if cmd:
                        self._restart_service(name, cmd, cwd)
            time.sleep(10)

    def stop_all(self):
        print("\n⏹ Deteniendo servicios...")
        for name, svc in self.processes.items():
            try:
                svc["process"].terminate()
                svc["process"].wait(timeout=5)
                print(f"  ⏹ {name} detenido")
            except Exception:
                try:
                    svc["process"].kill()
                except Exception:
                    pass
        self.running = False


def save_status(manager):
    status = {"timestamp": datetime.now().isoformat(), "services": {}}
    for name, svc in manager.processes.items():
        status["services"][name] = {
            "alive": manager._is_alive(name),
            "pid": svc["process"].pid,
            "restarts": svc["restarts"],
        }
    STATUS_FILE.write_text(json.dumps(status, indent=2))


def start_antigravity_bridge():
    """Inicia el bridge de Antigravity si está configurado"""
    api_key = None
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.strip().startswith("ANTIGRAVITY_API_KEY="):
                    api_key = line.strip().split("=", 1)[1]
                    break
    if not api_key:
        print("⚠️  Antigravity no configurado (sin API key)")
        print("   Corre: python scripts/antigravity_setup.py")
        return None
    proc = subprocess.Popen(
        [sys.executable, "scripts/antigravity_bridge.py", "--listen"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    print(f"🤖 Antigravity Bridge iniciado (PID {proc.pid})")
    return proc


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AURA Core — Script de inicio maestro")
    parser.add_argument("--no-tunnel", action="store_true", help="No iniciar cloudflared")
    args = parser.parse_args()

    print("=" * 55)
    print("  AURA Core — Inicio Maestro")
    print("=" * 55)

    manager = ServiceManager()
    manager.start_all()
    save_status(manager)

    try:
        manager.monitor()
    except KeyboardInterrupt:
        print("\n\nSaliendo...")
    finally:
        manager.stop_all()
        save_status(manager)
