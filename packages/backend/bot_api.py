"""
API helpers para gestión de bots (Grook) desde ARIA/Brain.
"""
from __future__ import annotations

from typing import Any, Dict
from backend.bot_integration import bot_integration


def handle_bot_command(cmd: str, **kwargs) -> Dict[str, Any]:
    c = (cmd or "").strip().lower()
    if c == "list":
        return bot_integration.bot_manager.list_bots()
    if c == "create":
        name = kwargs.get("name") or "grook"
        return bot_integration.create_grook(name, config=kwargs.get("config"))
    if c == "start":
        bid = kwargs.get("bot_id")
        return bot_integration.start(bid) if bid else {"status": "missing_bot_id"}
    if c == "stop":
        bid = kwargs.get("bot_id")
        return bot_integration.stop(bid) if bid else {"status": "missing_bot_id"}
    if c == "tick":
        return bot_integration.tick_all()
    if c == "chat":
        bid = kwargs.get("bot_id")
        msg = kwargs.get("msg") or ""
        return bot_integration.chat(bid, msg) if bid else {"status": "missing_bot_id"}
    return {"status": "unknown_command", "command": cmd}
