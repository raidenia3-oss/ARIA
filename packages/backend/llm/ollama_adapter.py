# -*- coding: utf-8 -*-
"""Ollama adapter — local LLM + embeddings, always available as fallback.

Uses the Ollama HTTP API directly (no extra dependency) so the adapter
works even when ``anthropic`` or ``openai`` are not installed. The base
URL and model names come from :class:`LLMConfig`.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from .base_adapter import BaseLLMAdapter, EmbeddingResult, GenerationResult
from .llm_config import LLMConfig

logger = logging.getLogger("AURA.LLM.OllamaAdapter")


class OllamaAdapter(BaseLLMAdapter):
    """Adapter for a local Ollama server."""

    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        super().__init__(config)
        self.base_url = self.config.ollama_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    def is_available(self) -> bool:
        return bool(self.base_url)

    async def embed(self, text: str) -> EmbeddingResult:
        start = time.perf_counter()
        try:
            resp = await self.client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.config.ollama_embedding_model, "prompt": text},
            )
            if resp.status_code != 200:
                logger.debug("ollama embed failed: %s %s", resp.status_code, resp.text[:200])
                return EmbeddingResult(vector=[0.0] * self.config.embedding_dim,
                                       model=self.config.ollama_embedding_model,
                                       latency_ms=(time.perf_counter() - start) * 1000.0)
            data = resp.json()
            vec = data.get("embedding", [])
            if not vec:
                return EmbeddingResult(vector=[0.0] * self.config.embedding_dim,
                                       model=self.config.ollama_embedding_model,
                                       latency_ms=(time.perf_counter() - start) * 1000.0)
            return EmbeddingResult(
                vector=vec,
                model=self.config.ollama_embedding_model,
                latency_ms=(time.perf_counter() - start) * 1000.0,
            )
        except Exception as exc:
            logger.debug("ollama embed error: %s", exc)
            return EmbeddingResult(vector=[0.0] * self.config.embedding_dim,
                                   model=self.config.ollama_embedding_model,
                                   latency_ms=(time.perf_counter() - start) * 1000.0)

    async def generate_response(self, prompt: str, system_prompt: Optional[str] = None,
                                max_tokens: Optional[int] = None,
                                temperature: Optional[float] = None) -> GenerationResult:
        start = time.perf_counter()
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        try:
            resp = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.config.ollama_model,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens or self.config.default_max_tokens,
                        "temperature": temperature if temperature is not None else self.config.default_temperature,
                    },
                },
            )
            if resp.status_code != 200:
                logger.debug("ollama generate failed: %s %s", resp.status_code, resp.text[:200])
                return GenerationResult(text="", model=self.config.ollama_model,
                                        latency_ms=(time.perf_counter() - start) * 1000.0)
            data = resp.json()
            text = str(data.get("response", "")).strip()
            return GenerationResult(
                text=text,
                model=self.config.ollama_model,
                tokens_used=int(data.get("eval_count", 0)),
                latency_ms=(time.perf_counter() - start) * 1000.0,
                finish_reason=data.get("done_reason", "stop"),
            )
        except Exception as exc:
            logger.debug("ollama generate error: %s", exc)
            return GenerationResult(text="", model=self.config.ollama_model,
                                    latency_ms=(time.perf_counter() - start) * 1000.0)

    async def __aenter__(self) -> "OllamaAdapter":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None