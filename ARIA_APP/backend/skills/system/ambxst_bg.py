from __future__ import annotations

from typing import Any, Dict

NAME = "ambxst_bg"
DESCRIPTION = "Personalizar fondo Ambxst con imagen de galería/local o URL + animaciones cortas"
COMMANDS = ["bg pick", "bg set", "bg anim", "bg clear", "bg enhance"]


def handle(command: str, **kwargs) -> Dict[str, Any]:
    cmd = (command or "").strip().lower()
    if cmd.startswith("pick"):
        return {"status": "ui", "action": "AURA_BG_PICK_IMAGE", "msg": "Abre selector de archivos para elegir imagen"}
    if cmd.startswith("set"):
        url = kwargs.get("url") or kwargs.get("image") or ""
        mode = kwargs.get("mode") or "cover"
        anim = kwargs.get("anim") or "kenburns"
        if not url:
            return {"status": "missing", "need": ["url"]}
        return {"status": "ui", "action": "AURA_BG_CUSTOM_SET", "args": [url, {"mode": mode, "anim": anim}]}
    if cmd.startswith("anim"):
        anim = kwargs.get("anim") or "kenburns"
        cur = kwargs.get("current") or ""
        return {"status": "ui", "action": "AURA_BG_ENHANCE", "args": [{"anim": anim}]}
    if cmd.startswith("clear"):
        return {"status": "ui", "action": "AURA_BG_CUSTOM_CLEAR", "args": []}
    if cmd.startswith("enhance"):
        anim = kwargs.get("anim") or "kenburns"
        return {"status": "ui", "action": "AURA_BG_ENHANCE", "args": [{"anim": anim}]}
    return {"status": "unknown", "commands": COMMANDS}
