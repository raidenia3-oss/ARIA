from __future__ import annotations
from typing import Any, Dict

NAME = "theme_thrine"
DESCRIPTION = "Activar tema Thrine (clean, grid punteado, paneles con borde interno)"
COMMANDS = ["theme thrine"]


def handle(command: str, **kwargs) -> Dict[str, Any]:
    return {"status": "ui", "action": "set_theme", "args": ["thrine"]}
