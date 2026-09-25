# -*- coding: utf-8 -*-
"""ARIA OS - Chunk 2: RAG Agent.

Agente de recuperacion de informacion basado en memoria.
Integra con MemoryManager para busqueda semantica.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from backend.core.event_bus import CoreEvent, EventType, get_event_bus
from backend.memory.memory_manager import MemoryManager, get_memory_manager

logger = logging.getLogger("ARIA.RAGAgent")


class RAGAgent:
    """Agente de recuperacion de informacion en memoria.

    Realiza busqueda semantica en los tres niveles de memoria:
    - Short term: conversaciones recientes
    - Medio term: persistencia de 24h
    - Long term: patrones aprendidos
    """

    def __init__(
        self,
        memory_manager: Optional[MemoryManager] = None,
        event_bus: Optional[Any] = None,
        agent_id: str = "rag_agent",
    ) -> None:
        self._memory = memory_manager or get_memory_manager()
        self._bus = event_bus or get_event_bus()
        self._agent_id = agent_id
        self._last_query_time: float = 0.0
        self._query_count: int = 0

    async def search(
        self,
        query: str,
        top_k: int = 5,
        include_context: bool = True,
    ) -> Dict[str, Any]:
        """Busca informacion relevante en memoria.

        Args:
            query: Consulta de busqueda
            top_k: Numero maximo de resultados
            include_context: Si incluir contexto adicional

        Returns:
            Dict con resultados y metadata
        """
        start_time = time.time()
        self._query_count += 1

        logger.debug(f"RAGAgent: Buscando: {query[:50]}")

        try:
            context = self._memory.get_context(query, top_k=top_k)

            results = {
                "query": query,
                "results": context,
                "total_matches": context.get("total_matches", 0),
                "search_time_ms": round((time.time() - start_time) * 1000, 2),
                "agent_id": self._agent_id,
                "rationale": context.get("rationale", ""),
            }

            if include_context:
                results["context"] = {
                    "short_term": context.get("short_term", []),
                    "medium_term": context.get("medium_term", []),
                    "long_term": context.get("long_term", []),
                }

            self._last_query_time = time.time()

            return results

        except Exception as e:
            logger.error(f"RAGAgent: Error en busqueda: {e}")
            return {
                "query": query,
                "results": [],
                "total_matches": 0,
                "search_time_ms": round((time.time() - start_time) * 1000, 2),
                "agent_id": self._agent_id,
                "error": str(e),
            }

    async def search_and_respond(self, query: str) -> str:
        """Busca y retorna respuesta formateada.

        Args:
            query: Consulta del usuario

        Returns:
            Respuesta en texto plano
        """
        results = await self.search(query, top_k=5)

        if not results.get("results", {}).get("total_matches", 0):
            return "No encontre informacion relevante en mi memoria."

        rationale = results.get("rationale", "")
        matches = results["results"].get("total_matches", 0)

        response = f"Encontre {matches} coincidencia(s): {rationale}."

        short_term = results["results"].get("short_term", [])
        for item in short_term[:3]:
            response += (
                "\n  - [" + str(item.get("role", "")) + "] " + str(item.get("content", ""))[:100]
            )

        return response

    def get_status(self) -> Dict[str, Any]:
        """Retorna estado del agente."""
        return {
            "agent_id": self._agent_id,
            "query_count": self._query_count,
            "last_query_time": self._last_query_time,
            "memory_sources": ["short_term", "medium_term", "long_term"],
        }


def get_rag_agent() -> RAGAgent:
    """Retorna instancia global del RAGAgent."""
    if not hasattr(get_rag_agent, "_instance"):
        get_rag_agent._instance = RAGAgent()
    return get_rag_agent._instance


def reset_rag_agent() -> None:
    """Resetea la instancia global."""
    if hasattr(get_rag_agent, "_instance"):
        delattr(get_rag_agent, "_instance")


if __name__ == "__main__":
    import asyncio

    async def test():
        agent = get_rag_agent()
        results = await agent.search("Hola")
        print("RAGAgent:", results.get("total_matches", 0), "resultados")
        print(agent.get_status())
        print("rag_agent.py OK")

    asyncio.run(test())
