"""BLOQUE 72 - REST API tests for Knowledge RAG endpoints.

Tests use a minimal FastAPI app with only the knowledge router mounted
to avoid heavy imports from backend.main (which trigger HuggingFace API calls).
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def _reset():
    from backend.knowledge.rag import reset_rag_engine

    reset_rag_engine()
    yield
    reset_rag_engine()


@pytest.fixture
def client():
    """Build a minimal FastAPI app with only the knowledge router."""
    tmp = tempfile.mkdtemp(prefix="aura_kb_test_")
    os.environ["AURA_KNOWLEDGE_DIR"] = tmp

    from backend.knowledge.rag import reset_rag_engine

    reset_rag_engine()

    app = FastAPI(title="AURA Knowledge Test", version="test")
    from backend.knowledge.router import router as knowledge_router

    app.include_router(knowledge_router)

    with TestClient(app) as c:
        yield c

    reset_rag_engine()
    shutil.rmtree(tmp, ignore_errors=True)


def test_status(client):
    r = client.get("/api/knowledge/status")
    assert r.status_code == 200
    d = r.json()
    assert d["enabled"] is True
    assert "collections" in d


def test_create_and_list_collection(client):
    r = client.post("/api/knowledge/collections", json={"name": "mycoll"})
    assert r.status_code == 200
    r = client.get("/api/knowledge/collections")
    assert r.status_code == 200
    assert "mycoll" in r.json()


def test_index_text_and_search(client):
    r = client.post(
        "/api/knowledge/collections/test/index/text",
        json={"text": "The quick brown fox jumps over the lazy dog."},
    )
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "ok"
    r = client.post(
        "/api/knowledge/collections/test/search",
        json={"query": "fox"},
    )
    assert r.status_code == 200
    d = r.json()
    assert d["total_hits"] > 0


def test_inject_context(client):
    client.post(
        "/api/knowledge/collections/ctx/index/text",
        json={"text": "AURA is an AI assistant running locally."},
    )
    r = client.post(
        "/api/knowledge/inject",
        params={"query": "AURA", "collection": "ctx"},
    )
    assert r.status_code == 200
    d = r.json()
    assert "context" in d
    assert "CONOCIMIENTO" in d["context"]


def test_purge(client):
    client.post(
        "/api/knowledge/collections/p/index/text",
        json={"text": "data to purge"},
    )
    r = client.post("/api/knowledge/collections/p/purge")
    assert r.status_code == 200
    r = client.get("/api/knowledge/collections/p/status")
    assert r.status_code == 200
    assert r.json()["chunk_count"] == 0


def test_delete_collection(client):
    client.post("/api/knowledge/collections", json={"name": "delme"})
    r = client.delete("/api/knowledge/collections/delme")
    assert r.status_code == 200
    r = client.get("/api/knowledge/collections")
    assert "delme" not in r.json()
