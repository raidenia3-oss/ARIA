import asyncio
import json
import os
from typing import Any, Dict, List, Optional

from .base import ConnectorBase


class NotionConnector(ConnectorBase):
    def __init__(self, api_key: str = "", base_url: str = "https://api.notion.com/v1") -> None:
        super().__init__("notion")
        self.api_key = api_key or os.environ.get("NOTION_API_KEY", "")
        self.base_url = base_url
        self._cache: Dict[str, Any] = {}

    async def verify_connection(self) -> bool:
        if not self.api_key:
            return False
        return True

    async def _request(self, method: str, path: str, body: Optional[Dict] = None) -> Dict[str, Any]:
        import urllib.request

        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.api_key}")
        req.add_header("Content-Type", "application/json")
        req.add_header("Notion-Version", "2022-06-28")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            self._circuit_open = True
            self._circuit_opened_at = asyncio.get_event_loop().time()
            raise

    async def read_pages(
        self, database_id: str, filter_query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        async def _do():
            body = {"page_size": 100}
            if filter_query:
                body["filter"] = {"property": "title", "title": {"contains": filter_query}}
            resp = await asyncio.to_thread(
                self._request, "POST", f"/databases/{database_id}/query", body
            )
            return resp.get("results", [])

        return await self.retry_with_exponential_backoff(_do)

    async def create_database(self, title: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        async def _do():
            body = {
                "parent": {"type": "workspace", "workspace": True},
                "title": {"title": [{"text": {"content": title}}]},
                "properties": properties,
            }
            return await asyncio.to_thread(self._request, "POST", "/databases", body)

        return await self.retry_with_exponential_backoff(_do)

    async def add_item(self, database_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        async def _do():
            body = {"parent": {"database_id": database_id}, "properties": properties}
            return await asyncio.to_thread(self._request, "POST", "/pages", body)

        return await self.retry_with_exponential_backoff(_do)

    async def query_database(self, database_id: str, **kwargs) -> Dict[str, Any]:
        async def _do():
            return await asyncio.to_thread(
                self._request, "POST", f"/databases/{database_id}/query", kwargs
            )

        return await self.retry_with_exponential_backoff(_do)

    async def update_block(self, block_id: str, content: str) -> Dict[str, Any]:
        async def _do():
            body = {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": content}}]},
            }
            return await asyncio.to_thread(self._request, "PATCH", f"/blocks/{block_id}", body)

        return await self.retry_with_exponential_backoff(_do)

    async def fallback_mechanism(self, operation: str, **kwargs) -> Dict[str, Any]:
        return {
            "fallback": True,
            "connector": "notion",
            "operation": operation,
            "data": self._cache,
        }
