"""BLOQUE 84 - REST + WS tests for /api/scheduler/predictive (offline)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.fusion.sensory import get_fusion_engine, reset_fusion_engine
from backend.predictive.intent import get_predictive_engine, reset_predictive_engine
from backend.predictive.predictive_routes import router


@pytest.fixture(autouse=True)
def _reset():
    reset_predictive_engine()
    reset_fusion_engine()
    yield
    reset_predictive_engine()
    reset_fusion_engine()


@pytest.fixture
def client():
    app = FastAPI(title="AURA Predictive Test", version="test")
    app.include_router(router)
    with TestClient(app) as c:
        yield c


def test_status(client):
    r = client.get("/api/scheduler/predictive/status")
    assert r.status_code == 200
    assert r.json()["offline_only"] is True


def test_observe_and_lists(client):
    r = client.post(
        "/api/scheduler/predictive/observe",
        json={"sources": {"memory": 5, "network": 5}, "fused_score": 9.0, "state": "anomaly"},
    )
    assert r.status_code == 200
    assert r.json()["offline_only"] is True
    h = client.get("/api/scheduler/predictive/hypotheses")
    assert h.json()["count"] >= 1
    t = client.get("/api/scheduler/predictive/tasks")
    assert t.json()["count"] >= 1
    lg = client.get("/api/scheduler/predictive/ledger")
    assert lg.json()["count"] >= 1


def test_observe_fusion_bridge(client):
    get_fusion_engine().ingest("memory", "hit", {}, "high")
    get_fusion_engine().ingest("network", "pkt", {}, "high")
    get_fusion_engine().ingest("memory", "hit", {}, "high")
    r = client.post("/api/scheduler/predictive/observe-fusion", json={"window_s": 60.0})
    assert r.status_code == 200
    assert len(r.json()["hypotheses"]) >= 1


def test_confirm_and_reset(client):
    r = client.post(
        "/api/scheduler/predictive/observe",
        json={"sources": {"network": 4, "system": 1}, "fused_score": 2.0, "state": "active"},
    )
    pend = r.json()["pending_confirm"]
    assert pend
    c = client.post(f"/api/scheduler/predictive/confirm/{pend[0]['hypothesis_id']}")
    assert c.json()["confirmed"] is True
    z = client.post("/api/scheduler/predictive/reset")
    assert z.json()["reset"] is True
    assert client.get("/api/scheduler/predictive/hypotheses").json()["count"] == 0


def test_ws_streams(client):
    with client.websocket_connect("/api/scheduler/predictive/ws") as ws:
        d = ws.receive_json()
        assert d["offline_only"] is True and "hypotheses" in d
