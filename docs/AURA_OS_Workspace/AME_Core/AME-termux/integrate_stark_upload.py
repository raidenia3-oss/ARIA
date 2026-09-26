"""
Script para integrar el endpoint de subida de imágenes en el servidor AME.
"""

import sys
import os

# Añadir AME_Core al path para importar módulos
AME_CORE_DIR = os.path.dirname(os.path.abspath(__file__))
if AME_CORE_DIR not in sys.path:
    sys.path.insert(0, AME_CORE_DIR)

# Importar módulos del Stark Extraction Engine
from stark_upload_endpoint import register_stark_upload_endpoint

def integrate_stark_upload(app, logger):
    """
    Integra el endpoint de subida de imágenes en la aplicación Flask.
    :param app: Instancia de la aplicación Flask.
    :param logger: Logger de Flask para registrar eventos.
    """
    # Registrar el endpoint de subida de imágenes
    register_stark_upload_endpoint(app)

    # Mensaje de confirmación
    logger.info("✅ Endpoint de subida de imágenes para Stark Extraction Engine integrado correctamente")
    logger.info("📤 Endpoint disponible: /api/stark/upload_intel")