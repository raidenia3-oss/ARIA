"""Distributed Orchestrator para cluster AURA
Coordina trabajo entre múltiples nodos
"""

import asyncio
import logging
from typing import Dict, List, Optional

from backend.orchestrator import AvailabilityOrchestrator
from backend.distributed.redis_pubsub import redis_pubsub
from backend.distributed.agent_sync import agent_sync_manager

logger = logging.getLogger(__name__)


class DistributedOrchestrator(AvailabilityOrchestrator):
    """Extiende AvailabilityOrchestrator para operación distribuida."""

    def __init__(self, node_id: str):
        super().__init__()
        self.node_id = node_id
        self.cluster_nodes: Dict[str, dict] = {}
        self.distributed = True

    async def initialize_cluster(self):
        """Inicializa coordinación de cluster."""
        await redis_pubsub.connect(self.node_id)

        await agent_sync_manager.initialize(self.node_id)

        await redis_pubsub.subscribe_to_channel(
            "orchestrator:commands",
            self.handle_orchestrator_command,
        )

        await self.discover_cluster_nodes()

        logger.info("Orquestador distribuido iniciado (%s)", self.node_id)

    async def discover_cluster_nodes(self):
        """Descubre nodos en cluster."""
        while True:
            try:
                nodes = await redis_pubsub.get_cluster_nodes()
                self.cluster_nodes = {node: {"status": "active"} for node in nodes}

                logger.info("Cluster nodes: %s", list(self.cluster_nodes.keys()))

                await asyncio.sleep(10)
            except Exception as exc:
                logger.error("Discovery error: %s", exc)
                await asyncio.sleep(10)

    async def allocate_resources_distributed(
        self,
        agent_count: int,
        memory_gb: int,
        cpu_percent: int,
    ) -> Dict:
        """Asigna recursos distribuidos entre nodos."""

        nodes = await redis_pubsub.get_cluster_nodes()

        if not nodes:
            logger.warning("No cluster nodes available")
            return await self.allocate_resources(agent_count, memory_gb, cpu_percent)

        agents_per_node = agent_count // len(nodes)
        remainder = agent_count % len(nodes)

        allocations = {}

        for i, node in enumerate(nodes):
            agents = agents_per_node + (1 if i < remainder else 0)

            allocations[node] = {
                "agents": agents,
                "memory_gb": memory_gb // len(nodes),
                "cpu_percent": cpu_percent // len(nodes),
                "status": "pending",
            }

            await redis_pubsub.publish_to_channel("orchestrator:commands", {
                "action": "allocate",
                "target_node": node,
                "agents": agents,
                "memory_gb": memory_gb // len(nodes),
                "cpu_percent": cpu_percent // len(nodes),
            })

        logger.info("Recursos distribuidos: %s", allocations)

        return {
            "distributed": True,
            "allocations": allocations,
            "total_agents": agent_count,
        }

    async def handle_orchestrator_command(self, message: dict):
        """Maneja comandos del orquestador distribuido."""
        source = message.get("source_node")

        if source == self.node_id:
            return

        data = message.get("data", {})
        action = data.get("action")

        if action == "allocate":
            result = await self.allocate_resources(
                data.get("agents", 0),
                data.get("memory_gb", 0),
                data.get("cpu_percent", 0),
            )

            logger.info("Asignación ejecutada: %s", result)

        elif action == "status":
            status = {
                "node_id": self.node_id,
                "agents_active": len(getattr(self, "swarm", {}).get("agents", [])),
                "uptime": getattr(self, "uptime", 0),
                "health": "healthy",
            }

            await redis_pubsub.publish_to_channel("orchestrator:status", status)

    async def get_cluster_status(self) -> Dict:
        """Retorna estado de todo el cluster."""
        status = {
            "cluster": {
                "nodes": list(self.cluster_nodes.keys()),
                "node_count": len(self.cluster_nodes),
                "status": "healthy" if self.cluster_nodes else "degraded",
            },
            "local": {
                "node_id": self.node_id,
                "agents": len(getattr(self, "swarm", {}).get("agents", [])),
                "uptime": getattr(self, "uptime", 0),
            },
            "remote_agents": agent_sync_manager.get_all_agents(),
        }

        return status

    async def failover_to_node(self, failed_node: str, backup_node: str) -> bool:
        """Realiza failover de un nodo a otro."""
        logger.warning("Failover: %s -> %s", failed_node, backup_node)

        await redis_pubsub.broadcast_to_cluster("cluster:failover", {
            "failed_node": failed_node,
            "backup_node": backup_node,
            "action": "takeover",
        })

        return True


# Instancia global (se inicializa en main.py)
distributed_orchestrator = None
