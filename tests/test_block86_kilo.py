"""BLOQUE 86 - REST + WS tests for /api/ai/finetune (offline)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.edge_ai.engine import reset_edge_trainer
from backend.edge_ai.finetune_routes import router


@pytest.fixture
def client():
    reset_edge_trainer()
    app = FastAPI(title="AURA Edge FT Test", version="test")
    app.include_router(router)
    with TestClient(app) as c:
        yield c
    reset_edge_trainer()


def _recs(n=4):
    return [
        {"instruction": f"q{i}", "output": f"a{i}", "score": 0.9, "source": "interaction"}
        for i in range(n)
    ]


def test_status(client):
    r = client.get("/api/ai/finetune/status")
    assert r.status_code == 200 and r.json()["offline_only"] is True


def test_dataset_train_lifecycle(client):
    d = client.post("/api/ai/finetune/dataset/build", json={"records": _recs()})
    assert d.json()["count"] == 4
    t = client.post("/api/ai/finetune/train", json={"records": _recs(), "rank": 8, "epochs": 1})
    assert t.status_code == 200
    aid = t.json()["adapter"]["adapter_id"]
    e = client.post(f"/api/ai/finetune/adapters/{aid}/evaluate")
    assert e.json()["evaluated"] is True
    s = client.post(f"/api/ai/finetune/adapters/{aid}/activate")
    assert s.json()["swapped"] is True
    rb = client.post("/api/ai/finetune/rollback")
    assert rb.json()["rolled_back"] is True


def test_train_rejects_empty(client):
    assert client.post("/api/ai/finetune/train", json={"records": []}).status_code == 422


def test_ws_heartbeat(client):
    with client.websocket_connect("/api/ai/finetune/ws") as ws:
        d = ws.receive_json()
        assert d["event"] == "heartbeat" and d["offline_only"] is True
