"""WebSocket Gateway /api/ws/stream integration tests.

Validates:
- Auth via first-message JSON
- Broadcast of canon_event and character_update to subscribed clients
- Ping/pong keep-alive
- Concurrent message delivery to multiple clients
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client() -> TestClient:
    from backend.main import app

    return TestClient(app)


class TestWSStreamGateway:
    """Tests for the /api/ws/stream WebSocket gateway."""

    def test_ws_stream_accepts_auth_and_receives_pong(self, client: TestClient):
        with client.websocket_connect("/api/ws/stream") as ws:
            ws.send_json({"type": "auth", "token": "test", "deviceId": "test-dev"})
            resp = ws.receive_json()
            assert resp["status"] == "ok"
            assert resp.get("auth") == "accepted"

    def test_ws_stream_ignores_unknown_message_type(self, client: TestClient):
        """El gateway ignora mensajes con type desconocido sin cerrar la conexión."""
        with client.websocket_connect("/api/ws/stream") as ws:
            ws.send_json({"type": "auth", "token": "test", "deviceId": "test-dev"})
            ws.receive_json()
            ws.send_json({"type": "unknown_action", "data": {}})
            ws.send_json({"type": "ping"})
            resp = ws.receive_json()
            assert resp["type"] == "pong"

    def test_ws_stream_ping_returns_pong(self, client: TestClient):
        with client.websocket_connect("/api/ws/stream") as ws:
            ws.send_json({"type": "auth", "token": "test", "deviceId": "test-dev"})
            ws.receive_json()
            ws.send_json({"type": "ping"})
            resp = ws.receive_json()
            assert resp["type"] == "pong"

    def test_ws_stream_broadcast_delivers_canon_event(self):
        """Verifica que un evento canónico transmitido llega al AME suscrito.

        Usa el gateway directamente con mocks para simular clientes conectados.
        """
        import asyncio

        from backend.websocket_manager import ws_gateway

        work_id = "test_ws_canon_work"
        mock_client = MagicMock()
        mock_client.send = AsyncMock()
        ws_gateway.add_connection(mock_client)
        ws_gateway.subscribe(mock_client, work_id)

        async def _do_broadcast():
            return await ws_gateway.broadcast(
                "canon_event",
                {
                    "work_id": work_id,
                    "description": "El heroe cruza el umbral",
                    "source": "test",
                    "event_id": "evt_test_123",
                },
                work_id=work_id,
            )

        sent = asyncio.run(_do_broadcast())

        assert sent == 1
        mock_client.send.assert_awaited_once()
        call_args = mock_client.send.call_args
        sent_msg = json.loads(call_args[0][0])
        assert sent_msg["type"] == "canon_event"
        assert sent_msg["payload"]["work_id"] == work_id
        assert "El heroe cruza el umbral" in sent_msg["payload"]["description"]

        ws_gateway.remove_connection(mock_client)

    def test_ws_gateway_broadcast_to_mock_clients(self):
        """Verifica entrega concurrente a múltiples clientes simulados (mocks)."""
        import asyncio

        from backend.websocket_manager import ws_gateway

        work_id = f"test_concurrent_{uuid.uuid4().hex[:8]}"

        mocks = []
        for _ in range(3):
            m = MagicMock()
            m.send = AsyncMock()
            mocks.append(m)
            ws_gateway.add_connection(m, work_id)

        sent = asyncio.run(
            ws_gateway.broadcast(
                "canon_event",
                {
                    "work_id": work_id,
                    "description": "Evento concurrente",
                    "source": "test",
                },
                work_id=work_id,
            )
        )

        assert sent == 3
        for m in mocks:
            m.send.assert_awaited()
            ws_gateway.remove_connection(m)

    def test_ws_gateway_subscribe_unsubscribe(self):
        """Verifica que subscribe filtera eventos por work_id."""
        import asyncio

        from backend.websocket_manager import ws_gateway

        work_a = f"work_a_{uuid.uuid4().hex[:8]}"
        work_b = f"work_b_{uuid.uuid4().hex[:8]}"

        client_a = MagicMock()
        client_a.send = AsyncMock()
        client_b = MagicMock()
        client_b.send = AsyncMock()

        ws_gateway.add_connection(client_a)
        ws_gateway.add_connection(client_b)
        ws_gateway.subscribe(client_a, work_a)
        ws_gateway.subscribe(client_b, work_b)

        sent_a = asyncio.run(ws_gateway.broadcast("test_event", {"msg": "hello"}, work_id=work_a))
        sent_b = asyncio.run(ws_gateway.broadcast("test_event", {"msg": "hello"}, work_id=work_b))

        assert sent_a == 1
        assert sent_b == 1

        client_a.send = AsyncMock()
        client_b.send = AsyncMock()
        ws_gateway.unsubscribe(client_a, work_a)

        sent_after = asyncio.run(
            ws_gateway.broadcast("test_event", {"msg": "hello"}, work_id=work_a)
        )
        assert sent_after == 0

        ws_gateway.remove_connection(client_a)
        ws_gateway.remove_connection(client_b)
