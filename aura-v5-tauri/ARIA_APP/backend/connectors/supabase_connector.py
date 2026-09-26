import asyncio
import json
import os
from typing import Any, Dict, List, Optional

from .base import ConnectorBase


class SupabaseConnector(ConnectorBase):
    def __init__(self, url: str = "", key: str = "") -> None:
        super().__init__("supabase")
        self.url = url or os.environ.get("SUPABASE_URL", "http://localhost:54321")
        self.key = key or os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")
        self._realtime_subs: Dict[str, Any] = {}

    async def verify_connection(self) -> bool:
        return bool(self.url and self.key)

    async def _request(self, method: str, path: str, body: Optional[Dict] = None) -> Dict[str, Any]:
        import urllib.request

        url = f"{self.url}/rest/v1/{path}"
        data = json.dumps(body).encode("utf-8") if body else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("apikey", self.key)
        req.add_header("Authorization", f"Bearer {self.key}")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read().decode("utf-8")
                return json.loads(content) if content else []
        except Exception as exc:
            self._circuit_open = True
            self._circuit_opened_at = asyncio.get_event_loop().time()
            raise

    async def query(
        self, table: str, filters: Optional[Dict[str, Any]] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        async def _do():
            params = {"limit": limit}
            if filters:
                for k, v in filters.items():
                    params[k] = v
            from urllib.parse import urlencode

            url = f"{self.url}/rest/v1/{table}?{urlencode(params)}"
            import urllib.request

            req = urllib.request.Request(url, method="GET")
            req.add_header("apikey", self.key)
            req.add_header("Authorization", f"Bearer {self.key}")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read().decode("utf-8")
                return json.loads(content) if content else []

        return await self.retry_with_exponential_backoff(_do)

    async def insert(
        self, table: str, data: Dict[str, Any] | List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        async def _do():
            body = data if isinstance(data, list) else [data]
            return await asyncio.to_thread(self._request, "POST", table, body)

        return await self.retry_with_exponential_backoff(_do)

    async def update(
        self, table: str, filters: Dict[str, Any], data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        async def _do():
            body = {"data": data}
            return await asyncio.to_thread(self._request, "PATCH", table, body)

        return await self.retry_with_exponential_backoff(_do)

    async def delete(self, table: str, filters: Dict[str, Any]) -> Dict[str, Any]:
        async def _do():
            return await asyncio.to_thread(self._request, "DELETE", table, filters)

        return await self.retry_with_exponential_backoff(_do)

    async def auth(self, email: str, password: str) -> Dict[str, Any]:
        async def _do():
            import urllib.request

            url = f"{self.url}/auth/v1/token?grant_type=password"
            body = json.dumps({"email": email, "password": password}).encode("utf-8")
            req = urllib.request.Request(url, data=body, method="POST")
            req.add_header("apikey", self.key)
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))

        return await self.retry_with_exponential_backoff(_do)

    async def subscribe_realtime(self, table: str, event: str, callback) -> None:
        self._realtime_subs[f"{table}:{event}"] = {"callback": callback, "active": True}
