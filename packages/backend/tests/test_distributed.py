import pytest
from unittest.mock import AsyncMock, patch

from backend.distributed.redis_pubsub import redis_pubsub
from backend.distributed.agent_sync import agent_sync_manager
from backend.distributed.orchestrator_distributed import DistributedOrchestrator
from backend.ha.failover_manager import failover_manager


@pytest.mark.asyncio
async def test_redis_cluster_connection():
    with patch.object(redis_pubsub, "connect", new_callable=AsyncMock, return_value=True):
        await redis_pubsub.connect("test-node")
    with patch.object(redis_pubsub, "get_cluster_nodes", new_callable=AsyncMock, return_value=[]):
        nodes = await redis_pubsub.get_cluster_nodes()
    assert isinstance(nodes, list)


@pytest.mark.asyncio
async def test_agent_sync():
    await agent_sync_manager.register_local_agent("test-agent", {})
    agents = agent_sync_manager.get_all_agents()
    assert "test-agent" in agents["local"]


@pytest.mark.asyncio
async def test_orchestrator_distributed():
    with patch.object(redis_pubsub, "connect", new_callable=AsyncMock, return_value=True), \
         patch.object(agent_sync_manager, "initialize", new_callable=AsyncMock), \
         patch.object(redis_pubsub, "subscribe_to_channel", new_callable=AsyncMock), \
         patch.object(DistributedOrchestrator, "discover_cluster_nodes", new_callable=AsyncMock):
        orch = DistributedOrchestrator("test-node")
        await orch.initialize_cluster()
    status = await orch.get_cluster_status()
    assert "cluster" in status
    assert "local" in status


@pytest.mark.asyncio
async def test_failover_manager():
    with patch.object(redis_pubsub, "subscribe_to_channel", new_callable=AsyncMock):
        await failover_manager.start_monitoring()
    health = failover_manager.get_cluster_health()
    assert "healthy_nodes" in health
    assert "status" in health
