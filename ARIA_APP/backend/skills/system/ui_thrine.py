from __future__ import annotations
from typing import Any, Dict

NAME = "ui_thrine"
DESCRIPTION = "Aplicar UI estilo Thrine (punteado + paneles limpios)"
COMMANDS = ["ui thrine apply", "ui thrine toggle"]


def handle(command: str, **kwargs) -> Dict[str, Any]:
    return {"status": "ui", "action": "set_theme", "args": ["thrine"]}
