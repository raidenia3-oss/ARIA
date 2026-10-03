# -*- coding: utf-8 -*-
"""Bridge between the LLM adapter registry and the memory engine.

The existing :class:`MemoryEngine` (``backend/services/memory_engine.py``)
already handles ChromaDB storage and Ollama embeddings. This module adds a
typed layer on top of it so callers can:

* store a memory with a specific LLM source
* search memories using any registered adapter
* retrieve context for an agent execution

It never duplicates the storage logic — it delegates to ``MemoryEngine``
for persistence and only injects the adapter for embedding / ranking.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from .adapter_registry import LLMRegistry
from .base_adapter import BaseLLMAdapter
from .llm_config import LLMConfig

logger = logging.getLogger("AURA.LLM.MemoryBridge")


class LLMMemoryBridge:
    """Integrates LLM adapters with the existing memory engine."""

    def __init__(self, registry: Optional[LLMRegistry] = None,
                 config: Optional[LLMConfig] = None) -> None:
        self.registry = registry or LLMRegistry()
        self.config = config or self.registry.config
        self._engine = None  # lazy: avoids circular import at module load

    @property
    def engine(self):
        """Lazy-load the MemoryEngine to avoid circular imports."""
        if self._engine is None:
            from backend.services.memory_engine import MemoryEngine
            self._engine = MemoryEngine()
        return self._engine

    @property
    def embedding_adapter(self) -> BaseLLMAdapter:
        """Adapter used for embeddings (OpenAI preferred, Ollama fallback)."""
        return self.registry.get_embedding_adapter()

    async def store_memory(self, content: str, memory_type: str = "episodic",
                           source: str = "agent", session_id: str = "",
                           source_llm: Optional[str] = None,
                           source_agent: Optional[str] = None,
                           metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Store a memory, tagging it with the LLM + agent that produced it.

        Returns the memory_id and the embedding dimensions used.
        """
        if not content or not content.strip():
            return {"status": "error", "error": "empty_text", "memory_id": None}

        # Generate embedding via the adapter.
        embed_result = await self.embedding_adapter.embed(content.strip())
        full_metadata = dict(metadata or {})
        full_metadata["source_llm"] = source_llm or self.embedding_adapter.name.lower()
        full_metadata["source_agent"] = source_agent or source
        full_metadata["embedding_model"] = embed_result.model
        full_metadata["embedding_dim"] = len(embed_result.vector)

        result = self.engine.remember(
            text=content.strip(),
            memory_type=memory_type,
            source=source,
            session_id=session_id,
            metadata=full_metadata,
        )
        result["embedding_dim"] = len(embed_result.vector)
        result["embedding_model"] = embed_result.model
        result["embedding_latency_ms"] = embed_result.latency_ms
        return result

    async def search_memory(self, query: str, max_results: int = 5,
                            min_relevance: Optional[float] = None,
                            memory_type: Optional[str] = None,
                            source: Optional[str] = None) -> Dict[str, Any]:
        """Search memories using the embedding adapter for the query vector.

        Falls back to the engine's own search when the adapter fails.
        """
        if not query or not query.strip():
            return {"status": "error", "error": "empty_query", "results": []}

        # Generate query embedding via the adapter.
        try:
            embed_result = await self.embedding_adapter.embed(query.strip())
            query_vec = embed_result.vector
        except Exception as exc:
            logger.debug("adapter embed failed, using engine fallback: %s", exc)
            return self.engine.search(query.strip(), max_results=max_results,
                                      min_relevance=min_relevance or self.config.min_relevance)

        # Use the engine's vector search with the adapter-generated vector.
        results = self.engine._store.search(
            query_vec,
            max_results=max_results,
            min_relevance=min_relevance if min_relevance is not None else self.config.min_relevance,
        )

        # Filter by type / source if requested.
        if memory_type or source:
            filtered = []
            for r in results:
                if memory_type and r.memory_type != memory_type:
                    continue
                if source and r.source != source:
                    continue
                filtered.append(r)
            results = filtered

        return {
            "status": "ok",
            "query": query,
            "count": len(results),
            "embedding_model": embed_result.model,
            "results": [r.to_dict() for r in results],
        }

    async def get_context_for_agent(self, agent_name: str, query: str,
                                    max_tokens: int = 2000) -> str:
        """Retrieve memory context for an agent execution.

        Returns a concatenated string of relevant memories, truncated to
        approximately ``max_tokens`` words.
        """
        result = await self.search_memory(
            query,
            max_results=self.config.search_top_k,
            source=agent_name,
        )
        memories = result.get("results", [])
        if not memories:
            # Try without the source filter — global memories.
            result = await self.search_memory(
                query,
                max_results=self.config.search_top_k,
            )
            memories = result.get("results", [])

        parts: List[str] = []
        total = 0
        for mem in memories:
            text = mem.get("text", "")
            tokens = len(text.split())
            if total + tokens > max_tokens:
                break
            parts.append(text)
            total += tokens
        return "\n\n".join(parts)

    async def rank_with_llm(self, query: str, memories: List[Dict[str, Any]],
                            top_k: int = 5, adapter_name: str = "claude") -> List[Dict[str, Any]]:
        """Re-rank memories using a generation-capable LLM.

        Falls back to cosine similarity when the named adapter is missing.
        """
        adapter = self.registry.get_adapter(adapter_name)
        if adapter is None or adapter_name not in self.registry.list_adapters():
            adapter = self.registry.get_embedding_adapter()
        if hasattr(adapter, "rank_memories"):
            return await adapter.rank_memories(query, memories, top_k=top_k)
        return await adapter.search_similar(query, memories, top_k=top_k)

    def get_status(self) -> Dict[str, Any]:
        """Status of the bridge and the underlying engine."""
        return {
            "adapters": self.registry.list_adapters(),
            "embedding_adapter": self.embedding_adapter.name,
            "config": {
                "embedding_model": self.config.embedding_model,
                "embedding_dim": self.config.embedding_dim,
                "search_top_k": self.config.search_top_k,
                "min_relevance": self.config.min_relevance,
            },
            "engine": self.engine.get_status(),
        }


_bridge: Optional[LLMMemoryBridge] = None


def get_llm_memory_bridge() -> LLMMemoryBridge:
    """Singleton accessor for the bridge."""
    global _bridge
    if _bridge is None:
        _bridge = LLMMemoryBridge()
    return _bridge


def reset_llm_memory_bridge() -> None:
    """Drop the singleton (used in tests)."""
    global _bridge
    _bridge = None