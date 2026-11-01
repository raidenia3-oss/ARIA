# -*- coding: utf-8 -*-
"""Centralised LLM configuration for AURA OS v6.

Every adapter reads from this config so the embedding dimension, model
names and token budgets are defined in one place. The defaults target
Ollama (always available locally); Claude and OpenAI are opt-in via env.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Optional


@dataclass
class LLMConfig:
    """Configuration shared by every LLM adapter."""

    # -- Embeddings ---------------------------------------------------- #
    embedding_model: str = "nomic-embed-text"
    embedding_dim: int = 768  # nomic-embed-text output size

    # -- Claude (Anthropic) ------------------------------------------- #
    claude_model: str = "claude-3-5-sonnet-20241022"
    claude_max_tokens: int = 1024
    claude_api_key: Optional[str] = None

    # -- OpenAI ------------------------------------------------------- #
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_max_tokens: int = 1024
    openai_api_key: Optional[str] = None

    # -- Ollama (local, always available) ----------------------------- #
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_embedding_model: str = "nomic-embed-text"

    # -- Generation defaults ------------------------------------------ #
    default_max_tokens: int = 1024
    default_temperature: float = 0.7

    # -- Memory integration ------------------------------------------- #
    context_max_tokens: int = 2000
    search_top_k: int = 5
    min_relevance: float = 0.25

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Build a config from environment variables, falling back to defaults."""
        return cls(
            embedding_model=os.getenv("ARIA_EMBEDDING_MODEL", "nomic-embed-text"),
            embedding_dim=int(os.getenv("ARIA_EMBEDDING_DIM", "768")),
            claude_model=os.getenv("ARIA_CLAUDE_MODEL", cls.claude_model),
            claude_max_tokens=int(os.getenv("ARIA_CLAUDE_MAX_TOKENS", str(cls.claude_max_tokens))),
            claude_api_key=os.getenv("ARIA_CLAUDE_API_KEY"),
            openai_model=os.getenv("ARIA_OPENAI_MODEL", cls.openai_model),
            openai_embedding_model=os.getenv("ARIA_OPENAI_EMBEDDING_MODEL", cls.openai_embedding_model),
            openai_max_tokens=int(os.getenv("ARIA_OPENAI_MAX_TOKENS", str(cls.openai_max_tokens))),
            openai_api_key=os.getenv("ARIA_OPENAI_API_KEY"),
            ollama_url=os.getenv("ARIA_OLLAMA_URL", cls.ollama_url),
            ollama_model=os.getenv("ARIA_OLLAMA_MODEL", cls.ollama_model),
            ollama_embedding_model=os.getenv("ARIA_OLLAMA_EMBEDDING_MODEL", cls.ollama_embedding_model),
            default_max_tokens=int(os.getenv("ARIA_DEFAULT_MAX_TOKENS", str(cls.default_max_tokens))),
            default_temperature=float(os.getenv("ARIA_DEFAULT_TEMPERATURE", str(cls.default_temperature))),
            context_max_tokens=int(os.getenv("ARIA_CONTEXT_MAX_TOKENS", str(cls.context_max_tokens))),
            search_top_k=int(os.getenv("ARIA_SEARCH_TOP_K", str(cls.search_top_k))),
            min_relevance=float(os.getenv("ARIA_MIN_RELEVANCE", str(cls.min_relevance))),
        )


def get_llm_config() -> LLMConfig:
    """Convenience singleton accessor."""
    return LLMConfig.from_env()