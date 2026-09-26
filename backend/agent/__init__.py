# -*- coding: utf-8 -*-
"""
AURA OS - Chunk 2: Agent package.

Contiene la base de agentes (swarm_base) y agentes especializados:
  - BaseAgent  (clase base)
  - RAGAgent   (retrieval / memoria)
  - ExecutorAgent (comandos locales + APIs)
  - WriterAgent (generacion de texto vía Jan / fallback local)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.agent.swarm_base import AgentRegistry, BaseAgent
    from backend.agent.rag_agent import RAGAgent
    from backend.agent.executor_agent import ExecutorAgent
    from backend.agent.writer_agent import WriterAgent

__all__ = [
    "AgentRegistry",
    "BaseAgent",
    "RAGAgent",
    "ExecutorAgent",
    "WriterAgent",
]

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
