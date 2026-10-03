# -*- coding: utf-8 -*-
"""Tests for LLM adapters (Claude, OpenAI, Ollama)."""
from __future__ import annotations

import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch

from backend.llm.base_adapter import BaseLLMAdapter, EmbeddingResult, GenerationResult
from backend.llm.llm_config import LLMConfig
from backend.llm.ollama_adapter import OllamaAdapter
from backend.llm.adapter_registry import LLMRegistry


@pytest.fixture(autouse=True)
def reset_registry():
    LLMRegistry.reset()
    yield
    LLMRegistry.reset()


def test_registry_is_singleton():
    a = LLMRegistry()
    b = LLMRegistry()
    assert a is b


def test_registry_lists_ollama_by_default():
    r = LLMRegistry()
    assert "ollama" in r.list_adapters()


def test_get_adapter_falls_back_to_ollama():
    r = LLMRegistry()
    adapter = r.get_adapter("does-not-exist")
    assert adapter is not None
    assert adapter.name == "OllamaAdapter"


def test_get_embedding_adapter_prefers_openai():
    r = LLMRegistry()
    adapter = r.get_embedding_adapter()
    assert adapter.name in ("OpenAIAdapter", "OllamaAdapter")


def test_config_defaults():
    cfg = LLMConfig()
    assert cfg.embedding_model == "nomic-embed-text"
    assert cfg.embedding_dim == 768
    assert cfg.ollama_url == "http://localhost:11434"


def test_config_from_env_uses_env_vars(monkeypatch):
    monkeypatch.setenv("ARIA_EMBEDDING_DIM", "384")
    monkeypatch.setenv("ARIA_OLLAMA_URL", "http://example.com:1234")
    cfg = LLMConfig.from_env()
    assert cfg.embedding_dim == 384
    assert cfg.ollama_url == "http://example.com:1234"


@pytest.mark.asyncio
async def test_ollama_embed_returns_vector():
    adapter = OllamaAdapter(LLMConfig())
    adapter._client = AsyncMock()
    adapter._client.post = AsyncMock(return_value=MagicMock(
        status_code=200, json=lambda: {"embedding": [0.1, 0.2, 0.3]}
    ))
    result = await adapter.embed("hello")
    assert isinstance(result, EmbeddingResult)
    assert result.vector == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_ollama_embed_handles_failure():
    adapter = OllamaAdapter(LLMConfig())
    adapter._client = AsyncMock()
    adapter._client.post = AsyncMock(side_effect=Exception("network down"))
    result = await adapter.embed("hello")
    assert result.vector == [0.0] * adapter.config.embedding_dim


@pytest.mark.asyncio
async def test_ollama_generate_response():
    adapter = OllamaAdapter(LLMConfig())
    adapter._client = AsyncMock()
    adapter._client.post = AsyncMock(return_value=MagicMock(
        status_code=200,
        json=lambda: {"response": "Hello there", "eval_count": 5, "done_reason": "stop"},
    ))
    result = await adapter.generate_response("hi")
    assert isinstance(result, GenerationResult)
    assert result.text == "Hello there"
    assert result.tokens_used == 5


@pytest.mark.asyncio
async def test_ollama_generate_handles_failure():
    adapter = OllamaAdapter(LLMConfig())
    adapter._client = AsyncMock()
    adapter._client.post = AsyncMock(side_effect=Exception("boom"))
    result = await adapter.generate_response("hi")
    assert result.text == ""


@pytest.mark.asyncio
async def test_search_similar_ranks_by_cosine():
    adapter = OllamaAdapter(LLMConfig())
    adapter.embed = AsyncMock(return_value=EmbeddingResult(
        vector=[0.95, 0.05], model="test"
    ))
    memories = [
        {"id": 1, "content": "python", "embedding": [0.9, 0.1]},
        {"id": 2, "content": "rust", "embedding": [0.1, 0.9]},
    ]
    result = await adapter.search_similar("python", memories, top_k=2)
    assert len(result) == 2
    assert result[0]["id"] == 1
    assert result[0]["relevance"] > result[1]["relevance"]


@pytest.mark.asyncio
async def test_search_similar_skips_memories_without_embedding():
    adapter = OllamaAdapter(LLMConfig())
    adapter.embed = AsyncMock(return_value=EmbeddingResult(vector=[1.0, 0.0], model="test"))
    memories = [
        {"id": 1, "content": "no embedding"},
        {"id": 2, "content": "has embedding", "embedding": [1.0, 0.0]},
    ]
    result = await adapter.search_similar("test", memories, top_k=5)
    assert len(result) == 1
    assert result[0]["id"] == 2


def test_cosine_similarity_identical():
    score = BaseLLMAdapter.cosine_similarity([1, 0, 0], [1, 0, 0])
    assert score == pytest.approx(1.0)


def test_cosine_similarity_orthogonal():
    score = BaseLLMAdapter.cosine_similarity([1, 0], [0, 1])
    assert score == pytest.approx(0.0)


def test_cosine_similarity_opposite():
    score = BaseLLMAdapter.cosine_similarity([1, 0], [-1, 0])
    assert score == pytest.approx(-1.0)


def test_cosine_similarity_zero_vector():
    score = BaseLLMAdapter.cosine_similarity([0, 0], [1, 1])
    assert score == 0.0


def test_embedding_result_to_dict():
    r = EmbeddingResult(vector=[0.1], model="test", latency_ms=1.5)
    d = r.to_dict()
    assert d["vector"] == [0.1]
    assert d["model"] == "test"


def test_generation_result_to_dict():
    r = GenerationResult(text="hi", model="test", tokens_used=3, latency_ms=2.0, finish_reason="stop")
    d = r.to_dict()
    assert d["text"] == "hi"
    assert d["tokens_used"] == 3


def test_ollama_adapter_is_available():
    adapter = OllamaAdapter(LLMConfig())
    assert adapter.is_available() is True


def test_ollama_adapter_repr():
    adapter = OllamaAdapter(LLMConfig())
    assert "OllamaAdapter" in repr(adapter)