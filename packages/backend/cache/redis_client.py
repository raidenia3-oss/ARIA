import asyncio
import json
import logging
from typing import Any, Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class RedisCache:
    def __init__(self, url: str = "redis://localhost:6379/0"):
        self.url = url
        self.client: Optional[redis.Redis] = None

    async def connect(self) -> None:
        try:
            self.client = await redis.from_url(self.url, decode_responses=True)
            await self.client.ping()
            logger.info("Redis conectado")
        except Exception as exc:
            logger.error("Redis connection failed: %s", exc)
            self.client = None

    async def get(self, key: str) -> Optional[Any]:
        if not self.client:
            return None
        try:
            value = await self.client.get(key)
            if value is not None:
                return json.loads(value)
        except Exception as exc:
            logger.error("Redis GET error: %s", exc)
        return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        if not self.client:
            return False
        try:
            await self.client.setex(key, ttl, json.dumps(value))
            return True
        except Exception as exc:
            logger.error("Redis SET error: %s", exc)
            return False

    async def delete(self, key: str) -> bool:
        if not self.client:
            return False
        try:
            await self.client.delete(key)
            return True
        except Exception as exc:
            logger.error("Redis DELETE error: %s", exc)
            return False

    async def publish(self, channel: str, message: dict) -> bool:
        if not self.client:
            return False
        try:
            await self.client.publish(channel, json.dumps(message))
            return True
        except Exception as exc:
            logger.error("Redis PUBLISH error: %s", exc)
            return False

    async def close(self) -> None:
        if self.client:
            await self.client.close()


redis_cache = RedisCache()


async def init_redis() -> None:
    await redis_cache.connect()


async def close_redis() -> None:
    await redis_cache.close()
