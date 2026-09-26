"""BLOQUE 88 - REST + WS tests for /api/memory/cognitive (offline)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.memory.cognitive_graph import reset_cognitive_graph
from backend.memory.cognitive_routes import router


@pytest.fixture
def client():
    reset_cognitive_graph()
    app = FastAPI(title="AURA Cognitive Test", version="test")
    app.include_router(router)
    with TestClient(app) as c:
        yield c
    reset_cognitive_graph()


def test_status(client):
    r = client.get("/api/memory/cognitive/status")
    assert r.status_code == 200 and r.json()["offline_only"] is True


def test_ingest_and_search(client):
    r = client.post(
        "/api/memory/cognitive/ingest",
        json={
            "text": "AURA usa ChromaDB y depende de Ollama para RAG.",
            "source": "rag",
            "kind": "concept",
        },
    )
    assert r.status_code == 200 and r.json()["count"] >= 1
    s = client.get("/api/memory/cognitive/search", params={"q": "ChromaDB"})
    assert s.json()["count"] >= 1


def test_clusters_and_summaries(client):
    client.post(
        "/api/memory/cognitive/ingest",
        json={"text": "AURA integra ChromaDB, Ollama y FastEmbed en el pipeline RAG."},
    )
    client.post(
        "/api/memory/cognitive/ingest",
        json={"text": "El motor de memoria usa ChromaDB y embeddings locales."},
    )
    c = client.post("/api/memory/cognitive/consolidate", json={"force": True})
    assert c.json()["count"] >= 1
    cl = client.get("/api/memory/cognitive/clusters")
    assert cl.json()["count"] >= 1
    sm = client.get("/api/memory/cognitive/summaries")
    assert sm.json()["count"] >= 1


def test_neighbors_and_reset(client):
    client.post(
        "/api/memory/cognitive/ingest",
        json={"text": "El modulo de seguridad cifra credenciales con Fernet."},
    )
    s = client.get("/api/memory/cognitive/search", params={"q": "seguridad"})
    nid = s.json()["nodes"][0]["node_id"]
    nb = client.get(f"/api/memory/cognitive/nodes/{nid}/neighbors")
    assert nb.json()["count"] >= 1
    assert client.post("/api/memory/cognitive/reset").json()["reset"] is True
    assert client.get("/api/memory/cognitive/status").json()["nodes"] == 0


def test_ws_heartbeat(client):
    with client.websocket_connect("/api/memory/cognitive/ws") as ws:
        d = ws.receive_json()
        assert d["type"] == "heartbeat" and d["offline_only"] is True
