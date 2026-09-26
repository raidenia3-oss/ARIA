"""Redis Pub/Sub for distributed agent coordination
Agents communicate across nodes via Redis channels
"""

import asyncio
import json
import logging
from typing import Callable, Dict, List, Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class RedisPubSub:
    """Redis Pub/Sub coordinator para agentes distribuidos."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self.client = None
        self.pubsub = None
        self.listeners: Dict[str, List[Callable]] = {}
        self.node_id: Optional[str] = None

    async def connect(self, node_id: str):
        """Conecta a Redis y se registra como nodo."""
        try:
            self.node_id = node_id
            self.client = await redis.from_url(self.redis_url, decode_responses=True)
            await self.client.ping()

            await self.client.sadd("cluster:nodes", self.node_id)
            await self.client.expire(f"node:{self.node_id}:heartbeat", 30)

            logger.info("Redis Pub/Sub conectado (node: %s)", self.node_id)

            asyncio.create_task(self._heartbeat_loop())

            return True
        except Exception as exc:
            logger.error("Redis connection failed: %s", exc)
            return False

    async def subscribe_to_channel(self, channel: str, callback: Callable):
        """Suscribe a canal con callback."""
        if channel not in self.listeners:
            self.listeners[channel] = []

        self.listeners[channel].append(callback)
        logger.info("Suscrito a canal: %s", channel)

        if not hasattr(self, f"_listener_{channel}"):
            asyncio.create_task(self._listen_channel(channel))

    async def publish_to_channel(self, channel: str, message: dict) -> bool:
        """Publica mensaje a canal."""
        if not self.client:
            return False

        try:
            payload = {
                "source_node": self.node_id,
                "timestamp": asyncio.get_event_loop().time(),
                "data": message,
            }

            await self.client.publish(channel, json.dumps(payload))
            return True
        except Exception as exc:
            logger.error("Publish error: %s", exc)
            return False

    async def _listen_channel(self, channel: str):
        """Escucha canal y dispara callbacks."""
        try:
            pubsub = self.client.pubsub()
            await pubsub.subscribe(channel)

            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])

                        for callback in self.listeners.get(channel, []):
                            if asyncio.iscoroutinefunction(callback):
                                await callback(data)
                            else:
                                callback(data)
                    except Exception as exc:
                        logger.error("Callback error: %s", exc)

        except Exception as exc:
            logger.error("Listen error for %s: %s", channel, exc)

    async def _heartbeat_loop(self):
        """Heartbeat periódico para detectar nodos down."""
        while True:
            try:
                await self.client.setex(
                    f"node:{self.node_id}:heartbeat",
                    30,
                    json.dumps(
                        {
                            "status": "alive",
                            "timestamp": asyncio.get_event_loop().time(),
                        }
                    ),
                )

                nodes = await self.client.smembers("cluster:nodes")
                for node in nodes:
                    hb = await self.client.get(f"node:{node}:heartbeat")
                    if not hb and node != self.node_id:
                        await self.client.srem("cluster:nodes", node)
                        logger.warning("Nodo removido (dead): %s", node)

                await asyncio.sleep(10)
            except Exception as exc:
                logger.error("Heartbeat error: %s", exc)
                await asyncio.sleep(10)

    async def get_cluster_nodes(self) -> List[str]:
        """Retorna lista de nodos activos en cluster."""
        if not self.client:
            return []

        return list(await self.client.smembers("cluster:nodes"))

    async def broadcast_to_cluster(self, channel: str, message: dict) -> int:
        """Publica a todos los nodos en cluster."""
        return await self.client.publish(
            channel,
            json.dumps(
                {
                    "source_node": self.node_id,
                    "broadcast": True,
                    "data": message,
                }
            ),
        )

    async def close(self):
        """Cierra conexión."""
        if self.client:
            await self.client.srem("cluster:nodes", self.node_id)
            await self.client.close()


# Instancia global
redis_pubsub = RedisPubSub()
