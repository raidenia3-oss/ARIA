# -*- coding: utf-8 -*-
"""Abstract base class for LLM adapters.

Every adapter implements the same three operations: embed (text -> vector),
generate_response (prompt -> text) and search_similar (query + memories ->
ranked subset). The base class provides cosine similarity so concrete
adapters only need to implement the network call.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import numpy as np

from .llm_config import LLMConfig

logger = logging.getLogger("AURA.LLM.BaseAdapter")


class EmbeddingResult:
    """Outcome of an embedding call."""

    def __init__(self, vector: List[float], model: str = "", latency_ms: float = 0.0) -> None:
        self.vector = vector
        self.model = model
        self.latency_ms = latency_ms

    def to_dict(self) -> Dict[str, Any]:
        return {"vector": self.vector, "model": self.model, "latency_ms": self.latency_ms}


class GenerationResult:
    """Outcome of a text generation call."""

    def __init__(self, text: str, model: str = "", tokens_used: int = 0,
                 latency_ms: float = 0.0, finish_reason: str = "") -> None:
        self.text = text
        self.model = model
        self.tokens_used = tokens_used
        self.latency_ms = latency_ms
        self.finish_reason = finish_reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "model": self.model,
            "tokens_used": self.tokens_used,
            "latency_ms": self.latency_ms,
            "finish_reason": self.finish_reason,
        }


class BaseLLMAdapter(ABC):
    """Common interface for Claude, OpenAI and Ollama adapters."""

    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        self.config = config or LLMConfig.from_env()
        self.name = self.__class__.__name__

    @abstractmethod
    async def embed(self, text: str) -> EmbeddingResult:
        """Generate an embedding for ``text``.

        Returns an :class:`EmbeddingResult` with the vector and metadata.
        """

    @abstractmethod
    async def generate_response(self, prompt: str, system_prompt: Optional[str] = None,
                                max_tokens: Optional[int] = None,
                                temperature: Optional[float] = None) -> GenerationResult:
        """Generate a text response for ``prompt``."""

    async def search_similar(self, query: str, memories: List[Dict[str, Any]],
                             top_k: int = 5) -> List[Dict[str, Any]]:
        """Rank ``memories`` by cosine similarity to the query embedding.

        Memories must carry an ``embedding`` field (list of floats). Those
        without one are skipped. Returns the top ``top_k`` sorted by score
        (highest first), with the score attached as ``relevance``.
        """
        if not memories:
            return []
        query_result = await self.embed(query)
        query_vec = np.array(query_result.vector, dtype=np.float32)
        norm_q = np.linalg.norm(query_vec)
        if norm_q == 0:
            return []

        scored: List[tuple] = []
        for mem in memories:
            raw = mem.get("embedding")
            if not raw:
                continue
            mem_vec = np.array(raw, dtype=np.float32)
            norm_m = np.linalg.norm(mem_vec)
            if norm_m == 0:
                continue
            score = float(np.dot(query_vec, mem_vec) / (norm_q * norm_m))
            entry = dict(mem)
            entry["relevance"] = round(score, 4)
            scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:top_k]]

    @staticmethod
    def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        """Cosine similarity between two vectors (pure, no numpy needed)."""
        a = np.array(vec_a, dtype=np.float32)
        b = np.array(vec_b, dtype=np.float32)
        na = np.linalg.norm(a)
        nb = np.linalg.norm(b)
        if na == 0 or nb == 0:
            return 0.0
        return float(np.dot(a, b) / (na * nb))

    def is_available(self) -> bool:
        """True when the adapter has the credentials it needs to run."""
        return True

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"{self.name}(available={self.is_available()})"