"""La autonomía de ARIA, dentro de su propio proceso.

ARIA no depende de ningún servicio: ni de un núcleo en otro puerto, ni de un
backend en Python, ni de un navegador. Todo lo que necesita para percibir,
decidir, actuar y aprender vive en este paquete y en archivos locales.

    from ARIA_APP.autonomy import get_runtime

    runtime = get_runtime()
    runtime.ingest("chat", "apunta revisar los logs", "escritorio")
    runtime.tick()
"""

from __future__ import annotations

from .perception import foreground_title, sense_drives, sense_worlds
from .runtime import (
    DATA_DIR,
    MAX_ATTEMPTS,
    PERSONA,
    SERVER,
    Runtime,
    get_runtime,
    reset_runtime,
    set_runtime,
)

__all__ = [
    "DATA_DIR",
    "MAX_ATTEMPTS",
    "PERSONA",
    "Runtime",
    "SERVER",
    "foreground_title",
    "get_runtime",
    "reset_runtime",
    "sense_drives",
    "sense_worlds",
    "set_runtime",
]
