"""BLOQUE 79 - REST API tests for Master Dashboard endpoints."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.master_control.master import get_master_orchestrator, reset_master_orchestrator
from backend.master_control.master_routes import router


@pytest.fixture(autouse=True)
def _reset():
    reset_master_orchestrator()
    yield
    reset_master_orchestrator()


@pytest.fixture
def client():
    reset_master_orchestrator()
    orch = get_master_orchestrator()
    orch.register_module("demo", lambda: {"ok": True})
    app = FastAPI(title="AURA Master Test", version="test")
    app.include_router(router)
    with TestClient(app) as c:
        yield c
    reset_master_orchestrator()


def test_status(client):
    r = client.get("/api/orchestrator/master/status")
    assert r.status_code == 200
    assert r.json()["enabled"] is True
    assert r.json()["offline_only"] is True


def test_modules(client):
    r = client.get("/api/orchestrator/master/modules")
    assert r.status_code == 200
    names = [m["name"] for m in r.json()]
    assert "demo" in names and any(m["healthy"] for m in r.json())


def test_module_check(client):
    r = client.post("/api/orchestrator/master/modules/demo/check")
    assert r.status_code == 200
    assert r.json()["healthy"] is True


def test_emit_event(client):
    r = client.post(
        "/api/orchestrator/master/events",
        json={"source": "telemetry", "kind": "beat", "level": "warn"},
    )
    assert r.status_code == 200
    assert r.json()["decision"] == "monitor"


def test_get_events_with_filter(client):
    client.post(
        "/api/orchestrator/master/events", json={"source": "a", "kind": "k", "level": "info"}
    )
    client.post(
        "/api/orchestrator/master/events", json={"source": "a", "kind": "k2", "level": "error"}
    )
    r = client.get("/api/orchestrator/master/events", params={"level": "error"})
    assert r.status_code == 200
    assert len(r.json()) == 1 and r.json()[0]["level"] == "error"


def test_run_pipeline(client):
    r = client.post(
        "/api/orchestrator/master/pipeline",
        json={
            "name": "mission-1",
            "steps": [{"kind": "noop"}, {"kind": "echo", "params": {"x": 1}}],
        },
    )
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "success"
    assert d["steps"][1]["result"] == {"x": 1}


def test_pipelines_list(client):
    client.post(
        "/api/orchestrator/master/pipeline", json={"name": "m1", "steps": [{"kind": "noop"}]}
    )
    r = client.get("/api/orchestrator/master/pipelines")
    assert r.status_code == 200 and len(r.json()) >= 1


def test_run_cycle(client):
    r = client.post("/api/orchestrator/master/cycle")
    assert r.status_code == 200
    assert "unhealthy" in r.json() and "healthy" in r.json()


def test_health(client):
    r = client.get("/api/orchestrator/master/health")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_websocket_status(client):
    with client.websocket_connect("/api/orchestrator/master/ws") as ws:
        ws.send_text("status")
        data = ws.receive_json()
        assert data["enabled"] is True


def test_websocket_cycle(client):
    with client.websocket_connect("/api/orchestrator/master/ws") as ws:
        ws.send_text("cycle")
        data = ws.receive_json()
        assert "unhealthy" in data
