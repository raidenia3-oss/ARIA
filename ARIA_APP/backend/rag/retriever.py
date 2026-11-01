# -*- coding: utf-8 -*-
"""ARIA OS - Multi-Strategy Retriever.

Estrategias de recuperación:
1. Semántica (vector store)
2. Palabras clave (short-term + long-term)
3. Híbrida (combinación ponderada)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ARIA.RAG.Retriever")


class MultiStrategyRetriever:
    """Retriever con múltiples estrategias de búsqueda."""

    def __init__(
        self,
        short_term_memory,
        long_term_memory,
        vector_store,
    ) -> None:
        self.stm = short_term_memory
        self.ltm = long_term_memory
        self.vs = vector_store

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        include_stm: bool = True,
        include_ltm: bool = True,
        include_vs: bool = True,
    ) -> List[Dict[str, Any]]:
        """Ejecuta todas las estrategias y combina resultados."""
        all_hits: List[Dict[str, Any]] = []

        if include_stm:
            stm_hits = self.stm.search(query, top_k=top_k)
            all_hits.extend(stm_hits)

        if include_ltm:
            ltm_hits = self.ltm.search(query, top_k=top_k)
            all_hits.extend(ltm_hits)

        if include_vs:
            vs_hits = self.vs.search(query, top_k=top_k)
            for h in vs_hits:
                h["source"] = "vector"
                all_hits.append(h)

        # Deduplicar por contenido
        seen = set()
        unique = []
        for h in all_hits:
            key = h.get("content", h.get("summary", ""))[:100]
            if key not in seen:
                seen.add(key)
                unique.append(h)

        # Ordenar por similaridad
        unique.sort(key=lambda h: h.get("similarity", 0), reverse=True)
        return unique[: max(1, top_k)]
