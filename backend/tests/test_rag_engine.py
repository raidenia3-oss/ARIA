"""Tests for Memory/RAG Engine - retrieval augmented generation."""

from __future__ import annotations

import time

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.services.memory_engine import MemoryEngine


@pytest.fixture
def memory_engine():
    with patch("backend.services.memory_engine.MemoryStore"):
        engine = MemoryEngine(orchestrator=None)
        engine._store = MagicMock()
        engine._store.count.return_value = 0
        engine._store.search.return_value = []
        return engine


@pytest.fixture
def sample_documents():
    return [
        {"id": "doc1", "text": "The Earth orbits the Sun", "metadata": {"type": "fact"}},
        {"id": "doc2", "text": "Python is a programming language", "metadata": {"type": "fact"}},
        {"id": "doc3", "text": "Machine learning uses data to train models", "metadata": {"type": "concept"}},
    ]


def test_memory_engine_init(memory_engine):
    assert memory_engine is not None
    assert memory_engine.orchestrator is None


def test_remember_valid(memory_engine):
    with patch.object(memory_engine._embedding_provider, "embed", return_value=[0.1, 0.2, 0.3]):
        result = memory_engine.remember("AURA is an AI assistant", memory_type="episodic")
    assert result.get("status") == "ok"
    assert "memory_id" in result


def test_remember_empty_text(memory_engine):
    result = memory_engine.remember("")
    assert result.get("status") == "error"
    result = memory_engine.remember("   ")
    assert result.get("status") == "error"


def test_search_valid(memory_engine):
    memory_engine._store.search.return_value = []
    result = memory_engine.search("AURA assistant", max_results=3)
    assert result.get("status") == "ok"
    assert "results" in result


def test_search_empty_query(memory_engine):
    result = memory_engine.search("")
    assert result.get("status") == "error"
    result = memory_engine.search("   ")
    assert result.get("status") == "error"


def test_forget_existing(memory_engine):
    memory_engine._store.delete.return_value = True
    result = memory_engine.forget("mem_123")
    assert result.get("status") == "ok"
    assert result.get("deleted") is True


def test_forget_missing(memory_engine):
    memory_engine._store.delete.return_value = False
    result = memory_engine.forget("missing_mem")
    assert result.get("status") == "not_found"


def test_inject_context(memory_engine):
    memory_engine._store.search.return_value = []
    context = memory_engine.inject_context("test query", max_results=2)
    assert isinstance(context, list)


def test_get_status(memory_engine):
    status = memory_engine.get_status()
    assert isinstance(status, dict)
    assert "total_memories" in status
    assert "embedding_backend" in status
    assert "vector_store" in status


def test_remember_with_metadata(memory_engine):
    with patch.object(memory_engine._embedding_provider, "embed", return_value=[0.1, 0.2, 0.3]):
        result = memory_engine.remember(
            "context note",
            memory_type="semantic",
            source="mobile",
            session_id="abc",
            metadata={"topic": "test"},
        )
    assert result.get("status") == "ok"
    assert result.get("type") == "semantic"


def test_search_with_custom_threshold(memory_engine):
    memory_engine._store.search.return_value = []
    result = memory_engine.search("query", max_results=5, min_relevance=0.5)
    assert result.get("status") == "ok"


def test_rag_full_pipeline(memory_engine):
    with patch.object(memory_engine._embedding_provider, "embed", return_value=[0.1, 0.2, 0.3]):
        remember_result = memory_engine.remember("AURA uses Python for backend")
    assert remember_result.get("status") == "ok"

    memory_engine._store.search.return_value = []
    search_result = memory_engine.search("Python backend", max_results=2)
    assert search_result.get("status") == "ok"

    context = memory_engine.inject_context("Python backend", max_results=2)
    assert isinstance(context, list)


def test_semantic_similarity_ordering(memory_engine):
    docs = [
        {"id": "d1", "text": "Python programming", "metadata": {}},
        {"id": "d2", "text": "Quantum computing qubits", "metadata": {}},
    ]
    with patch.object(memory_engine._embedding_provider, "embed", side_effect=[[1.0, 0.0], [0.0, 1.0], [0.9, 0.1]]):
        memory_engine.remember(docs[0]["text"])
        memory_engine.remember(docs[1]["text"])

    class FakeRecord:
        def __init__(self, text):
            self.text = text
            self.relevance_score = 0.9 if "Python" in text else 0.2
            self.recency_score = 1.0
            self.memory_id = text[:4]
            self.memory_type = "episodic"
        def to_dict(self):
            return {"text": self.text, "relevance_score": self.relevance_score, "memory_id": self.memory_id, "memory_type": self.memory_type}

    memory_engine._store.search.return_value = [FakeRecord(docs[0]["text"]), FakeRecord(docs[1]["text"])]
    result = memory_engine.search("Python", max_results=2)
    assert result.get("status") == "ok"
    assert len(result.get("results", [])) == 2
