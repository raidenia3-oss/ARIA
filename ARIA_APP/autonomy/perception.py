"""Percepción local de ARIA: lo que ve de verdad, sin depender de nadie.

Nada de aquí abre puertos ni llama a servicios: se le pregunta al sistema
operativo por la ventana que el usuario tiene delante (Windows, vía ctypes) y
se leen los archivos que ARIA ya tiene en su disco. Si un dato no está, no se
inventa: el mundo simplemente no está conectado.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict, List, Optional

#: Tras esto, la consola se considera en silencio.
CONSOLE_IDLE_SECS = 300.0

#: Tras esto, se considera que el usuario no está delante.
USER_IDLE_SECS = 300.0


def foreground_title() -> str:
    """El título de la ventana que el usuario tiene delante.

    Windows lo contesta la API de ventanas. Se pregunta con ctypes: no hay
    proceso externo, no hay comando de shell, no hay red.
    """
    if sys.platform != "win32":
        return ""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.GetWindowTextLengthW.restype = ctypes.c_int
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value.strip()
    except Exception:
        return ""


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, round(float(value), 4)))


def sense_worlds(
    *,
    capabilities: Optional[List[str]] = None,
    memory: Optional[Dict[str, Any]] = None,
    console: Optional[Dict[str, Any]] = None,
    focus: str = "",
) -> List[Dict[str, Any]]:
    """Los mundos que ARIA tiene abiertos ahora mismo.

    Cada mundo es algo real y local: el escritorio donde vive, su memoria en
    disco y la consola donde el usuario habla con ella.
    """
    caps = [str(c) for c in (capabilities or [])]
    mem = memory or {}
    con = console or {}

    memory_ready = bool(mem.get("connected", True))
    console_ready = bool(con.get("connected"))

    return [
        {
            "id": "escritorio",
            "label": "Escritorio",
            "kind": "local",
            "connected": True,
            "status": "en marcha",
            "capabilities": caps,
            "context": {"pid": os.getpid(), "titulo": focus},
            "context_age_secs": 0.0,
            "pending": 0,
        },
        {
            "id": "memoria",
            "label": "Memoria local",
            "kind": "local",
            "connected": memory_ready,
            "status": "en disco" if memory_ready else "sin datos",
            "capabilities": ["conversaciones", "notas", "lecciones"],
            "context": {
                "conversaciones": int(mem.get("conversaciones", 0)),
                "notas": int(mem.get("notas", 0)),
            },
            "context_age_secs": 0.0,
            "pending": 0,
        },
        {
            "id": "consola",
            "label": "Consola",
            "kind": "local",
            "connected": console_ready,
            "status": "escuchando" if console_ready else "en silencio",
            "capabilities": ["chat"],
            "context": {
                "mensajes": int(con.get("mensajes", 0)),
                "ultimo": str(con.get("ultimo", "")),
            },
            "context_age_secs": 0.0 if console_ready else CONSOLE_IDLE_SECS,
            "pending": 0,
        },
    ]


def sense_drives(
    drives: Optional[Dict[str, float]] = None,
    *,
    idle_secs: float = 0.0,
    user_present: bool = False,
    acted: bool = False,
    delta: float = 0.02,
) -> Dict[str, float]:
    """Las pulsiones de ARIA, ajustadas a lo que está pasando de verdad.

    La curiosidad sube cuando nadie le habla y baja cuando actúa; el cuidado
    sube con la presencia del usuario; el dominio sube con lo que consigue.
    """
    current = {k: float(v) for k, v in (drives or {}).items()}
    curiosity = current.get("curiosity", 0.3)
    care = current.get("care", 0.4)
    mastery = current.get("mastery", 0.2)

    if idle_secs > 120:
        curiosity += delta * 2
    else:
        curiosity += delta * 0.2
    if acted:
        curiosity -= delta * 3
    if user_present:
        care += delta * 2
    else:
        care -= delta
    mastery += delta * 0.2 if acted else -delta * 0.1

    return {
        "curiosity": _clamp(curiosity),
        "care": _clamp(care),
        "mastery": _clamp(mastery),
    }


def idle_seconds(last_user_at: float, now: Optional[float] = None) -> float:
    """Cuánto lleva el usuario sin hablar con ARIA."""
    now = now if now is not None else time.time()
    if not last_user_at:
        return 3600.0
    return max(0.0, now - float(last_user_at))
