from __future__ import annotations

import os
from typing import Any, Dict

from .client import DiscordManager

_manager: DiscordManager | None = None


def _get_manager() -> DiscordManager:
    global _manager
    if _manager is None:
        _manager = DiscordManager()
    return _manager


def _token() -> str | None:
    for env in ("DISCORD_BOT_TOKEN",):
        v = os.environ.get(env)
        if v:
            return v
    return None


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    action = params.get("action", "")

    if action == "connect":
        return _connect(params)
    if action == "disconnect":
        return _disconnect(params)
    if action == "status":
        return _status(params)
    if action == "guilds":
        return _guilds(params)
    if action == "channels":
        return _channels(params)
    if action == "send":
        return _send(params)
    if action == "read":
        return _read(params)
    return {"error": f"accion desconocida: {action}"}


def _connect(params: Dict[str, Any]) -> Dict[str, Any]:
    token = params.get("token") or _token()
    if not token:
        return {"error": "DISCORD_BOT_TOKEN no configurado"}
    return _get_manager().start(token)


def _disconnect(params: Dict[str, Any]) -> Dict[str, Any]:
    return _get_manager().stop()


def _status(params: Dict[str, Any]) -> Dict[str, Any]:
    return _get_manager().status()


def _guilds(params: Dict[str, Any]) -> Dict[str, Any]:
    return _get_manager().guilds()


def _channels(params: Dict[str, Any]) -> Dict[str, Any]:
    guild_id = int(params.get("guild_id", 0))
    if not guild_id:
        return {"error": "guild_id requerido"}
    return _get_manager().channels(guild_id)


def _send(params: Dict[str, Any]) -> Dict[str, Any]:
    channel_id = int(params.get("channel_id", 0))
    content = params.get("content", "")
    if not channel_id or not content:
        return {"error": "channel_id y content requeridos"}
    return _get_manager().send_message(channel_id, content)


def _read(params: Dict[str, Any]) -> Dict[str, Any]:
    channel_id = int(params.get("channel_id", 0))
    limit = int(params.get("limit", 20))
    if not channel_id:
        return {"error": "channel_id requerido"}
    return _get_manager().read_messages(channel_id, limit)
