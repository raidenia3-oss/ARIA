# -*- coding: utf-8 -*-
"""LLM adapter layer for AURA OS v6.

Provides a unified interface over Claude, OpenAI and Ollama so the memory
engine and agents can switch providers without changing call sites. The
registry is a singleton: adapters are created once at startup and reused.
"""
from __future__ import annotations

from .base_adapter import BaseLLMAdapter, EmbeddingResult, GenerationResult
from .llm_config import LLMConfig, get_llm_config
from .ollama_adapter import OllamaAdapter
from .openai_adapter import OpenAIAdapter
from .claude_adapter import ClaudeAdapter
from .adapter_registry import LLMRegistry

__all__ = [
    "BaseLLMAdapter",
    "EmbeddingResult",
    "GenerationResult",
    "LLMConfig",
    "get_llm_config",
    "OllamaAdapter",
    "OpenAIAdapter",
    "ClaudeAdapter",
    "LLMRegistry",
]