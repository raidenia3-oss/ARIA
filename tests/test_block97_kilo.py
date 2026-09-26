"""BLOQUE 97 - REST + WS tests for /api/hud/omni."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.hud.omni_routes import reset_omni_engine, router


@pytest.fixture(autouse=True)
def _clean():
    reset_omni_engine()
    yield
    reset_omni_engine()


@pytest.fixture
def client():
    app = FastAPI(title="AURA Omni HUD Test", version="test")
    app.include_router(router)
    with TestClient(app) as c:
        yield c


def test_status(client):
    r = client.get("/api/hud/omni/status")
    assert r.status_code == 200
    data = r.json()
    assert data["offline_only"] is True
    assert "hud" in data
    assert "synthesizer" in data


def test_snapshot(client):
    r = client.get("/api/hud/omni/snapshot")
    assert r.status_code == 200
    data = r.json()
    assert "hud" in data
    assert "recent_commands" in data
    assert data["offline_only"] is True


def test_ingest_text(client):
    r = client.post(
        "/api/hud/omni/ingest", json={"channel": "text", "text": "hola mundo", "confidence": 0.9}
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["input"]["channel"] == "text"


def test_ingest_hotkey(client):
    r = client.post(
        "/api/hud/omni/ingest", json={"channel": "hotkey", "text": "ctrl+n", "confidence": 1.0}
    )
    assert r.status_code == 200
    assert r.json()["input"]["intent"] == "control"


def test_command(client):
    r = client.post("/api/hud/omni/command", json={"channel": "text", "text": "abre algo"})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_hud_action(client):
    r = client.post(
        "/api/hud/omni/hud/action", json={"action": "mode", "params": {"mode": "minimal"}}
    )
    assert r.status_code == 200
    assert r.json()["state"]["mode"] == "minimal"


def test_hud_alert(client):
    r = client.post(
        "/api/hud/omni/hud/alert", json={"title": "Test", "message": "msg", "severity": "info"}
    )
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_hud_clear_alerts(client):
    client.post("/api/hud/omni/hud/alert", json={"title": "X", "message": "y"})
    r = client.post("/api/hud/omni/hud/clear_alerts", json={})
    assert r.status_code == 200
    assert r.json()["cleared"] >= 1


def test_hud_quick_actions(client):
    r = client.post(
        "/api/hud/omni/hud/quick_actions", json={"actions": [{"id": "a", "label": "A"}]}
    )
    assert r.status_code == 200
    assert r.json()["count"] == 1


def test_commands_list(client):
    client.post("/api/hud/omni/ingest", json={"channel": "text", "text": "hola"})
    r = client.get("/api/hud/omni/commands")
    assert r.status_code == 200
    assert r.json()["count"] >= 1


def test_inputs_list(client):
    client.post("/api/hud/omni/ingest", json={"channel": "text", "text": "hola"})
    r = client.get("/api/hud/omni/inputs")
    assert r.status_code == 200
    assert r.json()["count"] >= 1


def test_reset(client):
    client.post("/api/hud/omni/ingest", json={"channel": "text", "text": "hola"})
    r = client.post("/api/hud/omni/reset", json={})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_channels(client):
    r = client.get("/api/hud/omni/channels")
    assert r.status_code == 200
    data = r.json()
    assert "channels" in data
    assert "voice" in data["channels"]
    assert "text" in data["channels"]


def test_ws_heartbeat(client):
    with client.websocket_connect("/api/hud/omni/ws") as ws:
        msg = ws.receive_json()
        assert "event" in msg or "type" in msg


def test_ws_status_action(client):
    with client.websocket_connect("/api/hud/omni/ws") as ws:
        ws.send_json({"action": "status"})
        msg = ws.receive_json()
        assert isinstance(msg, dict)
