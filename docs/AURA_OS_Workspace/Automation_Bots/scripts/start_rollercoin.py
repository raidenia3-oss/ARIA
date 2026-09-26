#!/usr/bin/env python3
"""
RollerCoin Starter - Script para iniciar el bot RollerCoin con manejo de reinicios
Autor: AURA System
Descripción: Inicia el bot RollerCoin y lo reinicia automáticamente si falla.
             Máximo 3 reinicios por hora para evitar spam en caso de errores graves.
"""

import os
import sys
import time
import subprocess
import signal
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()


def log_message(message):
    """Muestra un mensaje en consola con timestamp."""
    timestamp = datetime.now().strftime("[%H:%M:%S]")
    print(f"{timestamp} {message}")


def check_credentials():
    """Verifica que las credenciales estén configuradas en el archivo .env."""
    email = os.getenv("ROLLERCOIN_EMAIL")
    password = os.getenv("ROLLERCOIN_PASSWORD")

    if not email or not password:
        log_message("❌ Error: Credenciales no configuradas en .env")
        log_message("   Asegúrate de tener las siguientes variables en tu .env:")
        log_message("   ROLLERCOIN_EMAIL=tu@email.com")
        log_message("   ROLLERCOIN_PASSWORD=tupassword")
        return False
    return True


def install_playwright():
    """Instala Playwright y Chromium si no están instalados."""
    try:
        log_message("🔧 Verificando instalación de Playwright...")
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        log_message("✅ Playwright y Chromium instalados correctamente.")
        return True
    except subprocess.CalledProcessError as e:
        log_message(f"❌ Error al instalar Playwright: {e}")
        return False


def start_bot(headless=False, visible=False):
    """Inicia el bot RollerCoin con los argumentos especificados."""
    try:
        log_message("🚀 Iniciando RollerCoin Bot...")

        # Construir la lista de argumentos
        args = [sys.executable, "scripts/rollercoin_bot.py"]

        if headless:
            args.append("--headless")
        elif visible:
            args.append("--visible")

        # Iniciar el proceso del bot
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Función para leer la salida del proceso
        def read_output(process):
            for line in process.stdout:
                if line.strip():
                    log_message(line.strip())

        # Iniciar hilo para leer la salida
        import threading

        output_thread = threading.Thread(target=read_output, args=(process,))
        output_thread.daemon = True
        output_thread.start()

        return process
    except Exception as e:
        log_message(f"❌ Error al iniciar el bot: {e}")
        return None


def monitor_bot(process):
    """Monitorea el proceso del bot y lo reinicia si falla."""
    last_restart_time = datetime.now()
    restart_count = 0

    while True:
        try:
            # Verificar si el proceso aún está vivo
            process.poll()
            if process.returncode is not None:
                log_message("⚠️ El bot ha terminado inesperadamente. Reiniciando...")

                # Verificar si ha pasado más de una hora desde el último reinicio
                if (datetime.now() - last_restart_time) < timedelta(hours=1) and restart_count >= 3:
                    log_message(
                        "❌ Máximo de reinicios (3) alcanzado en la última hora. Deteniendo."
                    )
                    break

                # Reiniciar el bot
                restart_count += 1
                log_message(f"🔄 Reinicio {restart_count}/3...")
                process = start_bot()
                if process is None:
                    log_message("❌ No se pudo reiniciar el bot. Deteniendo.")
                    break
                last_restart_time = datetime.now()

            # Esperar un poco antes de verificar nuevamente
            time.sleep(10)

        except KeyboardInterrupt:
            log_message("🛑 Deteniendo el monitor del bot...")
            process.terminate()
            break
        except Exception as e:
            log_message(f"❌ Error en el monitor: {e}")
            time.sleep(60)  # Esperar antes de reintentar


def main():
    """Función principal del starter."""
    log_message("🔥 RollerCoin Starter - Iniciando bot con manejo de reinicios")

    # Verificar credenciales
    if not check_credentials():
        sys.exit(1)

    # Instalar Playwright si es necesario
    if not install_playwright():
        log_message(
            "❌ No se pudo instalar Playwright. Asegúrate de tener permisos de administrador."
        )
        sys.exit(1)

    # Iniciar el bot en modo visible por defecto
    process = start_bot(visible=True)

    if process is None:
        log_message("❌ No se pudo iniciar el bot.")
        sys.exit(1)

    # Monitorear el bot
    monitor_bot(process)


if __name__ == "__main__":
    main()
