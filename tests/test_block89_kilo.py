"""BLOQUE 89 - REST + WS tests for /api/mesh/consensus (offline)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.mesh_consensus import reset_consensus_engine
from backend.mesh_consensus.consensus_routes import router


@pytest.fixture
def client():
    reset_consensus_engine()
    app = FastAPI(title="AURA Consensus Test", version="test")
    app.include_router(router)
    with TestClient(app) as c:
        yield c
    reset_consensus_engine()


def test_status(client):
    r = client.get("/api/mesh/consensus/status")
    assert r.status_code == 200 and r.json()["offline_only"] is True


def test_round_vote_lifecycle(client):
    r = client.post(
        "/api/mesh/consensus/rounds",
        json={"topic": "mision", "proposal": "go", "voters": ["a", "b", "c"]},
    )
    assert r.status_code == 200
    rid = r.json()["round_id"]
    client.post(f"/api/mesh/consensus/rounds/{rid}/vote", json={"voter": "a", "choice": "yes"})
    v = client.post(f"/api/mesh/consensus/rounds/{rid}/vote", json={"voter": "b", "choice": "yes"})
    assert v.json()["result"] == "accepted"
    assert client.get("/api/mesh/consensus/rounds").json()["count"] == 1


def test_round_rejects_empty(client):
    assert (
        client.post(
            "/api/mesh/consensus/rounds", json={"topic": "", "proposal": "", "voters": []}
        ).status_code
        == 422
    )


def test_task_auction(client):
    t = client.post("/api/mesh/consensus/tasks", json={"title": "subtarea-x"})
    tid = t.json()["task_id"]
    client.post(f"/api/mesh/consensus/tasks/{tid}/bid", json={"node_id": "n1", "capacity": 0.2})
    b = client.post(f"/api/mesh/consensus/tasks/{tid}/bid", json={"node_id": "n2", "capacity": 0.8})
    assert b.json()["assignee"] == "n2"


def test_ws_heartbeat(client):
    with client.websocket_connect("/api/mesh/consensus/ws") as ws:
        d = ws.receive_json()
        assert d["event"] == "heartbeat" and d["offline_only"] is True
