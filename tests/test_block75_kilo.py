"""BLOQUE 75 - REST integration tests for Overlay endpoints."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def _reset():
    from backend.desktop.overlay import reset_overlay_bridge

    reset_overlay_bridge()
    yield
    reset_overlay_bridge()


@pytest.fixture
def client():
    from backend.desktop.overlay import reset_overlay_bridge

    reset_overlay_bridge()
    app = FastAPI(title="AURA Overlay Test", version="test")
    from backend.desktop.overlay_routes_b75 import router as overlay_router

    app.include_router(overlay_router)
    with TestClient(app) as c:
        yield c
    reset_overlay_bridge()


def test_status(client):
    r = client.get("/api/desktop/overlay/status")
    assert r.status_code == 200
    body = r.json()
    assert "state" in body
    assert "status" in body


def test_set_mode(client):
    r = client.post("/api/desktop/overlay/mode", json={"mode": "compact"})
    assert r.status_code == 200
    assert r.json()["state"]["mode"] == "compact"


def test_set_mode_invalid(client):
    r = client.post("/api/desktop/overlay/mode", json={"mode": "invalid"})
    assert r.status_code == 422


def test_toggle(client):
    r = client.post("/api/desktop/overlay/toggle")
    assert r.status_code == 200
    assert r.json()["state"]["visible"] is True


def test_set_position(client):
    r = client.post(
        "/api/desktop/overlay/position", json={"position": "bottom_left", "x": 10, "y": 20}
    )
    assert r.status_code == 200
    assert r.json()["state"]["position"] == "bottom_left"


def test_set_opacity(client):
    r = client.post("/api/desktop/overlay/opacity", json={"opacity": 0.5})
    assert r.status_code == 200
    assert r.json()["state"]["opacity"] == 0.5


def test_set_context(client):
    r = client.post("/api/desktop/overlay/context", json={"context": "working on code"})
    assert r.status_code == 200
    assert r.json()["state"]["current_context"] == "working on code"


def test_notification(client):
    r = client.post(
        "/api/desktop/overlay/notification",
        json={"title": "Hi", "message": "Hello", "kind": "info"},
    )
    assert r.status_code == 200
    assert r.json()["notification"]["title"] == "Hi"


def test_clear_notifications(client):
    client.post("/api/desktop/overlay/notification", json={"title": "T", "message": "M"})
    r = client.post("/api/desktop/overlay/clear_notifications")
    assert r.status_code == 200
    assert r.json()["cleared"] >= 1


def test_toggle_dnd(client):
    r = client.post("/api/desktop/overlay/dnd")
    assert r.status_code == 200
    assert r.json()["state"]["mode"] == "dnd"


def test_toggle_pin(client):
    r = client.post("/api/desktop/overlay/pin")
    assert r.status_code == 200
    assert r.json()["state"]["pinned"] is True


def test_websocket(client):
    with client.websocket_connect("/api/desktop/overlay/ws") as ws:
        data = ws.receive_json()
        assert data["type"] == "connected"

        ws.send_json({"action": "status"})
        resp = ws.receive_json()
        assert resp["type"] == "status"

        ws.send_json({"action": "toggle"})
        resp = ws.receive_json()
        # Server processes toggle and may broadcast change
        assert resp is not None


def test_websocket_unknown_action(client):
    with client.websocket_connect("/api/desktop/overlay/ws") as ws:
        ws.receive_json()  # connected
        ws.send_json({"action": "unknown"})
        resp = ws.receive_json()
        assert resp["type"] == "error"
