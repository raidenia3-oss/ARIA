# -*- coding: utf-8 -*-
"""ARIA OS - Memory Consolidator.

Motor de consolidación de memoria: mueve entradas de corto plazo a largo
plazo basándose en importancia, frecuencia y relevancia.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ARIA.Memory.Consolidator")


class MemoryConsolidator:
    """Consolida memoria: promueve entradas importantes de corto a largo plazo."""

    def __init__(
        self,
        short_term_memory,
        long_term_memory,
        vector_store=None,
        importance_threshold: float = 0.7,
    ) -> None:
        self.stm = short_term_memory
        self.ltm = long_term_memory
        self.vs = vector_store
        self.importance_threshold = importance_threshold
        self._last_consolidation: float = 0.0

    def should_consolidate(self, interval_seconds: float = 300.0) -> bool:
        """Indica si es momento de consolidar."""
        return (time.time() - self._last_consolidation) >= interval_seconds

    def consolidate(
        self,
        interval_seconds: float = 300.0,
        max_promote: int = 10,
    ) -> Dict[str, Any]:
        """Promueve entradas importantes de STM a LTM."""
        if not self.should_consolidate(interval_seconds):
            return {"promoted": 0, "skipped": "not_due"}

        candidates = self.stm.get_by_importance(min_importance=self.importance_threshold)
        promoted = 0
        skipped = 0

        for entry in candidates[:max_promote]:
            # Evitar duplicados
            existing = self.ltm.search(entry.content, top_k=1, min_similarity=0.8)
            if existing:
                skipped += 1
                continue

            summary = entry.content[:200]
            category = self._infer_category(entry.content, entry.metadata)
            entry_id = self.ltm.add(
                content=entry.content,
                summary=summary,
                category=category,
                importance=entry.importance,
                metadata=entry.metadata,
            )

            # También agregar al vector store si está disponible
            if self.vs:
                self.vs.add(entry.content, metadata={"category": category, "source": "short_term"})

            promoted += 1

        self._last_consolidation = time.time()
        logger.info(f"MemoryConsolidator: {promoted} entradas promovidas, {skipped} omitidas")
        return {
            "promoted": promoted,
            "skipped": skipped,
            "consolidated_at": self._last_consolidation,
        }

    @staticmethod
    def _infer_category(content: str, metadata: Dict[str, Any]) -> str:
        """Infere la categoría de una entrada de memoria."""
        text = (content + " " + str(metadata)).lower()
        if any(k in text for k in ["código", "programar", "software", "ia", "inteligencia"]):
            return "tecnología"
        if any(k in text for k in ["aprender", "estudiar", "tutorial", "curso"]):
            return "educativo"
        if any(k in text for k in ["video", "imagen", "foto", "reel"]):
            return "multimedia"
        if any(k in text for k in ["salud", "medicina", "ejercicio"]):
            return "salud"
        return "general"

    def stats(self) -> Dict[str, Any]:
        return {
            "importance_threshold": self.importance_threshold,
            "last_consolidation": self._last_consolidation,
            "stm_entries": self.stm.stats().get("entries", 0),
            "ltm_entries": self.ltm.get_stats().get("total_entries", 0),
        }
