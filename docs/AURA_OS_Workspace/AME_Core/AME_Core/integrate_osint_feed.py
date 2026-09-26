"""
Script para integrar el feed OSINT global en el servidor AME.
"""

import sys
import os

# Añadir AME_Core al path para importar módulos
AME_CORE_DIR = os.path.dirname(os.path.abspath(__file__))
if AME_CORE_DIR not in sys.path:
    sys.path.insert(0, AME_CORE_DIR)

# Importar módulos del feed OSINT
from osint_global_feed import register_osint_global_feed

def integrate_osint_feed(app, logger):
    """
    Integra el feed OSINT global en la aplicación Flask.
    :param app: Instancia de la aplicación Flask.
    :param logger: Logger de Flask para registrar eventos.
    """
    # Registrar el endpoint del feed OSINT
    register_osint_global_feed(app)

    # Mensaje de confirmación
    logger.info("✅ Feed OSINT global integrado correctamente")
    logger.info("🌍 Endpoint disponible: /api/osint/global_feed")