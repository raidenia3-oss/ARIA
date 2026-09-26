import asyncio
import json
import os
from typing import Any, Dict, List, Optional

from .base import ConnectorBase


class TwitterApiConnector(ConnectorBase):
    def __init__(
        self, bearer_token: str = "", consumer_key: str = "", consumer_secret: str = ""
    ) -> None:
        super().__init__("twitter")
        self.bearer_token = bearer_token or os.environ.get("TWITTER_BEARER_TOKEN", "")
        self.consumer_key = consumer_key or os.environ.get("TWITTER_CONSUMER_KEY", "")
        self.consumer_secret = consumer_secret or os.environ.get("TWITTER_CONSUMER_SECRET", "")
        self.base_url = "https://api.twitter.com/2"

    async def verify_connection(self) -> bool:
        return bool(self.bearer_token)

    async def _request(self, method: str, path: str, body: Optional[Dict] = None) -> Dict[str, Any]:
        import urllib.request

        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.bearer_token}")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            self._circuit_open = True
            self._circuit_opened_at = asyncio.get_event_loop().time()
            raise

    async def post_tweet(self, text: str, media_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        async def _do():
            body = {"text": text}
            if media_ids:
                body["media"] = {"media_ids": media_ids}
            return await asyncio.to_thread(self._request, "POST", "/tweets", body)

        return await self.retry_with_exponential_backoff(_do)

    async def get_timeline(self, max_results: int = 20) -> List[Dict[str, Any]]:
        async def _do():
            resp = await asyncio.to_thread(
                self._request,
                "GET",
                f"/users/{self._get_user_id()}/tweets",
                {"max_results": max_results},
            )
            return resp.get("data", [])

        return await self.retry_with_exponential_backoff(_do)

    async def search_tweets(self, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        async def _do():
            resp = await asyncio.to_thread(
                self._request,
                "GET",
                "/tweets/search/recent",
                {"query": query, "max_results": max_results},
            )
            return resp.get("data", [])

        return await self.retry_with_exponential_backoff(_do)

    async def like_tweet(self, tweet_id: str) -> Dict[str, Any]:
        async def _do():
            user_id = await self._get_user_id()
            body = {"target": {"tweet_id": tweet_id}}
            return await asyncio.to_thread(self._request, "POST", f"/users/{user_id}/likes", body)

        return await self.retry_with_exponential_backoff(_do)

    async def follow_user(self, target_user_id: str) -> Dict[str, Any]:
        async def _do():
            user_id = await self._get_user_id()
            body = {"target": {"user_id": target_user_id}}
            return await asyncio.to_thread(
                self._request, "POST", f"/users/{user_id}/following", body
            )

        return await self.retry_with_exponential_backoff(_do)

    async def _get_user_id(self) -> str:
        try:
            resp = await asyncio.to_thread(self._request, "GET", "/users/me")
            return resp.get("data", {}).get("id", "me")
        except Exception:
            return "me"
