import pytest
import asyncio
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def mock_redis():
    from unittest.mock import AsyncMock
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock(return_value=True)
    return redis_mock


@pytest.fixture
def mock_orchestrator():
    from unittest.mock import Mock
    orc = Mock()
    orc.status = "healthy"
    orc.swarm = Mock()
    orc.swarm.agents = []
    return orc


@pytest.fixture
def auth_token(client):
    response = client.post("/api/auth/login", json={
        "username": "test_user",
        "password": "test_pass",
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    return None

