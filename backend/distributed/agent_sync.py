"""Agent Synchronization across cluster nodes
Coordina agentes distribuidos vía Redis Pub/Sub
"""

import asyncio
import logging
from typing import Dict, List

from backend.distributed.redis_pubsub import redis_pubsub

logger = logging.getLogger(__name__)


class AgentSyncManager:
    """Sincroniza estado de agentes entre nodos."""

    def __init__(self):
        self.local_agents: Dict[str, dict] = {}
        self.remote_agents: Dict[str, dict] = {}
        self.sync_interval = 5  # segundos

    async def initialize(self, node_id: str):
        """Inicializa sincronización."""
        await redis_pubsub.subscribe_to_channel("agents:status", self.handle_agent_status)

        await redis_pubsub.subscribe_to_channel("agents:command", self.handle_agent_command)

        logger.info("AgentSyncManager iniciado (%s)", node_id)

        asyncio.create_task(self.sync_loop())

    async def register_local_agent(self, agent_id: str, agent_data: dict):
        """Registra agente local."""
        self.local_agents[agent_id] = agent_data

        await redis_pubsub.publish_to_channel("agents:status", {
            "action": "register",
            "agent_id": agent_id,
            "status": "active",
            "capacity": agent_data.get("capacity", 1),
        })

        logger.info("Agente registrado: %s", agent_id)

    async def handle_agent_status(self, message: dict):
        """Maneja updates de estado de agentes."""
        source = message.get("source_node")
        data = message.get("data", {})

        if source == redis_pubsub.node_id:
            return

        agent_id = data.get("agent_id")

        if data.get("action") == "register":
            self.remote_agents[agent_id] = data
            logger.info("Agente remoto registrado: %s", agent_id)

        elif data.get("action") == "unregister":
            self.remote_agents.pop(agent_id, None)
            logger.info("Agente remoto removido: %s", agent_id)

    async def handle_agent_command(self, message: dict):
        """Maneja comandos para agentes."""
        data = message.get("data", {})
        target_agent = data.get("target_agent")

        if target_agent in self.local_agents:
            await self.execute_remote_command(target_agent, data)

    async def execute_remote_command(self, agent_id: str, command: dict):
        """Ejecuta comando remoto en agente local."""
        logger.info("Ejecutando comando remoto en %s: %s", agent_id, command)
        # Implementación específica del agente

    async def sync_loop(self):
        """Sincroniza estado periódicamente."""
        while True:
            try:
                for agent_id, agent_data in self.local_agents.items():
                    await redis_pubsub.publish_to_channel("agents:status", {
                        "action": "heartbeat",
                        "agent_id": agent_id,
                        "status": agent_data.get("status", "active"),
                        "load": agent_data.get("load", 0),
                        "processed": agent_data.get("processed_tasks", 0),
                    })

                await asyncio.sleep(self.sync_interval)
            except Exception as exc:
                logger.error("Sync error: %s", exc)
                await asyncio.sleep(self.sync_interval)

    def get_all_agents(self) -> Dict[str, List[str]]:
        """Retorna todos los agentes (locales + remotos)."""
        return {
            "local": list(self.local_agents.keys()),
            "remote": list(self.remote_agents.keys()),
            "total": len(self.local_agents) + len(self.remote_agents),
        }


# Instancia global
agent_sync_manager = AgentSyncManager()
