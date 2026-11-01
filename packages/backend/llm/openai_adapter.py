# -*- coding: utf-8 -*-
"""OpenAI adapter — chat completions + embeddings.

Uses the official ``openai`` package (already a project dependency). Both
``embed`` and ``generate_response`` are async wrappers around the sync
client so callers can use ``await`` consistently.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from .base_adapter import BaseLLMAdapter, EmbeddingResult, GenerationResult
from .llm_config import LLMConfig

logger = logging.getLogger("AURA.LLM.OpenAIAdapter")


class OpenAIAdapter(BaseLLMAdapter):
    """Adapter for OpenAI (GPT + text-embedding models)."""

    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        super().__init__(config)
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                import openai
            except ImportError as exc:
                raise RuntimeError("openai package not installed") from exc
            api_key = self.config.openai_api_key
            if not api_key:
                raise RuntimeError("ARIA_OPENAI_API_KEY not set")
            self._client = openai.OpenAI(api_key=api_key)
        return self._client

    def is_available(self) -> bool:
        return bool(self.config.openai_api_key)

    async def embed(self, text: str) -> EmbeddingResult:
        start = time.perf_counter()
        try:
            response = self.client.embeddings.create(
                model=self.config.openai_embedding_model,
                input=text,
            )
            vec = response.data[0].embedding
            return EmbeddingResult(
                vector=vec,
                model=self.config.openai_embedding_model,
                latency_ms=(time.perf_counter() - start) * 1000.0,
            )
        except Exception as exc:
            logger.debug("openai embed error: %s", exc)
            return EmbeddingResult(vector=[0.0] * self.config.embedding_dim,
                                   model=self.config.openai_embedding_model,
                                   latency_ms=(time.perf_counter() - start) * 1000.0)

    async def generate_response(self, prompt: str, system_prompt: Optional[str] = None,
                                max_tokens: Optional[int] = None,
                                temperature: Optional[float] = None) -> GenerationResult:
        start = time.perf_counter()
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        try:
            response = self.client.chat.completions.create(
                model=self.config.openai_model,
                messages=messages,
                max_tokens=max_tokens or self.config.openai_max_tokens,
                temperature=temperature if temperature is not None else self.config.default_temperature,
            )
            choice = response.choices[0]
            text = str(choice.message.content or "").strip()
            usage = getattr(response, "usage", None)
            tokens = int(getattr(usage, "completion_tokens", 0) or 0) if usage else 0
            return GenerationResult(
                text=text,
                model=self.config.openai_model,
                tokens_used=tokens,
                latency_ms=(time.perf_counter() - start) * 1000.0,
                finish_reason=getattr(choice, "finish_reason", "stop") or "stop",
            )
        except Exception as exc:
            logger.debug("openai generate error: %s", exc)
            return GenerationResult(text="", model=self.config.openai_model,
                                    latency_ms=(time.perf_counter() - start) * 1000.0)