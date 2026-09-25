import asyncio
import json
import os
from typing import Any, Dict, List, Optional

from .base import ConnectorBase


class SlackConnector(ConnectorBase):
    def __init__(self, token: str = "", base_url: str = "https://slack.com/api") -> None:
        super().__init__("slack")
        self.token = token or os.environ.get("SLACK_BOT_TOKEN", "")
        self.base_url = base_url
        self._webhooks: Dict[str, str] = {}

    async def verify_connection(self) -> bool:
        return bool(self.token)

    async def _request(self, method: str, path: str, body: Optional[Dict] = None) -> Dict[str, Any]:
        import urllib.request

        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            self._circuit_open = True
            self._circuit_opened_at = asyncio.get_event_loop().time()
            raise

    async def send_message(
        self, channel: str, text: str, blocks: Optional[List] = None
    ) -> Dict[str, Any]:
        async def _do():
            body = {"channel": channel, "text": text}
            if blocks:
                body["blocks"] = blocks
            return await asyncio.to_thread(self._request, "POST", "/chat.postMessage", body)

        return await self.retry_with_exponential_backoff(_do)

    async def post_to_channel(
        self, channel: str, text: str, attachments: Optional[List] = None
    ) -> Dict[str, Any]:
        async def _do():
            body = {"channel": channel, "text": text}
            if attachments:
                body["attachments"] = attachments
            return await asyncio.to_thread(self._request, "POST", "/chat.postMessage", body)

        return await self.retry_with_exponential_backoff(_do)

    async def create_thread(self, channel: str, thread_ts: str, text: str) -> Dict[str, Any]:
        async def _do():
            body = {"channel": channel, "ts": thread_ts, "text": text}
            return await asyncio.to_thread(self._request, "POST", "/chat.postMessage", body)

        return await self.retry_with_exponential_backoff(_do)

    async def upload_file(self, channel: str, file_path: str, title: str = "") -> Dict[str, Any]:
        async def _do():
            import os as _os

            if not _os.path.exists(file_path):
                return {"error": "file not found"}
            body = {"channels": channel, "title": title or _os.path.basename(file_path)}
            return await asyncio.to_thread(self._request, "POST", "/files.upload", body)

        return await self.retry_with_exponential_backoff(_do)

    async def set_status(self, emoji: str, text: str) -> Dict[str, Any]:
        async def _do():
            body = {"status_emoji": emoji, "status_text": text}
            return await asyncio.to_thread(self._request, "POST", "/users.profile.set", body)

        return await self.retry_with_exponential_backoff(_do)
