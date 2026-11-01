from __future__ import annotations

import os
from typing import Any, Dict

try:
    from backend.explorer.explorer_api import explorer_manager
except Exception:
    explorer_manager = None


NAME = "aria_explorer"
DESCRIPTION = "Módulo especial ARIA: bots exploradores outbound-only para acceso a internet (sin servidor HTTP)"
COMMANDS = ["aria_explorer spawn", "aria_explorer explore", "aria_explorer fetch", "aria_explorer search"]


def handle(command: str, **kwargs) -> Dict[str, Any]:
    cmd = (command or "").strip().lower()
    if explorer_manager is None:
        return {"status": "error", "error": "explorer_not_available"}
    if cmd.startswith("spawn"):
        name = kwargs.get("name") or "aria_explorer"
        return explorer_manager.create_explorer(name=name)
    if cmd.startswith("fetch"):
        bid = kwargs.get("bot_id") or kwargs.get("id")
        url = kwargs.get("url") or ""
        if not bid or not url:
            return {"status": "missing", "need": ["bot_id", "url"]}
        return explorer_manager.fetch(bid, url)
    if cmd.startswith("search"):
        bid = kwargs.get("bot_id") or kwargs.get("id")
        q = kwargs.get("q") or kwargs.get("query") or ""
        if not bid or not q:
            return {"status": "missing", "need": ["bot_id", "q"]}
        return explorer_manager.search(bid, q)
    if cmd.startswith("explore"):
        bid = kwargs.get("bot_id") or kwargs.get("id")
        topic = kwargs.get("topic") or ""
        if not bid or not topic:
            return {"status": "missing", "need": ["bot_id", "topic"]}
        return explorer_manager.explore(bid, topic)
    return {"status": "unknown", "commands": COMMANDS}
