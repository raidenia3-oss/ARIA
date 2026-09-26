"""AURA Local Custom Skill Modules (Bloque 56) - ejecutados 100%% en local.

Cada modulo define un dict ``TOOLS`` donde cada entrada sigue el contrato:
{
  "group.tool_name": {
    "description": str,
    "parameters": { "type": "object", "properties": {...}, "required": [...] },
    "category": str,      # opcional
    "risk": "safe",       # opcional
    "func": callable,       # def run(**params) o async def run(**params)
  },
}
"""

import importlib.util
import pathlib

_TOOLS_DIR = pathlib.Path(__file__).parent


def discover_modules():
    """Lista los nombres de modulos de habilidades locales disponibles."""
    names = []
    for f in sorted(_TOOLS_DIR.glob("*.py")):
        if f.name.startswith("_") or f.name == "__init__.py":
            continue
        names.append(f.stem)
    return names
