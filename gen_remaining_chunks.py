#!/usr/bin/env python3
"""Genera los archivos restantes de los Chunks 2 y 3."""
from pathlib import Path

BASE = Path(r'C:\Users\User\Downloads\AURA')

# ---------------------------------------------------------------------------
# rag_agent.py (Chunk 2)
# ---------------------------------------------------------------------------
rag_agent_content = """\
# -*- coding: utf-8 -*-
"""AURA OS - Chunk 2: RAG Agent.

Agente de recuperacion de informacion basado en memoria.

Capacidades:
- Busqueda semantica en memoria (corto/medio/largo plazo)
- Respuesta contextual a preguntas
- Integracion con MemoryManager y EventBus
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from backend.memory.memory_manager import get_memory_manager
from backend.core.event_bus import CoreEvent, EventType, get_event_bus

logger = logging.getLogger("AURA.RAGAgent")


class RAGAgent:
    """Agente que busca informacion en la memoria de AURA.

    Combina los tres niveles de memoria del sistema:
    - Short term: conversaciones recientes (ultimas 20)
    - Medium term: persistencia de las ultimas 24 horas
    - Long term: patrones aprendidos permanentemente

    Emite eventos al EventBus para tracking de busquedas.
    """

    def __init__(
        self,
        agent_id: str = "rag_agent",
        top_k_default: int = 5,
    ) -> None:
        """Inicializa el RAGAgent.

        Args:
            agent_id: Identificador unico del agente
            top_k_default: Numero default de resultados a retornar
        """
        self._agent_id = agent_id
        self._top_k_default = top_k_default
        self._search_count: int = 0
        self._last_results: Optional[Dict[str, Any]] = None
        self._total_searches: int = 0
        self._cache: Dict[str, Any] = {}

    async def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        sources: Optional[List[str]] = None,
        cache_enabled: bool = True,
    ) -> Dict[str, Any]:
        """Busca informacion relevante en la memoria disponible.

        Args:
            query: Texto de busqueda
            top_k: Maximos resultados a retornar
            sources: Fuentes de memoria a consultar (short/medium/long)
            cache_enabled: Si se debe usar cache interno

        Returns:
            Dict con resultados y estadisticas de la busqueda
        """
        top_k = top_k or self._top_k_default
        sources = sources or ["short", "medium", "long"]
        cache_key = f"{query}_{top_k}_{'_'.join(sorted(sources))}"

        if cache_enabled and cache_key in self._cache:
            logger.debug(f"RAGAgent: Cache hit para '{query}'")
            return self._cache[cache_key]

        self._search_count += 1
        self._total_searches += 1
        logger.info(f"RAGAgent: Buscando '{query[:50]}...' en {len(sources)} fuentes")

        start_time = time.time()
        results: Dict[str, Any] = {
            "query": query,
            "timestamp": time.time(),
            "searched_by": self._agent_id,
            "sources_consulted": sources,
            "results": [],
            "total_matches": 0,
            "search_duration_ms": 0,
            "errors": [],
        }

        try:
            memory = get_memory_manager()

            if "short" in sources:
                short_data = memory.get_context(query, top_k=top_k)
                results["results"].extend(short_data.get("short_term", []))
                results["results"].extend(short_data.get("medium_term", []))

            if "long" in sources:
                long_patterns = memory.get_long_term_patterns(top_k=top_k)
                long_results = []
                for pattern in long_patterns:
                    if query.lower() in pattern.trigger.lower():
                        long_results.append({
                            "type": "pattern",
                            "trigger": pattern.trigger,
                            "response": pattern.response,
                            "confidence": pattern.confidence,
                            "frequency": pattern.frequency,
                        })
                results["results"].extend(long_results[:top_k])

            results["total_matches"] = len(results["results"])
            results["search_duration_ms"] = round((time.time() - start_time) * 1000, 2)

            if cache_enabled and results["total_matches"] > 0:
                self._cache[cache_key] = results

            self._last_results = results
            logger.debug(f"RAGAgent: {results['total_matches']} resultados para '{query[:30]}'")

        except Exception as e:
            error_msg = f"Error en busqueda: {e}"
            logger.error(error_msg)
            results["errors"].append(error_msg)
            results["search_duration_ms"] = round((time.time() - start_time) * 1000, 2)

        return results

    async def search_detailed(
        self,
        query: str,
        context_size: int = 200,
        include_metadata: bool = True,
    ) -> Dict[str, Any]:
        """Busqueda detallada con contexto expandido y metadata.

        Args:
            query: Texto de busqueda
            context_size: Tamanno maximo del contexto por resultado
            include_metadata: Si incluir metadata de cada resultado

        Returns:
            Dict con resultados detallados y analisis
        """
        basic_results = await self.search(query, top_k=10)

        detailed = {
            "query": query,
            "search_summary": {
                "total_matches": basic_results.get("total_matches", 0),
                "duration_ms": basic_results.get("search_duration_ms", 0),
                "sources": basic_results.get("sources_consulted", []),
            },
            "results": [],
            "analysis": {},
        }

        for result in basic_results.get("results", [])[:5]:
            entry: Dict[str, Any] = {
                "content": result.get("content", "")[:context_size],
                "source": result.get("role", "unknown"),
                "score": result.get("score", 0.0),
            }

            if include_metadata:
                entry["metadata"] = {
                    "timestamp": result.get("timestamp", 0),
                    "type": result.get("type", "unknown"),
                    "match_quality": result.get("score", 0.0),
                }

            detailed["results"].append(entry)

        detailed["analysis"] = {
            "confidence": min(1.0, basic_results.get("total_matches", 0) / 5.0),
            "has_relevant_info": basic_results.get("total_matches", 0) > 0,
            "suggested_follow_up": self._suggest_follow_up(query, basic_results),
        }

        return detailed

    def _suggest_follow_up(self, query: str, results: Dict[str, Any]) -> Optional[str]:
        """Sugiere siguiente accion basada en los resultados."""
        if results.get("total_matches", 0) == 0:
            return f"No se encontro informacion sobre '{query}'. Intentar con terminos alternativos."
        if results.get("total_matches", 0) < 3:
            return f"Se encontraron pocos resultados ({results['total_matches']}). Ampliar la busqueda."
        return "Informacion suficiente encontrada. Proceder con la tarea."

    async def summarize_memory(
        self,
        query: Optional[str] = None,
        max_entries: int = 10,
    ) -> Dict[str, Any]:
        """Resume el contenido de la memoria para el usuario.

        Args:
            query: Filtro opcional para la busqueda
            max_entries: Maximo de entradas a incluir en el resumen

        Returns:
            Dict con el resumen de la memoria
        """
        if query:
            results = await self.search(query, top_k=max_entries)
        else:
            memory = get_memory_manager()
            short = memory.get_short_term(limit=max_entries)
            results = {
                "results": [
                    {"content": e.content, "role": e.role, "timestamp": e.timestamp}
                    for e in short
 
