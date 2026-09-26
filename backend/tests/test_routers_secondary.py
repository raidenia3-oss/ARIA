"""Tests for secondary API routers."""

from __future__ import annotations

import base64
from PIL import Image
import io

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client():
    from backend.main import app
    from backend.middleware import rate_limiter as rl_module
    import asyncio
    original_check = rl_module.rate_limiter.check_rate_limit
    async def always_allow(client_id):
        return True
    rl_module.rate_limiter.check_rate_limit = always_allow
    try:
        from fastapi.testclient import TestClient
        yield TestClient(app)
    finally:
        rl_module.rate_limiter.check_rate_limit = original_check


class TestVisionRouter:
    def test_analyze_frame_missing_image(self, client):
        response = client.post("/vision/analyze-frame", json={})
        assert response.status_code == 422

    def test_analyze_frame_valid(self, client):
        img = Image.new("RGB", (10, 10), color="red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_b64 = base64.b64encode(buf.getvalue()).decode()

        response = client.post("/vision/analyze-frame", json={"image": img_b64, "session_id": "s1"})
        assert response.status_code == 200
        data = response.json()
        assert "model" in data
        assert "description" in data

    def test_analyze_screenshot_missing_image(self, client):
        response = client.post("/vision/screenshot", json={})
        assert response.status_code == 422

    def test_vision_status(self, client):
        response = client.get("/vision/status")
        assert response.status_code == 200
        data = response.json()
        assert "model" in data


class TestMemoryRouter:
    def test_remember_missing_text(self, client):
        response = client.post("/memory/remember", json={})
        assert response.status_code == 422

    def test_remember_valid(self, client):
        response = client.post("/memory/remember", json={"text": "test memory", "type": "episodic"})
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        assert "memory_id" in data

    def test_search_missing_query(self, client):
        response = client.get("/memory/search")
        assert response.status_code == 422

    def test_search_valid(self, client):
        client.post("/memory/remember", json={"text": "AURA backend testing", "type": "episodic"})
        response = client.get("/memory/search?q=AURA+backend")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        assert "results" in data

    def test_memory_status(self, client):
        response = client.get("/memory/status")
        assert response.status_code == 200
        data = response.json()
        assert "total_memories" in data


class TestActionsRouter:
    def test_list_tools(self, client):
        response = client.get("/actions/tools")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "tools" in data
        assert data["count"] > 0

    def test_execute_missing_tool(self, client):
        response = client.post("/actions/execute", json={})
        assert response.status_code == 400

    def test_execute_unknown_tool(self, client):
        response = client.post("/actions/execute", json={"tool": "nonexistent_tool"})
        assert response.status_code == 400
        data = response.json()
        assert data.get("success") is False

    def test_actions_status(self, client):
        response = client.get("/actions/status")
        assert response.status_code == 200
        data = response.json()
        assert "tool_count" in data


class TestWebRTCRouter:
    def test_audio_process_missing_session(self, client):
        response = client.post("/webrtc/audio/process", json={})
        assert response.status_code in (400, 422)

    def test_tts_speak_missing_text(self, client):
        response = client.post("/webrtc/tts/speak", json={})
        assert response.status_code in (400, 422)

    def test_tts_status(self, client):
        response = client.get("/webrtc/tts/status")
        assert response.status_code == 200

    def test_audio_status(self, client):
        response = client.get("/webrtc/audio/status")
        assert response.status_code == 200


class TestTelemetryRouter:
    def test_websocket_telemetry(self, client):
        with client.websocket_connect("/ws/telemetry") as websocket:
            data = websocket.receive_json()
            assert "timestamp" in data
            assert "cpu_percent" in data
            assert "ram_percent" in data
