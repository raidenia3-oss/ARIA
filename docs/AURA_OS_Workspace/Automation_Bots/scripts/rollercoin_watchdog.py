"""
Watchdog para Rollercoin Automation
Verifica si el proceso de automatización está corriendo y lo reinicia si es necesario.
"""

import subprocess
import os
import sys
import time
import signal
from datetime import datetime

ROLLERCOIN_SCRIPT = "AME_Core/rollercoin/main_v2.py"
LOG_FILE = "rollercoin_watchdog.log"
CHECK_INTERVAL = 30  # segundos
MAX_RETRIES = 3


def log(message):
    """Registra mensajes en el archivo de log"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"
    with open(LOG_FILE, "a") as f:
        f.write(log_entry)
    print(log_entry.strip())


def is_process_running():
    """Verifica si el proceso de Rollercoin está corriendo"""
    try:
        # Buscar procesos de Python que estén ejecutando el script
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True, check=True)

        for line in result.stdout.splitlines():
            if ROLLERCOIN_SCRIPT in line and "python" in line.lower():
                return True
        return False
    except Exception as e:
        log(f"Error al verificar procesos: {e}")
        return False


def start_rollercoin():
    """Inicia el proceso de Rollercoin en segundo plano"""
    try:
        log("Iniciando automatización de Rollercoin...")
        # Usar pythonw para evitar ventana de consola en Windows
        if sys.platform == "win32":
            subprocess.Popen(
                [sys.executable, ROLLERCOIN_SCRIPT],
                shell=True,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            subprocess.Popen(
                [sys.executable, ROLLERCOIN_SCRIPT],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        log("Automatización de Rollercoin iniciada correctamente")
        return True
    except Exception as e:
        log(f"Error al iniciar Rollercoin: {e}")
        return False


def main():
    log("=" * 50)
    log("🤖 WATCHDOG DE ROLLERCOIN INICIADO")
    log(f"Verificando cada {CHECK_INTERVAL} segundos...")
    log("=" * 50)

    retries = 0

    while True:
        try:
            if not is_process_running():
                log("⚠️ Automatización de Rollercoin NO está corriendo")

                if retries < MAX_RETRIES:
                    log(f"Intentando reiniciar (intento {retries + 1}/{MAX_RETRIES})...")
                    if start_rollercoin():
                        retries = 0  # Reiniciar contador si tuvo éxito
                    else:
                        retries += 1
                else:
                    log("❌ Máximo de intentos alcanzado. Deteniendo watchdog.")
                    break
            else:
                log("🤖 Automatización de Rollercoin activa y ejecutándose")
                retries = 0  # Reiniciar contador si está corriendo

        except KeyboardInterrupt:
            log("⛔ Detenido por el usuario")
            break
        except Exception as e:
            log(f"❌ Error en watchdog: {e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
