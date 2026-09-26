"""
Script para integrar los endpoints tácticos en el servidor AME.
"""

import sys
import os

# Añadir AME_Core al path para importar módulos
AME_CORE_DIR = os.path.dirname(os.path.abspath(__file__))
if AME_CORE_DIR not in sys.path:
    sys.path.insert(0, AME_CORE_DIR)

# Importar módulos de los endpoints tácticos
from tactical_endpoints import register_tactical_endpoints

def integrate_tactical_endpoints(app, logger):
    """
    Integra los endpoints tácticos en la aplicación Flask.
    :param app: Instancia de la aplicación Flask.
    :param logger: Logger de Flask para registrar eventos.
    """
    # Registrar los endpoints tácticos
    register_tactical_endpoints(app)

    # Mensaje de confirmación
    logger.info("✅ Endpoints tácticos integrados correctamente")
    logger.info("📡 Endpoints disponibles: /api/tactical/world_state, /api/tactical/resources, /api/tactical/network, /api/tactical/console")