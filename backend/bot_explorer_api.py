from __future__ import annotations

from typing import Any, Dict

try:
    from backend.explorer.explorer_api import explorer_manager
    from backend.bot_integration import bot_integration
except Exception:
    explorer_manager = None
    bot_integration = None


def handle_bot_explorer(cmd: str, **kwargs) -> Dict[str, Any]:
    c = (cmd or "").strip().lower()
    if explorer_manager is None and bot_integration is None:
        return {"status": "error", "error": "explorer_unavailable"}
    if c.startswith("create"):
        name = kwargs.get("name") or "explorer"
        if bot_integration and hasattr(bot_integration, "create_explorer"):
            return bot_integration.create_explorer(name=name)
        if explorer_manager:
            return explorer_manager.create_explorer(name=name)
    if c.startswith("spawn"):
        name = kwargs.get("name") or "explorer_swarm"
        if bot_integration and hasattr(bot_integration, "create_explorer"):
            return bot_integration.create_explorer(name=name)
        if explorer_manager:
            return explorer_manager.create_explorer(name=name)
    if c.startswith("fetch"):
        bid = kwargs.get("bot_id") or kwargs.get("id")
        url = kwargs.get("url") or ""
        if explorer_manager and bid:
            return explorer_manager.fetch(bid, url)
    if c.startswith("search"):
        bid = kwargs.get("bot_id") or kwargs.get("id")
        q = kwargs.get("q") or kwargs.get("query") or ""
        if explorer_manager and bid:
            return explorer_manager.search(bid, q)
    if c.startswith("explore"):
        bid = kwargs.get("bot_id") or kwargs.get("id")
        topic = kwargs.get("topic") or ""
        if explorer_manager and bid:
            return explorer_manager.explore(bid, topic)
    return {"status": "unknown_command", "hint": "bot:explorer create|fetch|search|explore"}
