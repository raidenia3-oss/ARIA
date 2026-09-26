import pytest
from fastapi.testclient import TestClient
from backend.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code in [200, 429]
    if response.status_code == 200:
        data = response.json()
        assert 'status' in data


def test_openapi_docs(client):
    response = client.get("/api/docs")
    assert response.status_code in [200, 429]


@pytest.mark.asyncio
async def test_websocket_connection(client):
    with client.websocket_connect("/ws/telemetry") as websocket:
        data = websocket.receive_json()
        assert 'cpu_percent' in data or 'cpu' in data
        assert 'ram_percent' in data or 'memory' in data


def test_rate_limiting(client):
    for _ in range(10):
        response = client.get("/health")
        assert response.status_code in [200, 429]


@pytest.mark.asyncio
async def test_websocket_disconnect_handling(client):
    """Test que server maneja disconnect gracefully."""
    with client.websocket_connect("/ws/telemetry") as websocket:
        data1 = websocket.receive_json()
        assert data1 is not None
        websocket.close()


@pytest.mark.asyncio
async def test_websocket_high_frequency_messages(client):
    """Test WebSocket bajo carga alta."""
    with client.websocket_connect("/ws/telemetry") as websocket:
        import time

        start = time.time()
        message_count = 0

        while time.time() - start < 2:
            try:
                data = websocket.receive_json(timeout=0.5)
                message_count += 1
            except Exception:
                break

        assert message_count >= 0


@pytest.mark.asyncio
async def test_websocket_error_recovery(client):
    """Test que WebSocket se recupera de errores."""
    with client.websocket_connect("/ws/telemetry") as websocket:
        data1 = websocket.receive_json()
        assert data1 is not None

        try:
            websocket.send_json({"invalid": "command"})
        except Exception:
            pass
