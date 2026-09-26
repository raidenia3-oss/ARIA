#!/usr/bin/env python3
"""
auto_updater.py — Verifica actualizaciones en GitHub y actualiza AURA Core automáticamente
Corre en segundo plano en AURA Core y revisa GitHub cada hora
"""

import os
import sys
import json
import time
import subprocess
import requests
from pathlib import Path
from datetime import datetime

# Configuración
GITHUB_REPO = "TU_USUARIO/aura-ame"  # Cambiar por tu repositorio real
CHECK_INTERVAL_HOURS = 1  # Revisar cada hora
LOG_FILE = Path(__file__).resolve().parent.parent / "update_log.txt"
VERSION_FILE = Path(__file__).resolve().parent.parent / "version.json"

def get_latest_release():
    """Obtiene la última release de GitHub"""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            log_message(f"⚠️  Error obteniendo releases: HTTP {response.status_code}")
            return None
    except Exception as e:
        log_message(f"⚠️  Error de conexión: {e}")
        return None

def get_local_version():
    """Obtiene la versión local de AURA Core"""
    try:
        with open(VERSION_FILE) as f:
            return json.load(f)["aura_core"]
    except Exception as e:
        log_message(f"⚠️  Error leyendo version.json: {e}")
        return "0.0.0"

def log_message(message):
    """Registra mensajes en el log"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"
    LOG_FILE.write_text(log_entry, encoding="utf-8")

def update_if_needed():
    """Verifica si hay actualización disponible y la aplica"""
    release = get_latest_release()
    if not release:
        return False

    remote_ver = release["tag_name"].lstrip("v")
    local_ver = get_local_version()

    if remote_ver != local_ver:
        log_message(f"🔄 Actualización disponible: {local_ver} → {remote_ver}")
        log_message(f"📝 Cambios: {release['body'][:200]}...")

        try:
            # Pull automático
            log_message("📥 Realizando git pull...")
            subprocess.run(["git", "pull", "origin", "main"], check=True, capture_output=True)

            # Verificar que el pull fue exitoso
            if subprocess.run(["git", "status"], capture_output=True).returncode == 0:
                log_message("✅ Código actualizado")

                # Reiniciar servicios
                log_message("🔄 Reiniciando servicios...")
                subprocess.run([sys.executable, "scripts/start_aura.py", "--restart"], check=True)

                # Actualizar versión local
                with open(VERSION_FILE) as f:
                    versions = json.load(f)
                versions["aura_core"] = remote_ver
                with open(VERSION_FILE, 'w') as f:
                    json.dump(versions, f, indent=2)

                log_message(f"✅ Versión actualizada a {remote_ver}")
                return True
            else:
                log_message("❌ Error en git pull")
                return False

        except subprocess.CalledProcessError as e:
            log_message(f"❌ Error actualizando: {e.stderr.decode().strip()}")
            return False
        except Exception as e:
            log_message(f"❌ Error inesperado: {e}")
            return False
    else:
        log_message(f"✅ Versión actualizada ({local_ver})")
        return False

def watch_loop():
    """Bucle principal que revisa actualizaciones cada X horas"""
    log_message("🚀 Iniciando auto_updater.py")
    log_message(f"🔗 Repositorio: {GITHUB_REPO}")
    log_message(f"📡 Revisando cada {CHECK_INTERVAL_HOURS} hora(s)")

    while True:
        try:
            update_if_needed()
            time.sleep(CHECK_INTERVAL_HOURS * 3600)
        except KeyboardInterrupt:
            log_message("🛑 Deteniendo auto_updater...")
            break
        except Exception as e:
            log_message(f"❌ Error en bucle: {e}")
            time.sleep(60)  # Esperar 1 minuto antes de reintentar

def main():
    """Punto de entrada principal"""
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Modo de prueba: solo verifica una vez
        log_message("🔍 Modo de prueba: verificando una vez...")
        update_if_needed()
        return

    # Crear directorio de logs si no existe
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Iniciar bucle principal
    watch_loop()

if __name__ == "__main__":
    main()