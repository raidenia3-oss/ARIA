# -*- coding: utf-8 -*-
"""Singleton registry of LLM adapters.

Created once at startup from environment variables. Ollama is always
available (local server), Claude and OpenAI are opt-in via
``ARIA_CLAUDE_API_KEY`` / ``ARIA_OPENAI_API_KEY``. Tests can swap adapters
with :meth:`LLMRegistry.set_adapter`.
"""
from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

from .base_adapter import BaseLLMAdapter
from .claude_adapter import ClaudeAdapter
from .llm_config import LLMConfig
from .ollama_adapter import OllamaAdapter
from .openai_adapter import OpenAIAdapter

logger = logging.getLogger("AURA.LLM.Registry")


class LLMRegistry:
    """Factory + singleton for LLM adapters."""

    _instance: Optional["LLMRegistry"] = None

    def __new__(cls) -> "LLMRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._adapters = {}
            cls._instance._config = LLMConfig.from_env()
            cls._instance._init_adapters()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Drop the singleton (use in tests to force re-init)."""
        cls._instance = None

    def _init_adapters(self) -> None:
        # Ollama is always available as the local fallback.
        self._adapters["ollama"] = OllamaAdapter(self._config)

        # Claude: opt-in via env.
        if self._config.claude_api_key:
            try:
                self._adapters["claude"] = ClaudeAdapter(
                    self._config,
                    embedding_fallback=self._adapters["ollama"],
                )
            except Exception as exc:
                logger.warning("claude adapter init failed: %s", exc)

        # OpenAI: opt-in via env.
        if self._config.openai_api_key:
            try:
                self._adapters["openai"] = OpenAIAdapter(self._config)
            except Exception as exc:
                logger.warning("openai adapter init failed: %s", exc)

    def get_adapter(self, name: str) -> Optional[BaseLLMAdapter]:
        """Return the adapter for ``name``, falling back to Ollama."""
        return self._adapters.get(name) or self._adapters.get("ollama")

    def get_embedding_adapter(self) -> BaseLLMAdapter:
        """Prefer OpenAI for embeddings (cheaper + higher quality), else Ollama."""
        return self._adapters.get("openai") or self._adapters["ollama"]

    def list_adapters(self) -> List[str]:
        return sorted(self._adapters.keys())

    def set_adapter(self, name: str, adapter: BaseLLMAdapter) -> None:
        """Register or replace an adapter (used by tests)."""
        self._adapters[name] = adapter

    @property
    def config(self) -> LLMConfig:
        return self._config


def get_llm_registry() -> LLMRegistry:
    """Convenience accessor that returns the singleton."""
    return LLMRegistry()