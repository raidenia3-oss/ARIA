#!/usr/bin/env python3
"""
Guardian System Watchdog
Monitorea el servidor Flask en el puerto 5000 y realiza auto-reinicio en caso de fallos.
Incluye logging detallado en system_health.log y manejo de procesos con taskkill.
"""

import os
import sys
import time
import subprocess
import logging
import platform
from datetime import datetime

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('system_health.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('GuardianWatchdog')

# Configuración global
SERVER_PORT = 5000
MAX_RETRIES = 3
RETRY_DELAY = 10  # segundos entre reinicios
SERVER_SCRIPT = 'AME_Core/servidor_ame.py'
PID_FILE = 'flask_server.pid'

def kill_python_processes():
    """Mata todos los procesos de Python en ejecución."""
    try:
        if platform.system() == 'Windows':
            subprocess.run(['taskkill', '/F', '/IM', 'python.exe', '/T'], check=True)
            logger.info("🔥 Todos los procesos Python han sido terminados con taskkill.")
        else:
            # Para Linux/Mac, matar procesos Python con ps aux | grep python
            subprocess.run(['pkill', '-f', 'python'], check=True)
            logger.info("🔥 Todos los procesos Python han sido terminados con pkill.")
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Error al matar procesos Python: {e}")

def check_server_health():
    """Verifica si el servidor Flask está respondiendo."""
    try:
        response = subprocess.run(
            ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', f'http://localhost:{SERVER_PORT}/health'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return response.stdout.strip() == '200'
    except subprocess.TimeoutExpired:
        return False
    except Exception as e:
        logger.error(f"❌ Error al verificar salud del servidor: {e}")
        return False

def start_server():
    """Inicia el servidor Flask."""
    global server_process
    try:
        # Verificar si ya existe un proceso en ejecución
        if os.path.exists(PID_FILE):
            with open(PID_FILE, 'r') as f:
                pid = int(f.read().strip())
            try:
                os.kill(pid, 0)  # Verificar si el proceso existe
                logger.info(f"Servidor ya está en ejecución con PID: {pid}")
                return True
            except ProcessLookupError:
                logger.warning(f"Archivo PID {PID_FILE} existe, pero el proceso no. Eliminando...")
                os.remove(PID_FILE)

        # Matar cualquier proceso Python residual antes de iniciar
        kill_python_processes()

        # Iniciar el servidor Flask
        logger.info("🚀 Iniciando servidor Flask...")
        server_process = subprocess.Popen(
            [sys.executable, SERVER_SCRIPT],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )

        # Guardar el PID del servidor
        with open(PID_FILE, 'w') as f:
            f.write(str(server_process.pid))

        logger.info(f"✅ Servidor iniciado con PID: {server_process.pid}")
        return True
    except Exception as e:
        logger.error(f"❌ Error al iniciar el servidor: {e}")
        return False

def log_recovery_attempt(attempt_number, success):
    """Registra un intento de recuperación en system_health.log."""
    status = "ÉXITO" if success else "FRACASO"
    log_message = (
        f"🔄 INTENTO {attempt_number}/{MAX_RETRIES} DE RECUPERACIÓN - "
        f"Servidor Flask {status} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    logger.info(log_message)

def main():
    """Función principal del watchdog."""
    global server_process
    server_process = None
    retries = 0

    logger.info("🔍 Guardian System Watchdog iniciado. Monitoreando servidor Flask...")

    while True:
        if not server_process or not check_server_health():
            if server_process:
                logger.warning("🚨 Servidor no está respondiendo. Reiniciando...")

            if retries < MAX_RETRIES:
                logger.info(f"🔄 Intento {retries + 1} de {MAX_RETRIES}...")
                if start_server():
                    retries = 0  # Reiniciar contador de intentos si el servidor se inicia correctamente
                    log_recovery_attempt(retries + 1, True)
                else:
                    retries += 1
                    log_recovery_attempt(retries, False)
            else:
                logger.error("💥 Máximo número de reinicios alcanzado. Deteniendo el sistema para evitar corrupción de datos.")
                kill_python_processes()
                logger.error("🛑 Sistema detenido. Se requiere intervención manual.")
                break

            if server_process:
                time.sleep(RETRY_DELAY)  # Esperar antes de verificar nuevamente
        else:
            retries = 0  # Reiniciar contador de intentos si el servidor está funcionando
            time.sleep(5)  # Verificar cada 5 segundos si el servidor está funcionando

if __name__ == "__main__":
    main()