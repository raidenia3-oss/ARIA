#!/usr/bin/env python3
"""
ame_updater.py — Actualizador automático para AME en Termux
Verifica actualizaciones en GitHub y aplica cambios automáticamente
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime

# Configuración
GITHUB_REPO = "TU_USUARIO/aura-ame"  # Cambiar por tu repositorio real
CHECK_INTERVAL_HOURS = 6  # Revisar cada 6 horas
LOG_FILE = Path("/sdcard/update_ame_log.txt")
VERSION_FILE = Path("/sdcard/version.json")  # Versión local en el celular

def get_latest_release():
    """Obtiene la última release de GitHub"""
    import requests
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
    """Obtiene la versión local de AME"""
    try:
        if VERSION_FILE.exists():
            with open(VERSION_FILE) as f:
                return json.load(f)["ame_client"]
        return "0.0.0"
    except Exception as e:
        log_message(f"⚠️  Error leyendo version.json: {e}")
        return "0.0.0"

def log_message(message):
    """Registra mensajes en el log"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"

    # Crear directorio si no existe
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Añadir mensaje al log
    with open(LOG_FILE, 'a') as f:
        f.write(log_entry)

    # Mostrar en consola
    print(f"[{timestamp}] {message}")

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
            # Verificar conexión a internet
            log_message("📡 Verificando conexión a internet...")
            if not check_internet():
                log_message("❌ Sin conexión a internet")
                return False

            # Clonar repositorio (o actualizar si ya existe)
            repo_path = Path("/sdcard/aura-ame")
            if not repo_path.exists():
                log_message("📥 Clonando repositorio por primera vez...")
                subprocess.run(["git", "clone", "https://github.com/TU_USUARIO/aura-ame.git", "/sdcard/aura-ame"],
                             check=True, capture_output=True)
            else:
                log_message("📥 Actualizando repositorio...")
                os.chdir("/sdcard/aura-ame")
                subprocess.run(["git", "pull", "origin", "main"], check=True, capture_output=True)

            # Copiar archivos esenciales
            log_message("📂 Copiando archivos esenciales...")
            essential_files = [
                "scripts/ame_config_generator.py",
                "scripts/test_ame_connection.py",
                "AME_Core/ame_client.py",
                "AME_Core/telemetria_radio.py",
                "version.json"
            ]

            for file_path in essential_files:
                src = repo_path / file_path
                dst = Path(f"/sdcard/{file_path}")

                if src.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    subprocess.run(["cp", str(src), str(dst)], check=True)
                    log_message(f"✅ Copiado: {file_path}")
                else:
                    log_message(f"⚠️  Archivo no encontrado: {file_path}")

            # Actualizar versión local
            with open(VERSION_FILE, 'w') as f:
                json.dump({"ame_client": remote_ver}, f, indent=2)

            log_message(f"✅ AME actualizado a {remote_ver}")
            log_message("🔄 Reinicia telemetry.py para aplicar cambios")
            return True
        except subprocess.CalledProcessError as e:
            log_message(f"❌ Error actualizando: {e.stderr.decode().strip()}")
            return False
        except Exception as e:
            log_message(f"❌ Error inesperado: {e}")
            return False
    else:
        log_message(f"✅ Versión actualizada ({local_ver})")
        return False

def check_internet():
    """Verifica conexión a internet"""
    try:
        import requests
        response = requests.get("https://1.1.1.1", timeout=5)
        return response.status_code == 200
    except Exception:
        return False

def setup_auto_update_cron():
    """Configura un cron job para actualizaciones automáticas"""
    log_message("📅 Configurando actualizaciones automáticas cada 6 horas...")

    # Verificar si termux-job-scheduler está instalado
    try:
        subprocess.run(["termux-job-scheduler", "--list"], capture_output=True, check=True)
        log_message("✅ termux-job-scheduler encontrado")

        # Programar tarea
        job_id = f"aura_ame_updater_{int(time.time())}"
        command = f"python /sdcard/aura-ame/scripts/ame_updater.py --silent"

        subprocess.run([
            "termux-job-scheduler",
            "--create",
            job_id,
            "--interval", "6/6",  # Cada 6 horas
            "--at", "00:00",     # A las 00:00
            "--exec", command
        ], check=True)

        log_message(f"✅ Tarea programada con ID: {job_id}")
        return True

    except subprocess.CalledProcessError:
        log_message("⚠️  termux-job-scheduler no encontrado. Usando sleep en segundo plano...")
        return False

def watch_loop(interval_hours=CHECK_INTERVAL_HOURS):
    """Bucle principal que revisa actualizaciones cada X horas"""
    log_message("🚀 Iniciando ame_updater.py")
    log_message(f"🔗 Repositorio: {GITHUB_REPO}")
    log_message(f"📡 Revisando cada {interval_hours} hora(s)")

    while True:
        try:
            update_if_needed()
            time.sleep(interval_hours * 3600)
        except KeyboardInterrupt:
            log_message("🛑 Deteniendo ame_updater...")
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

    if len(sys.argv) > 1 and sys.argv[1] == "--silent":
        # Modo silencioso para cron jobs
        update_if_needed()
        return

    # Configurar actualizaciones automáticas
    setup_auto_update_cron()

    # Iniciar bucle principal
    watch_loop()

if __name__ == "__main__":
    main()