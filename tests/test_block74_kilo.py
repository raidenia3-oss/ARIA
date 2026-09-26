"""REST integration tests for Bloque 74 - Voice Interaction API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.audio.voice import reset_voice_engine
from backend.main import app


@pytest.fixture
def client():
    reset_voice_engine()
    with TestClient(app) as c:
        yield c
    reset_voice_engine()


class TestVoiceStatus:
    def test_status(self, client):
        r = client.get("/api/audio/voice/status")
        assert r.status_code == 200
        body = r.json()
        assert "available" in body
        assert "stt_engine" in body
        assert "tts_engine" in body
        assert "sample_rate" in body


class TestSessionEndpoints:
    def test_create_and_list(self, client):
        r = client.post("/api/audio/voice/sessions", json={"metadata": {"src": "test"}})
        assert r.status_code == 200
        created = r.json()
        assert created["session_id"]
        assert created["metadata"]["src"] == "test"

        r2 = client.get("/api/audio/voice/sessions")
        assert r2.status_code == 200
        body = r2.json()
        assert body["count"] >= 1
        assert any(s["session_id"] == created["session_id"] for s in body["sessions"])

    def test_close_session(self, client):
        r = client.post("/api/audio/voice/sessions", json={})
        sid = r.json()["session_id"]
        r2 = client.post(f"/api/audio/voice/sessions/{sid}/close")
        assert r2.status_code == 200
        assert r2.json()["ok"] is True

    def test_close_missing(self, client):
        r = client.post("/api/audio/voice/sessions/missing-id/close")
        assert r.status_code == 404

    def test_process_missing(self, client):
        r = client.post("/api/audio/voice/sessions/missing-id/process")
        assert r.status_code == 404

    def test_process_empty_session(self, client):
        r = client.post("/api/audio/voice/sessions", json={})
        sid = r.json()["session_id"]
        r2 = client.post(f"/api/audio/voice/sessions/{sid}/process")
        assert r2.status_code == 200
        body = r2.json()
        assert body["ok"] is True
        assert body["reason"] == "empty"

    def test_receive_audio_chunk(self, client):
        r = client.post("/api/audio/voice/sessions", json={})
        sid = r.json()["session_id"]
        import base64

        chunk_b64 = base64.b64encode(b"\x00\x00" * 10).decode()
        r2 = client.post(
            f"/api/audio/voice/sessions/{sid}/audio",
            json={"session_id": sid, "audio_b64": chunk_b64},
        )
        assert r2.status_code == 200
        assert r2.json()["chunks"] == 1

    def test_receive_audio_invalid_b64(self, client):
        r = client.post("/api/audio/voice/sessions", json={})
        sid = r.json()["session_id"]
        r2 = client.post(
            f"/api/audio/voice/sessions/{sid}/audio",
            json={"session_id": sid, "audio_b64": "!!!not-base64!!!"},
        )
        assert r2.status_code == 404 or r2.status_code == 400


class TestWebSocketStream:
    def test_ws_connect_and_ping(self, client):
        with client.websocket_connect("/api/audio/voice/stream") as ws:
            msg = ws.receive_json()
            assert msg["event"] == "connected"
            ws.send_json({"action": "ping"})
            pong = ws.receive_json()
            assert pong["event"] == "pong"

    def test_ws_create_session(self, client):
        with client.websocket_connect("/api/audio/voice/stream") as ws:
            ws.receive_json()  # connected
            ws.send_json({"action": "create", "metadata": {"k": "v"}})
            msg = ws.receive_json()
            assert msg["event"] == "session_created"
            assert msg["session"]["session_id"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
