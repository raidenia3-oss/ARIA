"""High Availability - Failover automatico entre nodos
"""

import asyncio
import logging
from typing import Dict, Optional

from backend.distributed.redis_pubsub import redis_pubsub

logger = logging.getLogger(__name__)


class FailoverManager:
    """Gestiona failover automático de nodos."""

    def __init__(self):
        self.heartbeat_timeout = 30  # segundos
        self.node_status: Dict[str, str] = {}
        self.failover_in_progress = False

    async def start_monitoring(self):
        """Inicia monitoreo de salud de nodos."""
        asyncio.create_task(self._monitor_nodes())

        await redis_pubsub.subscribe_to_channel(
            "cluster:failover",
            self.handle_failover_event,
        )

        logger.info("FailoverManager iniciado")

    async def _monitor_nodes(self):
        """Monitorea heartbeat de nodos."""
        while True:
            try:
                nodes = await redis_pubsub.get_cluster_nodes()

                for node in nodes:
                    heartbeat = await redis_pubsub.client.get(
                        f"node:{node}:heartbeat"
                    )

                    if heartbeat:
                        self.node_status[node] = "healthy"
                    else:
                        self.node_status[node] = "dead"
                        logger.warning("Nodo muerto: %s", node)

                        await self.trigger_failover(node)

                await asyncio.sleep(10)
            except Exception as exc:
                logger.error("Monitoring error: %s", exc)
                await asyncio.sleep(10)

    async def trigger_failover(self, failed_node: str):
        """Inicia failover de nodo muerto."""
        if self.failover_in_progress:
            return

        self.failover_in_progress = True

        try:
            logger.error("FAILOVER INICIADO: %s", failed_node)

            backup_node = None
            for node, status in self.node_status.items():
                if node != failed_node and status == "healthy":
                    backup_node = node
                    break

            if not backup_node:
                logger.error(
                    "No backup nodes disponibles para %s", failed_node
                )
                self.failover_in_progress = False
                return

            await redis_pubsub.broadcast_to_cluster("cluster:failover", {
                "failed_node": failed_node,
                "backup_node": backup_node,
                "action": "takeover",
            })

            await asyncio.sleep(5)

            logger.info("FAILOVER COMPLETADO: %s -> %s", failed_node, backup_node)

        finally:
            self.failover_in_progress = False

    async def handle_failover_event(self, message: dict):
        """Maneja evento de failover."""
        data = message.get("data", {})
        failed_node = data.get("failed_node")
        backup_node = data.get("backup_node")

        logger.info(
            "Failover event: %s -> %s", failed_node, backup_node
        )

        self.node_status[failed_node] = "dead"
        self.node_status[backup_node] = "backup_active"

    def get_cluster_health(self) -> Dict:
        """Retorna salud del cluster."""
        healthy = sum(1 for s in self.node_status.values() if s == "healthy")
        dead = sum(1 for s in self.node_status.values() if s == "dead")

        return {
            "healthy_nodes": healthy,
            "dead_nodes": dead,
            "total_nodes": len(self.node_status),
            "failover_in_progress": self.failover_in_progress,
            "status": "healthy" if healthy > 0 else "degraded",
        }


# Instancia global
failover_manager = FailoverManager()
