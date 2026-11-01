from __future__ import annotations

from typing import Any, Dict

from .tray import run as tray_run
from .hotkeys import run as hotkeys_run


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    domain = params.get("domain", "tray")
    inner = dict(params)
    inner.pop("domain", None)
    if domain == "tray":
        return tray_run(inner)
    if domain == "hotkeys":
        return hotkeys_run(inner)
    return {"error": f"dominio desconocido: {domain}"}
