# -*- coding: utf-8 -*-
"""ARIA OS - Cross-Encoder Reranker.

Re-ranking de resultados de búsqueda usando un modelo de puntuación
(cross-encoder simulado o real si está disponible).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger("ARIA.RAG.Reranker")


class CrossEncoderReranker:
    """Re-rankear resultados de búsqueda para mejorar relevancia."""

    def __init__(self) -> None:
        self._model = None
        self._try_load_model()

    def _try_load_model(self) -> None:
        """Intenta cargar un cross-encoder real."""
        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
            logger.info("CrossEncoderReranker: modelo real cargado")
        except Exception as exc:
            logger.debug(f"CrossEncoderReranker: usando puntuación heurística ({exc})")

    def rerank(
        self,
        query: str,
        hits: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Re-rankea hits según relevancia con la consulta."""
        if not hits:
            return hits

        if self._model:
            return self._rerank_with_model(query, hits, top_k)
        return self._rerank_heuristic(query, hits, top_k)

    def _rerank_with_model(
        self,
        query: str,
        hits: List[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """Re-ranking con cross-encoder real."""
        pairs = [(query, h.get("content", h.get("summary", ""))) for h in hits]
        try:
            scores = self._model.predict(pairs)
            for h, score in zip(hits, scores):
                h["rerank_score"] = float(score)
                h["similarity"] = max(h.get("similarity", 0), float(score))
        except Exception as exc:
            logger.debug(f"CrossEncoder predict error: {exc}")

        hits.sort(key=lambda h: h.get("rerank_score", h.get("similarity", 0)), reverse=True)
        return hits[: max(1, top_k)]

    def _rerank_heuristic(
        self,
        query: str,
        hits: List[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """Re-ranking heurístico basado en superposición de tokens."""
        q_tokens = set(query.lower().split())
        for h in hits:
            content = h.get("content", h.get("summary", "")).lower()
            c_tokens = set(content.split())
            if q_tokens and c_tokens:
                overlap = len(q_tokens & c_tokens) / max(1, len(q_tokens | c_tokens))
                h["rerank_score"] = overlap
                h["similarity"] = max(h.get("similarity", 0), overlap)
            else:
                h["rerank_score"] = h.get("similarity", 0)

        hits.sort(key=lambda h: h.get("rerank_score", 0), reverse=True)
        return hits[: max(1, top_k)]
