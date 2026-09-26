#!/usr/bin/env python3
"""
AURA Keep Alive - Sistema para mantener el servidor despierto en Railway
Hace peticiones periódicas a endpoints internos para evitar que el servidor se duerma
"""

import os
import sys
import time
import subprocess
import requests
import logging
from datetime import datetime
from flask import Flask, jsonify

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("logs/keep_alive.log"), logging.StreamHandler()],
)
logger = logging.getLogger("AURAKeepAlive")

# Configuración global
KEEP_ALIVE_INTERVAL = 600  # 10 minutos en segundos
HEALTH_ENDPOINT = "/health"
STATUS_ENDPOINT = "/status"
MAX_RETRIES = 3
START_TIME = time.time()


def _get_ram_usage():
    if sys.platform == "win32":
        return "N/A"
    try:
        return (
            subprocess.check_output(
                "free -m | awk 'NR==2{printf \"%.2f\", $3*100/$2 }'",
                shell=True,
            )
            .decode()
            .strip()
        )
    except Exception:
        return "N/A"


def _get_cpu_usage():
    if sys.platform == "win32":
        return "N/A"
    try:
        return (
            subprocess.check_output(
                'top -bn1 | grep "Cpu(s)" | sed "s/.*, *\\([0-9.]*\\)%* id.*/\\1/" | awk \'{print 100 - $1}\'',
                shell=True,
            )
            .decode()
            .strip()
        )
    except Exception:
        return "N/A"

# Inicializar Flask para endpoints internos
app = Flask(__name__)


@app.route(HEALTH_ENDPOINT)
def health_check():
    """Endpoint para verificar la salud del servidor"""
    return jsonify(
        {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "message": "Servidor AURA funcionando correctamente",
        }
    )


@app.route(STATUS_ENDPOINT)
def status_check():
    """Endpoint para obtener el estado del sistema"""
    return jsonify(
        {
            "status": "operational",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "system": {
                "ram_usage": _get_ram_usage(),
                "cpu_usage": _get_cpu_usage(),
                "uptime": int(time.time() - START_TIME),
            },
            "message": "Estado del sistema actualizado",
        }
    )


def keep_alive_loop():
    """Bucle principal para mantener el servidor despierto"""
    logger.info("Iniciando sistema de keep-alive")
    logger.info(f"Intervalo de keep-alive: {KEEP_ALIVE_INTERVAL} segundos")

    while True:
        try:
            # Hacer petición al endpoint de salud
            response = requests.get(f"http://localhost{HEALTH_ENDPOINT}", timeout=5)
            if response.status_code == 200:
                logger.info(
                    f"Ping exitoso al endpoint {HEALTH_ENDPOINT} - {response.status_code}"
                )
            else:
                logger.warning(
                    f"Petición fallida al endpoint {HEALTH_ENDPOINT}: {response.status_code}"
                )

            # Hacer petición al endpoint de estado
            response = requests.get(f"http://localhost{STATUS_ENDPOINT}", timeout=5)
            if response.status_code == 200:
                logger.info(
                    f"Ping exitoso al endpoint {STATUS_ENDPOINT} - {response.status_code}"
                )
            else:
                logger.warning(
                    f"Petición fallida al endpoint {STATUS_ENDPOINT}: {response.status_code}"
                )

            # Registrar actividad
            logger.debug(
                f"Keep-alive ejecutado a las {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
            )

        except requests.exceptions.RequestException as e:
            logger.error(f"Error al hacer keep-alive: {str(e)}")
        except Exception as e:
            logger.error(f"Error inesperado en keep-alive: {str(e)}")

        # Esperar hasta la próxima ejecución
        time.sleep(KEEP_ALIVE_INTERVAL)


def main():
    """Punto de entrada principal"""
    # Iniciar el servidor Flask en un hilo separado
    import threading

    flask_thread = threading.Thread(
        target=app.run, kwargs={"port": 5000, "use_reloader": False}
    )
    flask_thread.daemon = True
    flask_thread.start()

    # Esperar un momento para que el servidor inicie
    time.sleep(2)

    # Iniciar el bucle de keep-alive
    keep_alive_loop()


if __name__ == "__main__":
    main()
