"""Distributed metrics collection from all cluster nodes
"""

import asyncio
import logging
from typing import Dict, List

from prometheus_client import Gauge, Counter

from backend.distributed.redis_pubsub import redis_pubsub

logger = logging.getLogger(__name__)

# Métricas globales (aplican a todo el cluster)
cluster_agents_total = Gauge(
    "aura_cluster_agents_total",
    "Total agents across all nodes",
    ["node_id"],
)

cluster_nodes_count = Gauge(
    "aura_cluster_nodes_count",
    "Number of active nodes in cluster",
)

cluster_request_latency = Gauge(
    "aura_cluster_request_latency_ms",
    "Request latency between nodes",
    ["source_node", "target_node"],
)

cluster_failover_total = Counter(
    "aura_cluster_failover_total",
    "Total failover events",
    ["failed_node", "backup_node"],
)


class DistributedMetricsCollector:
    """Colecta métricas de todos los nodos."""

    def __init__(self):
        self.node_metrics: Dict[str, dict] = {}
        self.collection_interval = 5

    async def collect_metrics_from_cluster(self):
        """Colecta métricas periódicamente de todos los nodos."""
        while True:
            try:
                nodes = await redis_pubsub.get_cluster_nodes()

                await redis_pubsub.broadcast_to_cluster("metrics:request", {
                    "action": "collect"
                })

                await asyncio.sleep(self.collection_interval)

                self._aggregate_metrics()

            except Exception as exc:
                logger.error("Collection error: %s", exc)
                await asyncio.sleep(self.collection_interval)

    async def handle_metrics_response(self, message: dict):
        """Maneja respuesta de métricas de nodo."""
        source_node = message.get("source_node")
        data = message.get("data", {})

        self.node_metrics[source_node] = {
            "cpu": data.get("cpu"),
            "memory": data.get("memory"),
            "disk": data.get("disk"),
            "agents": data.get("agents"),
            "timestamp": data.get("timestamp"),
        }

        logger.debug("Metricas de %s: %s", source_node, data)

    def _aggregate_metrics(self):
        """Agrega métricas de todos los nodos."""
        total_agents = 0

        for node_id, metrics in self.node_metrics.items():
            if metrics:
                agents = metrics.get("agents", 0)
                total_agents += agents

                cluster_agents_total.labels(node_id=node_id).set(agents)

        cluster_nodes_count.set(len(self.node_metrics))


# Instancia global
distributed_metrics_collector = DistributedMetricsCollector()
