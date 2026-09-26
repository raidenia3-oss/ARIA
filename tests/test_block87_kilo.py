"""BLOQUE 87 - REST + WS tests for /api/security/defense (offline)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.security.mitigation import reset_defense_engine
from backend.security.mitigation_routes import router


@pytest.fixture
def client():
    reset_defense_engine()
    app = FastAPI(title="AURA Defense Test", version="test")
    app.include_router(router)
    with TestClient(app) as c:
        yield c
    reset_defense_engine()


def test_status(client):
    r = client.get("/api/security/defense/status")
    assert r.status_code == 200 and r.json()["offline_only"] is True


def test_feed_evaluate_quarantine_restore(client):
    client.post(
        "/api/security/defense/feed",
        json={"category": "auth", "signal": "login_failed", "severity": "medium"},
    )
    for _ in range(4):
        client.post(
            "/api/security/defense/feed",
            json={"category": "auth", "signal": "login_failed", "severity": "medium"},
        )
    e = client.post("/api/security/defense/evaluate")
    assert e.json()["count"] >= 1
    a = client.get("/api/security/defense/alerts")
    assert a.json()["count"] >= 1
    q = client.get("/api/security/defense/quarantine")
    assert q.json()["count"] >= 1
    rid = q.json()["records"][0]["record_id"]
    rel = client.post(f"/api/security/defense/quarantine/{rid}/restore")
    assert rel.json()["restored"] is True
    assert client.post("/api/security/defense/reset").json()["reset"] is True


def test_scan_and_restore_404(client):
    s = client.post("/api/security/defense/scan", json={"text": "rm -rf /tmp/victim"})
    assert s.json()["count"] == 1
    assert client.post("/api/security/defense/quarantine/nope/restore").status_code == 409


def test_ws_heartbeat(client):
    with client.websocket_connect("/api/security/defense/ws") as ws:
        d = ws.receive_json()
        assert d["type"] == "heartbeat" and d["offline_only"] is True
