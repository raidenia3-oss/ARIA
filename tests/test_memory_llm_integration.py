# -*- coding: utf-8 -*-
"""Tests for the LLM <-> memory bridge integration."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.llm.adapter_registry import LLMRegistry
from backend.llm.base_adapter import EmbeddingResult
from backend.llm.llm_config import LLMConfig
from backend.llm.memory_bridge import LLMMemoryBridge, get_llm_memory_bridge, reset_llm_memory_bridge
from backend.llm.ollama_adapter import OllamaAdapter


@pytest.fixture(autouse=True)
def reset_state():
    LLMRegistry.reset()
    reset_llm_memory_bridge()
    yield
    LLMRegistry.reset()
    reset_llm_memory_bridge()


def test_bridge_is_singleton():
    a = get_llm_memory_bridge()
    b = get_llm_memory_bridge()
    assert a is b


def test_bridge_has_embedding_adapter():
    bridge = LLMMemoryBridge()
    adapter = bridge.embedding_adapter
    assert adapter is not None
    assert adapter.name in ("OpenAIAdapter", "OllamaAdapter")


def test_bridge_status():
    bridge = LLMMemoryBridge()
    status = bridge.get_status()
    assert "adapters" in status
    assert "embedding_adapter" in status
    assert "engine" in status


@pytest.mark.asyncio
async def test_store_memory_empty_text():
    bridge = LLMMemoryBridge()
    result = await bridge.store_memory("")
    assert result["status"] == "error"
    assert result["memory_id"] is None


@pytest.mark.asyncio
async def test_store_memory_uses_adapter():
    bridge = LLMMemoryBridge()
    # Replace the engine with a mock so no real ChromaDB is touched.
    mock_engine = MagicMock()
    mock_engine.remember.return_value = {"status": "ok", "memory_id": "abc123"}
    bridge._engine = mock_engine

    # Replace the embedding adapter with a mock.
    mock_adapter = OllamaAdapter(LLMConfig())
    mock_adapter.embed = AsyncMock(return_value=EmbeddingResult(
        vector=[0.1, 0.2, 0.3], model="mock-embed", latency_ms=1.0
    ))
    bridge.registry.set_adapter("mock", mock_adapter)
    bridge._embedding_adapter_override = mock_adapter

    # Patch the property to return our mock.
    type(bridge).embedding_adapter = property(lambda self: mock_adapter)
    try:
        result = await bridge.store_memory(
            "ARIA es un sistema autónomo",
            memory_type="context",
            source_agent="planner",
            source_llm="ollama",
        )
    finally:
        del type(bridge).embedding_adapter

    assert result["status"] == "ok"
    assert result["memory_id"] == "abc123"
    assert result["embedding_dim"] == 3
    assert result["embedding_model"] == "mock-embed"
    # The engine.remember call should carry the metadata.
    args, kwargs = mock_engine.remember.call_args
    assert kwargs["metadata"]["source_llm"] == "ollama"
    assert kwargs["metadata"]["source_agent"] == "planner"


@pytest.mark.asyncio
async def test_search_memory_empty_query():
    bridge = LLMMemoryBridge()
    result = await bridge.search_memory("")
    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_search_memory_returns_results():
    bridge = LLMMemoryBridge()
    mock_adapter = OllamaAdapter(LLMConfig())
    mock_adapter.embed = AsyncMock(return_value=EmbeddingResult(vector=[1.0, 0.0], model="mock"))
    bridge.registry.set_adapter("mock", mock_adapter)
    type(bridge).embedding_adapter = property(lambda self: mock_adapter)
    try:
        # Replace the engine with a mock that returns results.
        mock_engine = MagicMock()
        mock_record = MagicMock()
        mock_record.to_dict.return_value = {"memory_id": "x", "text": "hello", "relevance_score": 0.9}
        mock_engine._store.search.return_value = [mock_record]
        bridge._engine = mock_engine

        result = await bridge.search_memory("hello", max_results=3)
    finally:
        del type(bridge).embedding_adapter

    assert result["status"] == "ok"
    assert result["count"] == 1
    assert result["results"][0]["text"] == "hello"


@pytest.mark.asyncio
async def test_get_context_for_agent_concatenates():
    bridge = LLMMemoryBridge()
    mock_adapter = OllamaAdapter(LLMConfig())
    mock_adapter.embed = AsyncMock(return_value=EmbeddingResult(vector=[1.0], model="mock"))
    bridge.registry.set_adapter("mock", mock_adapter)
    type(bridge).embedding_adapter = property(lambda self: mock_adapter)
    try:
        mock_engine = MagicMock()
        rec1 = MagicMock()
        rec1.to_dict.return_value = {"text": "Paso 1: inicializar", "relevance_score": 0.9}
        rec2 = MagicMock()
        rec2.to_dict.return_value = {"text": "Paso 2: compilar", "relevance_score": 0.8}
        mock_engine._store.search.return_value = [rec1, rec2]
        bridge._engine = mock_engine

        context = await bridge.get_context_for_agent("agent_coder", "pasos", max_tokens=2000)
    finally:
        del type(bridge).embedding_adapter

    assert "inicializar" in context
    assert "compilar" in context


@pytest.mark.asyncio
async def test_get_context_for_agent_empty():
    bridge = LLMMemoryBridge()
    mock_adapter = OllamaAdapter(LLMConfig())
    mock_adapter.embed = AsyncMock(return_value=EmbeddingResult(vector=[1.0], model="mock"))
    bridge.registry.set_adapter("mock", mock_adapter)
    type(bridge).embedding_adapter = property(lambda self: mock_adapter)
    try:
        mock_engine = MagicMock()
        mock_engine._store.search.return_value = []
        bridge._engine = mock_engine
        context = await bridge.get_context_for_agent("nobody", "nothing")
    finally:
        del type(bridge).embedding_adapter
    assert context == ""


@pytest.mark.asyncio
async def test_rank_with_llm_falls_back_to_cosine():
    bridge = LLMMemoryBridge()
    mock_adapter = OllamaAdapter(LLMConfig())
    mock_adapter.embed = AsyncMock(return_value=EmbeddingResult(vector=[1.0, 0.0], model="mock"))
    mock_adapter.search_similar = AsyncMock(return_value=[{"id": 1, "content": "x"}])
    # Register as "openai" so get_embedding_adapter() returns the mock.
    bridge.registry.set_adapter("openai", mock_adapter)
    result = await bridge.rank_with_llm("test", [{"id": 1, "content": "x"}], top_k=1, adapter_name="claude")
    assert len(result) == 1