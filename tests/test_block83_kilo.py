"""BLOQUE 83 - REST + WS tests for /api/fusion (offline)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.fusion.fusion_routes import router
from backend.fusion.sensory import reset_fusion_engine


@pytest.fixture(autouse=True)
def _reset():
    reset_fusion_engine()
    yield
    reset_fusion_engine()


@pytest.fixture
def client():
    app = FastAPI(title="AURA Fusion Test", version="test")
    app.include_router(router)
    with TestClient(app) as c:
        yield c


def test_status(client):
    r = client.get("/api/fusion/status")
    assert r.status_code == 200
    d = r.json()
    assert d["online"] is True and d["offline_only"] is True
    assert "vision" in d["sources"]


def test_ingest_and_context(client):
    r = client.post(
        "/api/fusion/ingest", json={"source": "vision", "kind": "frame", "severity": "high"}
    )
    assert r.status_code == 200
    r = client.get("/api/fusion/context")
    assert r.status_code == 200
    d = r.json()
    assert d["event_count"] == 1 and d["sources"] == {"vision": 1}


def test_ingest_rejects_bad_source(client):
    r = client.post("/api/fusion/ingest", json={"source": "nope"})
    assert r.status_code == 422


def test_batch_history_reset(client):
    r = client.post(
        "/api/fusion/ingest/batch",
        json={
            "events": [
                {"source": "audio", "severity": "low"},
                {"source": "network", "severity": "info"},
            ]
        },
    )
    assert r.json()["count"] == 2
    client.get("/api/fusion/context")
    h = client.get("/api/fusion/history")
    assert h.json()["count"] >= 1
    z = client.post("/api/fusion/reset")
    assert z.json()["events_cleared"] == 2


def test_ws_streams_snapshot(client):
    with client.websocket_connect("/api/fusion/ws") as ws:
        d = ws.receive_json()
        assert "state" in d and d["offline_only"] is True
