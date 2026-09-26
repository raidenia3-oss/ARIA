"""
Script para integrar la Caja Negra en el servidor AME.
"""

import sys
import os
from AME_Core.tactical_log_manager import tactical_log_manager, TacticalLogHandler, init_tactical_logs
from AME_Core.blackbox_endpoint import register_blackbox_endpoint

def integrate_blackbox(app, logger):
    """
    Integra la Caja Negra en la aplicación Flask.
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