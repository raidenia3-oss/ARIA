from __future__ import annotations
from typing import Any, Dict

NAME = "background"
DESCRIPTION = "Fondo personalizado Ambxst: imagen local/galería, URL, gradientes y animaciones"
COMMANDS = ["background pick", "background set", "background anim kenburns|zoom|fade|none", "background clear"]


def handle(command: str, **kwargs) -> Dict[str, Any]:
    cmd = (command or "").strip().lower()
    if "pick" in cmd:
        return {"status": "ui", "action": "AURA_BG_PICK_IMAGE"}
    if "clear" in cmd:
        return {"status": "ui", "action": "AURA_BG_CUSTOM_CLEAR"}
    if "anim" in cmd:
        anim = kwargs.get("anim") or "kenburns"
        return {"status": "ui", "action": "AURA_BG_ENHANCE", "args": [{"anim": anim}]}
    if "set" in cmd:
        url = kwargs.get("url") or kwargs.get("src") or kwargs.get("image") or ""
        anim = kwargs.get("anim") or "kenburns"
        if not url: return {"status": "missing", "need": ["url"]}
        return {"status": "ui", "action": "AURA_BG_CUSTOM_SET", "args": [url, {"mode": kwargs.get("mode") or "cover", "anim": anim}]}
    return {"status": "unknown", "commands": COMMANDS}
