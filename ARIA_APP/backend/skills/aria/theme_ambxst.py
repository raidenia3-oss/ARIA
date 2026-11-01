from __future__ import annotations
from typing import Any, Dict

NAME = "theme_ambxst"
DESCRIPTION = "Cambiar entre temas Ambxst (ambxst-dark/ambxst-light)"
COMMANDS = ["theme ambxst dark", "theme ambxst light"]


def handle(command: str, **kwargs) -> Dict[str, Any]:
    cmd = (command or "").strip().lower()
    if "dark" in cmd:
        return {"status": "ui", "action": "set_theme", "args": ["ambxst-dark"]}
    if "light" in cmd:
        return {"status": "ui", "action": "set_theme", "args": ["ambxst-light"]}
    return {"status": "unknown", "commands": COMMANDS}
