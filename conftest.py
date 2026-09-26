"""Conftest raiz de AURA (ayuda a Kilo — arregla el resumen de la suite completa).

Problema: huggingface_hub registra un hook ``atexit`` (``close_session``) que
cierra el cliente httpx compartido AL TERMINAR el interprete. httpcore emite
logs DEBUG en ese cierre, pero los handlers apuntan al stderr capturado por
pytest, que YA esta cerrado → ``ValueError: I/O operation on closed file``.
Ese ruido de teardown destruye/oculta la linea resumen final de pytest
(``N passed, M failed``), obligando a parsear la salida a mano.

Solucion: en ``pytest_unconfigure`` (que corre ANTES de los hooks atexit)
desactivamos esos loggers para que el cierre de httpx no emita nada.
"""

from __future__ import annotations

import logging

_NOISY_EXIT_LOGGERS = ("httpx", "httpcore", "huggingface_hub")


def pytest_unconfigure(config) -> None:  # noqa: ANN001
    try:
        for name in _NOISY_EXIT_LOGGERS:
            lg = logging.getLogger(name)
            lg.handlers = []
            lg.propagate = False
            lg.disabled = True
        logging.raiseExceptions = False
    except Exception:
        pass
