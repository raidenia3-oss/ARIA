"""
Mobile endpoints tests.

Validates:
- GET /api/mobile/ames
- GET /api/mobile/ames/{ame_id}/history
- POST /api/mobile/ames/{ame_id}/message
- WebSocket /api/mobile/sync/{client_id} auth (query param + first-message)
"""

from __future__ import annotations

import json
import os
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.database import SessionLocal
from backend.main import app
from backend.models import Message

TEST_API_KEY = "test-mobile-key"


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AURA_API_KEY", TEST_API_KEY)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


class TestMobileAmes:
    """Tests for /api/mobile/ames endpoints."""

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": TEST_API_KEY, "Content-Type": "application/json"}

    def test_list_ames_returns_fallback_when_no_conversations(self, client: TestClient):
        resp = client.get("/api/mobile/ames", headers=self._headers())
        assert resp.status_code == 200
        data = resp.json()
        assert "ames" in data
        assert isinstance(data["ames"], list)
        assert len(data["ames"]) >= 1
        first = data["ames"][0]
        assert "id" in first
        assert "name" in first
        assert "status" in first
        assert "lastActivity" in first
        assert "unreadCount" in first

    def test_list_ames_accepts_api_key(self, client: TestClient):
        resp = client.get("/api/mobile/ames", headers=self._headers())
        assert resp.status_code == 200
        data = resp.json()
        assert "ames" in data

    def test_list_ames_rejects_wrong_api_key(self, client: TestClient):
        resp = client.get("/api/mobile/ames", headers={"X-API-Key": "wrong"})
        assert resp.status_code == 401

    def test_history_empty_for_unknown_ame(self, client: TestClient):
        resp = client.get("/api/mobile/ames/ame_does_not_exist/history", headers=self._headers())
        assert resp.status_code == 200
        data = resp.json()
        assert data["messages"] == []

    def test_message_requires_body(self, client: TestClient):
        resp = client.post("/api/mobile/ames/ame_core/message", headers=self._headers(), json={})
        assert resp.status_code == 400

    def test_message_creates_and_returns_message(self, client: TestClient):
        resp = client.post(
            "/api/mobile/ames/ame_core/message",
            headers=self._headers(),
            json={"message": "hola", "role": "user"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "user"
        assert data["content"] == "hola"
        assert "id" in data
        assert "timestamp" in data

    def test_message_normalizes_invalid_role(self, client: TestClient):
        resp = client.post(
            "/api/mobile/ames/ame_core/message",
            headers=self._headers(),
            json={"message": "test", "role": "invalid"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "user"


class TestMobileWebSocketAuth:
    """WebSocket auth tests without real network."""

    def test_websocket_backend_accepts_first_message_auth(self, client: TestClient):
        with client.websocket_connect("/api/mobile/sync/test-client") as ws:
            ws.send_json({"type": "auth", "token": TEST_API_KEY})
            resp = ws.receive_json()
            assert resp["status"] == "ok"
            assert resp.get("auth") == "accepted"

    def test_websocket_backend_rejects_invalid_token_in_first_message(self, client: TestClient):
        with pytest.raises(Exception):
            with client.websocket_connect("/api/mobile/sync/test-client") as ws:
                ws.send_json({"type": "auth", "token": "wrong-token"})
                ws.receive_json()


class TestChatEndpoint:
    """Tests for /api/chat to ensure AI Router does not raise NameError."""

    def test_chat_returns_200_without_name_error(
        self, client: TestClient, caplog: pytest.LogCaptureFixture
    ):
        caplog.set_level("ERROR")
        resp = client.post(
            "/api/chat",
            headers={"X-API-Key": TEST_API_KEY, "Content-Type": "application/json"},
            json={"prompt": "hola bloque 13"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "text" in data
        assert "_ai_router is not defined" not in resp.text
        for record in caplog.records:
            assert "_ai_router is not defined" not in record.getMessage()


class TestWebSocketChatMessage:
    """Tests for chat_message over WebSocket sync."""

    def test_websocket_chat_message_persists_in_db(self, client: TestClient):
        with client.websocket_connect("/api/mobile/sync/test-ws-chat") as ws:
            ws.send_json({"type": "auth", "token": TEST_API_KEY})
            resp = ws.receive_json()
            assert resp["status"] == "ok"
            assert resp.get("auth") == "accepted"

            ws.send_json(
                {
                    "action": "chat_message",
                    "data": {
                        "ameId": "ame_core",
                        "role": "user",
                        "content": "prueba ws chat",
                        "timestamp": "2026-09-04T19:50:00.000Z",
                    },
                }
            )
            resp = ws.receive_json()
            assert resp["status"] == "ok"
            assert resp["action"] == "chat_message"
            assert resp["data"]["content"] == "prueba ws chat"

        db = SessionLocal()
        try:
            msg = (
                db.query(Message)
                .filter(Message.content == "prueba ws chat")
                .order_by(Message.id.desc())
                .first()
            )
            assert msg is not None
            assert msg.role == "user"
            assert msg.extra is not None
            assert "ws" in msg.extra
        finally:
            db.close()


class TestMobilePairingProfile:
    """Tests for /api/mobile/pairing-profile and /api/mobile/health-check."""

    def test_pairing_profile_returns_local_ips(self, client: TestClient):
        resp = client.get("/api/mobile/pairing-profile")
        assert resp.status_code == 200
        data = resp.json()
        assert "local_ips" in data
        assert isinstance(data["local_ips"], list)
        assert "pairing_token" in data
        assert data["pairing_token_ttl"] == 300
        assert "port" in data

    def test_pairing_profile_token_not_empty(self, client: TestClient):
        resp = client.get("/api/mobile/pairing-profile")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["pairing_token"]) > 0

    def test_health_check_returns_status(self, client: TestClient):
        resp = client.get("/api/mobile/health-check")
        assert resp.status_code == 200
        data = resp.json()
        # El contrato es "ok" + data_source "measured": se midio gethostbyname.
        # Antes devolvia "healthy" con `latency_ms: 0` fijo, y el test validaba
        # esa mentira.
        assert data["status"] == "ok"
        assert data["data_source"] == "measured"
        assert "hostname" in data
        assert "port" in data
        assert isinstance(data["hostname_resolution_ms"], (int, float))
        assert "latency_ms" not in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
