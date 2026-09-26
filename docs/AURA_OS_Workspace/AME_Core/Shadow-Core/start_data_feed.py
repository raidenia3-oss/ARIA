"""
start_data_feed.py - Script para iniciar el servidor de datos en tiempo real de Shadow-Core
"""

import os
import sys
import subprocess
import time
import logging
from pathlib import Path

# Configuración del logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def install_requirements():
    """Instala los requisitos necesarios para el servidor de datos"""
    requirements_path = Path(__file__).parent / 'requirements.txt'

    if not requirements_path.exists():
        logger.error(f"Archivo requirements.txt no encontrado en {requirements_path}")
        return False

    try:
        logger.info("Instalando requisitos...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', requirements_path])
        logger.info("Requisitos instalados con éxito")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error al instalar requisitos: {e}")
        return False
    except Exception as e:
        logger.error(f"Error inesperado al instalar requisitos: {e}")
        return False

def start_server():
    """Inicia el servidor de datos en tiempo real"""
    server_path = Path(__file__).parent / 'data_feed.py'

    if not server_path.exists():
        logger.error(f"Archivo data_feed.py no encontrado en {server_path}")
        return False

    try:
        logger.info("Iniciando servidor de datos en tiempo real...")
        subprocess.Popen([sys.executable, str(server_path)])
        logger.info("Servidor iniciado con éxito")
        return True
    except Exception as e:
        logger.error(f"Error al iniciar el servidor: {e}")
        return False

def main():
    """Función principal"""
    # Instalar requisitos si no están instalados
    if not install_requirements():
        logger.error("No se pudieron instalar los requisitos. Deteniendo ejecución.")
        return 1

    # Iniciar servidor
    if not start_server():
        logger.error("No se pudo iniciar el servidor. Deteniendo ejecución.")
        return 1

    logger.info("Servidor de datos en tiempo real iniciado correctamente")
    return 0

if __name__ == '__main__':
    sys.exit(main())