from __future__ import annotations

import asyncio
import threading
from typing import Any, Dict, Optional

import discord


class DiscordBot(discord.Client):
    def __init__(self, intents: discord.Intents) -> None:
        super().__init__(intents=intents)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ready = False
        self._token: Optional[str] = None
        self.guilds_cache: Dict[int, Any] = {}
        self.channels_cache: Dict[int, Any] = {}

    async def on_ready(self) -> None:
        self._ready = True
        for g in self.guilds:
            self.guilds_cache[g.id] = g
            for c in g.channels:
                self.channels_cache[c.id] = c
        print(f"[Discord] Conectado como {self.user} ({len(self.guilds)} servidores)")

    async def on_connect(self) -> None:
        self._loop = asyncio.get_running_loop()

    def start(self, token: str) -> None:
        self._token = token
        self._thread = threading.Thread(target=self._run, daemon=True, name="DiscordBot")
        self._thread.start()

    def _run(self) -> None:
        asyncio.run(self.start(self._token))

    def stop(self) -> None:
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.close(), self._loop)
        self._ready = False

    def is_ready(self) -> bool:
        return self._ready and not self.is_closed()

    def _coro(self, coro):
        if not self._loop or not self._loop.is_running():
            raise RuntimeError("Discord loop no esta corriendo")
        return asyncio.run_coroutine_threadsafe(coro, self._loop)


class DiscordManager:
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.guild_messages = True
        self.bot = DiscordBot(intents=intents)
        self._started = False

    def start(self, token: str) -> Dict[str, Any]:
        if self._started:
            return {"status": "already_running"}
        self.bot.start(token)
        self._started = True
        return {"status": "started"}

    def stop(self) -> Dict[str, Any]:
        self.bot.stop()
        self._started = False
        return {"status": "stopped"}

    def status(self) -> Dict[str, Any]:
        return {
            "connected": self.bot.is_ready(),
            "user": str(self.bot.user) if self.bot.user else None,
            "guilds": len(self.bot.guilds_cache),
            "channels": len(self.bot.channels_cache),
        }

    def guilds(self) -> Dict[str, Any]:
        if not self.bot.is_ready():
            return {"error": "bot no conectado"}
        return {
            "guilds": [
                {"id": g.id, "name": g.name, "member_count": g.member_count}
                for g in self.bot.guilds_cache.values()
            ]
        }

    def channels(self, guild_id: int) -> Dict[str, Any]:
        if not self.bot.is_ready():
            return {"error": "bot no conectado"}
        g = self.bot.guilds_cache.get(guild_id)
        if not g:
            return {"error": f"servidor {guild_id} no encontrado"}
        return {
            "guild_id": guild_id,
            "channels": [
                {"id": c.id, "name": c.name, "type": str(c.type)}
                for c in g.channels
            ],
        }

    def send_message(self, channel_id: int, content: str) -> Dict[str, Any]:
        if not self.bot.is_ready():
            return {"error": "bot no conectado"}
        try:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                return {"error": f"canal {channel_id} no encontrado"}
            future = self.bot._coro(channel.send(content))
            msg = future.result(timeout=15)
            return {"status": "ok", "message_id": msg.id, "channel_id": channel_id}
        except Exception as exc:
            return {"error": str(exc)}

    def read_messages(self, channel_id: int, limit: int = 20) -> Dict[str, Any]:
        if not self.bot.is_ready():
            return {"error": "bot no conectado"}
        try:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                return {"error": f"canal {channel_id} no encontrado"}
            future = self.bot._coro(self._fetch_messages(channel, limit))
            messages = future.result(timeout=15)
            return {"channel_id": channel_id, "messages": messages, "count": len(messages)}
        except Exception as exc:
            return {"error": str(exc)}

    async def _fetch_messages(self, channel, limit: int):
        out = []
        async for m in channel.history(limit=limit):
            out.append({
                "id": m.id,
                "author": str(m.author),
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            })
        return out
