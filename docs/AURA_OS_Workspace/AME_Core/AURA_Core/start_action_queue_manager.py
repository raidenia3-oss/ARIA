"""
start_action_queue_manager.py - Script para iniciar el Action Queue Manager de AURA
Este script inicia el gestor de cola de acciones que requiere aprobación antes de ejecutarse.
"""

import os
import sys
import time
import logging
import subprocess
from pathlib import Path

# Configuración del logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def install_requirements():
    """Instalar requisitos adicionales para el Action Queue Manager"""
    try:
        logger.info("📦 Instalando requisitos para Action Queue Manager...")

        # Verificar si ya están instalados
        try:
            import socketio
            import dotenv
            logger.info("✅ Requisitos ya están instalados")
            return True
        except ImportError:
            pass

        # Instalar requisitos desde el archivo requirements_decision.txt
        requirements_file = Path("Shadow-Core/requirements_decision.txt")
        if requirements_file.exists():
            logger.info(f"📄 Encontrado archivo de requisitos: {requirements_file}")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info("✅ Requisitos instalados con éxito")
            logger.info(result.stdout)
            return True
        else:
            logger.error("❌ Archivo de requisitos no encontrado")
            return False

    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Error al instalar requisitos: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"❌ Error inesperado al instalar requisitos: {e}")
        return False

def start_action_queue_manager():
    """Iniciar el Action Queue Manager"""
    try:
        logger.info("🚀 Iniciando Action Queue Manager para AURA")

        # Verificar si el Action Queue Manager ya está en ejecución
        try:
            import action_queue_manager
            logger.info("✅ Action Queue Manager ya está en ejecución (módulo importado)")
            return True
        except ImportError:
            pass

        # Verificar si el archivo action_queue_manager.py existe
        action_queue_path = Path("AURA_Core/action_queue_manager.py")
        if not action_queue_path.exists():
            logger.error("❌ Archivo action_queue_manager.py no encontrado")
            return False

        # Iniciar el Action Queue Manager
        logger.info("🔌 Conectando Action Queue Manager al servidor...")
        import action_queue_manager
        action_queue_manager.main()

        return True

    except Exception as e:
        logger.error(f"❌ Error al iniciar Action Queue Manager: {e}")
        return False

def main():
    """Función principal"""
    logger.info("INICIANDO ACTION QUEUE MANAGER PARA AURA")
    logger.info("=" * 50)

    # Instalar requisitos
    if not install_requirements():
        logger.error("❌ No se pudieron instalar los requisitos. Deteniendo ejecución.")
        return False

    # Iniciar Action Queue Manager
    if not start_action_queue_manager():
        logger.error("❌ No se pudo iniciar Action Queue Manager.")
        return False

    logger.info("")
    logger.info("🎉 Action Queue Manager iniciado con éxito!")
    logger.info("   - Esperando solicitudes de aprobación de acciones")
    logger.info("   - Gestionando cola de acciones pendientes")
    logger.info("   - Registrando acciones en logs")
    logger.info("   - Reportando estado al dashboard")
    logger.info("")
    logger.info("Para detener el Action Queue Manager, presione Ctrl+C")

    try:
        # Mantener el script en ejecución
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 Action Queue Manager detenido por el usuario")

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)