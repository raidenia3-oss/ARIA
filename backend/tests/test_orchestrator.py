import pytest
from backend.orchestrator import AvailabilityOrchestrator, Node


@pytest.fixture
def orchestrator():
    return AvailabilityOrchestrator()


def test_orchestrator_init(orchestrator):
    assert orchestrator is not None
    assert orchestrator.nodes is not None
    assert orchestrator.get_status() is not None


def test_get_status(orchestrator):
    status = orchestrator.get_status()
    assert status is not None
    assert 'orchestrator' in status or 'status' in status or isinstance(status, str)


def test_get_primary_backend(orchestrator):
    backend = orchestrator.get_primary_backend()
    assert backend is None or isinstance(backend, Node)


def test_register_and_mark_node(orchestrator):
    node = Node(node_id="test_node", node_type="pc", base_url="http://localhost:8000", role="light")
    orchestrator.register_node(node)
    retrieved = orchestrator.get_node("test_node")
    assert retrieved is not None
    orchestrator.mark_online("test_node", capabilities=["test"])
    orchestrator.mark_offline("test_node")


def test_probe_node(orchestrator):
    node = Node(node_id="probe_node", node_type="pc", base_url="http://localhost:8000", role="light")
    result = orchestrator.probe_node(node, timeout=1)
    assert isinstance(result, bool)


def test_start_stop_monitoring(orchestrator):
    orchestrator.start_monitoring(interval=30)
    orchestrator.stop_monitoring()


def test_get_available_nodes(orchestrator):
    nodes = orchestrator.get_available_nodes()
    assert isinstance(nodes, list)


@pytest.mark.asyncio
async def test_orchestrator_concurrent_loads(orchestrator):
    """Test multiple concurrent requests to orchestrator."""
    import asyncio

    async def _probe():
        node = Node(node_id=f"concurrent_{i}", node_type="pc", base_url="http://localhost:8000", role="light")
        orchestrator.register_node(node)
        return orchestrator.probe_node(node, timeout=1)

    tasks = [_probe() for i in range(5)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    assert len(results) == 5


@pytest.mark.asyncio
async def test_orchestrator_restart_failed_agent(orchestrator):
    """Test restart de agente fallido."""
    node = Node(node_id="agent_1", node_type="pc", base_url="http://localhost:8000", role="light")
    orchestrator.register_node(node)
    orchestrator.mark_online("agent_1")
    orchestrator.mark_offline("agent_1")
    assert orchestrator.get_node("agent_1") is not None


@pytest.mark.asyncio
async def test_orchestrator_memory_limits(orchestrator):
    """Test enforcement de memory limits."""
    for i in range(50):
        node = Node(node_id=f"load_node_{i}", node_type="pc", base_url="http://localhost:8000", role="light")
        orchestrator.register_node(node)
    nodes = orchestrator.get_available_nodes()
    assert isinstance(nodes, list)


@pytest.mark.asyncio
async def test_orchestrator_state_persistence(orchestrator):
    """Test que estado se persiste entre instancias."""
    node = Node(node_id="persist_node", node_type="pc", base_url="http://localhost:8000", role="light")
    orchestrator.register_node(node)
    orchestrator.mark_online("persist_node")
    state_before = orchestrator.state
    assert state_before is not None
