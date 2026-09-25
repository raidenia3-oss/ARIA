import asyncio
import json
import os
from typing import Any, Dict, List, Optional

from .base import ConnectorBase


class DiscordConnector(ConnectorBase):
    def __init__(self, token: str = "") -> None:
        super().__init__("discord")
        self.token = token or os.environ.get("DISCORD_BOT_TOKEN", "")
        self.base_url = "https://discord.com/api/v10"
        self._ws_url: Optional[str] = None

    async def verify_connection(self) -> bool:
        return bool(self.token)

    async def _request(self, method: str, path: str, body: Optional[Dict] = None) -> Dict[str, Any]:
        import urllib.request

        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", self.token)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            self._circuit_open = True
            self._circuit_opened_at = asyncio.get_event_loop().time()
            raise

    async def send_message(
        self, channel_id: str, content: str, embeds: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        async def _do():
            body = {"content": content}
            if embeds:
                body["embeds"] = embeds
            return await asyncio.to_thread(
                self._request, "POST", f"/channels/{channel_id}/messages", body
            )

        return await self.retry_with_exponential_backoff(_do)

    async def create_embed(
        self,
        channel_id: str,
        title: str,
        description: str,
        color: int = 0x5865F2,
        fields: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        async def _do():
            embed = {"title": title, "description": description, "color": color}
            if fields:
                embed["fields"] = fields
            body = {"embeds": [embed]}
            return await asyncio.to_thread(
                self._request, "POST", f"/channels/{channel_id}/messages", body
            )

        return await self.retry_with_exponential_backoff(_do)

    async def upload_to_channel(
        self, channel_id: str, file_path: str, content: str = ""
    ) -> Dict[str, Any]:
        async def _do():
            import os as _os

            if not _os.path.exists(file_path):
                return {"error": "file not found"}
            body = {"content": content}
            return await asyncio.to_thread(
                self._request, "POST", f"/channels/{channel_id}/messages", body
            )

        return await self.retry_with_exponential_backoff(_do)

    async def join_voice(self, guild_id: str, channel_id: str) -> Dict[str, Any]:
        async def _do():
            return await asyncio.to_thread(
                self._request, "POST", f"/channels/{channel_id}/voice-users/@me", {}
            )

        result = await self.retry_with_exponential_backoff(_do)
        return {"joined": True, "guild_id": guild_id, "channel_id": channel_id, **result}

    async def stream_audio(
        self, channel_id: str, audio_source: str, duration: float = 0
    ) -> Dict[str, Any]:
        async def _do():
            body = {"channel_id": channel_id, "audio_source": audio_source}
            if duration > 0:
                body["duration"] = duration
            return await asyncio.to_thread(self._request, "POST", "/voice/stream", body)

        return await self.retry_with_exponential_backoff(_do)
