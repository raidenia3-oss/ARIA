# -*- coding: utf-8 -*-
"""Claude (Anthropic) adapter — generation only.

Claude does not expose a native embedding endpoint, so ``embed`` delegates
to a secondary adapter (Ollama by default) when one is configured. The
registry wires that up; this adapter just needs to know which one to call.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

from .base_adapter import BaseLLMAdapter, EmbeddingResult, GenerationResult
from .llm_config import LLMConfig

logger = logging.getLogger("AURA.LLM.ClaudeAdapter")


class ClaudeAdapter(BaseLLMAdapter):
    """Adapter for Claude via the Anthropic Messages API.

    The ``anthropic`` package is imported lazily so the rest of the codebase
    keeps working when it is not installed.
    """

    def __init__(self, config: Optional[LLMConfig] = None,
                 embedding_fallback: Optional[BaseLLMAdapter] = None) -> None:
        super().__init__(config)
        self._client = None
        self.embedding_fallback = embedding_fallback

    @property
    def client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:
                raise RuntimeError("anthropic package not installed") from exc
            api_key = self.config.claude_api_key
            if not api_key:
                raise RuntimeError("ARIA_CLAUDE_API_KEY not set")
            self._client = anthropic.Anthropic(api_key=api_key)
        return self._client

    def is_available(self) -> bool:
        return bool(self.config.claude_api_key)

    async def embed(self, text: str) -> EmbeddingResult:
        """Claude has no embedding endpoint — delegate to the fallback adapter."""
        if self.embedding_fallback is not None:
            return await self.embedding_fallback.embed(text)
        # Last resort: zero vector so callers can still store the memory.
        return EmbeddingResult(vector=[0.0] * self.config.embedding_dim,
                               model="claude-none",
                               latency_ms=0.0)

    async def generate_response(self, prompt: str, system_prompt: Optional[str] = None,
                                max_tokens: Optional[int] = None,
                                temperature: Optional[float] = None) -> GenerationResult:
        start = time.perf_counter()
        try:
            message = self.client.messages.create(
                model=self.config.claude_model,
                max_tokens=max_tokens or self.config.claude_max_tokens,
                temperature=temperature if temperature is not None else self.config.default_temperature,
                system=system_prompt or "",
                messages=[{"role": "user", "content": prompt}],
            )
            text = ""
            for block in getattr(message, "content", []):
                if getattr(block, "type", None) == "text":
                    text += getattr(block, "text", "")
            usage = getattr(message, "usage", None)
            tokens = int(getattr(usage, "output_tokens", 0) or 0) if usage else 0
            return GenerationResult(
                text=text.strip(),
                model=self.config.claude_model,
                tokens_used=tokens,
                latency_ms=(time.perf_counter() - start) * 1000.0,
                finish_reason=getattr(message, "stop_reason", "stop") or "stop",
            )
        except Exception as exc:
            logger.debug("claude generate error: %s", exc)
            return GenerationResult(text="", model=self.config.claude_model,
                                    latency_ms=(time.perf_counter() - start) * 1000.0)

    async def search_similar(self, query: str, memories: List[Dict[str, Any]],
                             top_k: int = 5) -> List[Dict[str, Any]]:
        """Claude re-ranks memories using semantic understanding.

        Falls back to cosine similarity when the fallback adapter is set,
        which is the common case in production.
        """
        if self.embedding_fallback is not None:
            return await self.embedding_fallback.search_similar(query, memories, top_k=top_k)
        return await super().search_similar(query, memories, top_k=top_k)

    async def rank_memories(self, query: str, memories: List[Dict[str, Any]],
                            top_k: int = 5) -> List[Dict[str, Any]]:
        """Use Claude's semantic understanding to re-rank memories.

        This is more expensive than cosine similarity but produces better
        results when the query is vague or the memories are short.
        """
        if not memories:
            return []
        summaries = "\n".join(
            f"{i}: {m.get('content', '')[:120]}" for i, m in enumerate(memories[:20])
        )
        prompt = (
            f'Given this query: "{query}"\n\n'
            f"Rank these memories by relevance (1=most relevant). "
            f"Return ONLY a JSON array of indices, like [3, 0, 7]:\n{summaries}"
        )
        result = await self.generate_response(prompt, max_tokens=128)
        try:
            text = result.text.strip()
            text = text[text.find("["):text.rfind("]") + 1]
            ranking: List[int] = json.loads(text)
        except (ValueError, json.JSONDecodeError):
            return list(memories[:top_k])
        ranked = []
        for idx in ranking:
            if isinstance(idx, int) and 0 <= idx < len(memories):
                ranked.append(memories[idx])
        return ranked[:top_k] if ranked else list(memories[:top_k])