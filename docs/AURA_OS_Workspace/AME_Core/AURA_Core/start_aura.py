#!/usr/bin/env python3
"""Punto de entrada único para arrancar AURA Nexus."""

import logging
import signal
import sys
import os
import time

# Asegurar que el directorio raíz del proyecto esté en sys.path para imports absolutos
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configurar logging básico a consola
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("AURA_Start")

from AURA_Core.nexus import nexus  # noqa: E402


def main() -> int:
    logger.info("Iniciando AURA Core mediante AURANexus...")
    estado = nexus.arrancar_sistema()
    ok = estado.get("ok", False)
    if not ok:
        logger.error("Aranque parcial con errores: %s", estado)
    else:
        logger.info("AURA Nexus operativo. Componentes: %s", estado.get("pasos"))
    print("ESTADO_SISTEMA:", nexus.obtener_estado())
    # Mantener el proceso vivo hasta SIGINT/SIGTERM
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Interrupción recibida, deteniendo sistema...")
    nexus.detener_sistema()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
