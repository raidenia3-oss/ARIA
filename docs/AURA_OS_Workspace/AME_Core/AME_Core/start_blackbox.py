"""
Script para iniciar la Caja Negra en el servidor AME.
"""

import sys
import os

# Añadir AME_Core al path para importar módulos
AME_CORE_DIR = os.path.dirname(os.path.abspath(__file__))
if AME_CORE_DIR not in sys.path:
    sys.path.insert(0, AME_CORE_DIR)

# Importar módulos de la Caja Negra
from tactical_log_manager import tactical_log_manager, TacticalLogHandler, init_tactical_logs
from blackbox_endpoint import register_blackbox_endpoint
from integrate_blackbox import integrate_blackbox

def start_blackbox(app, logger):
    """
    Inicia la Caja Negra en el servidor AME.
    :param app: Instancia de la aplicación Flask.
    :param logger: Logger de Flask para registrar eventos.
    """
    # Inicializar el sistema de logs tácticos
    tactical_log_manager = init_tactical_logs()

    # Añadir handler táctico al logger
    tactical_log_handler = TacticalLogHandler(tactical_log_manager)
    logger.addHandler(tactical_log_handler)

    # Registrar el endpoint de la Caja Negra
    register_blackbox_endpoint(app)

    # Mensaje de confirmación
    logger.info("✅ Caja Negra (BlackBox) integrada correctamente")
    logger.info("📜 Endpoint /api/tactical/logs disponible")

if __name__ == "__main__":
    print("Caja Negra lista para ser integrada en el servidor AME.")