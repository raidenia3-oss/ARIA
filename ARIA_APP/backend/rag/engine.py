# -*- coding: utf-8 -*-
"""ARIA OS - Enhanced RAG Engine.

Motor RAG principal que combina:
- Búsqueda semántica vectorial
- Búsqueda por palabras clave
- Re-ranking con cross-encoder
- Inyección de contexto en prompts
- Soporte multi-modal (texto, imagen, video)
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from backend.memory.vector_store import VectorMemoryStore
from backend.memory.long_term import LongTermMemory
from backend.memory.short_term import ShortTermMemory
from backend.memory.consolidation import MemoryConsolidator
from backend.ai.models import AIModelManager, ModelType
from .retriever import MultiStrategyRetriever
from .reranker import CrossEncoderReranker
from .multimodal import MultimodalRAG

logger = logging.getLogger("ARIA.RAG.Engine")


class EnhancedRAG:
    """Motor RAG mejorado con múltiples capas de recuperación."""

    def __init__(
        self,
        data_dir: str = "data/rag",
        model_manager: Optional[AIModelManager] = None,
    ) -> None:
        self.data_dir = data_dir
        self.model_manager = model_manager or AIModelManager()

        # Capas de memoria
        self.stm = ShortTermMemory(max_entries=100)
        self.ltm = LongTermMemory(data_dir=f"{data_dir}/long_term")
        self.vs = VectorMemoryStore(data_dir=f"{data_dir}/vector")
        self.consolidator = MemoryConsolidator(self.stm, self.ltm, self.vs)

        # Componentes RAG
        self.retriever = MultiStrategyRetriever(self.stm, self.ltm, self.vs)
        self.reranker = CrossEncoderReranker()
        self.multimodal = MultimodalRAG(self.model_manager)

    # ------------------------------------------------------------------ #
    # Ingestión
    # ------------------------------------------------------------------ #
    def add_text(
        self,
        content: str,
        source: str = "user",
        metadata: Optional[Dict[str, Any]] = None,
        importance: float = 0.5,
    ) -> Dict[str, Any]:
        """Agrega texto al sistema RAG (memoria corta + vector)."""
        # Memoria corta
        self.stm.add("user" if source == "user" else "assistant", content,
                     metadata=metadata or {}, importance=importance)

        # Vector store
        entry_id = self.vs.add(content, metadata={"source": source, **(metadata or {})})

        # Consolidar si es momento
        consolidated = self.consolidator.consolidate()

        return {
            "entry_id": entry_id,
            "stm_entries": self.stm.stats()["entries"],
            "consolidated": consolidated.get("promoted", 0),
        }

    def add_conversation(
        self,
        user_message: str,
        assistant_response: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Agrega una conversación completa al RAG."""
        meta = metadata or {}
        self.add_text(user_message, source="user", metadata=meta, importance=0.6)
        self.add_text(assistant_response, source="assistant", metadata=meta, importance=0.7)
        return {"status": "ok"}

    # ------------------------------------------------------------------ #
    # Recuperación
    # ------------------------------------------------------------------ #
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        use_reranker: bool = True,
        include_short_term: bool = True,
        include_long_term: bool = True,
        include_vector: bool = True,
    ) -> Dict[str, Any]:
        """Recupera contexto relevante para una consulta."""
        hits = self.retriever.retrieve(
            query,
            top_k=top_k,
            include_stm=include_short_term,
            include_ltm=include_long_term,
            include_vs=include_vector,
        )

        if use_reranker and hits:
            hits = self.reranker.rerank(query, hits, top_k=top_k)

        # Construir contexto para prompt
        context = self._build_context(hits)

        return {
            "query": query,
            "hits": hits,
            "context": context,
            "total_hits": len(hits),
        }

    def retrieve_for_chat(
        self,
        user_message: str,
        history: Optional[List[List[str]]] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """Recupera contexto optimizado para chat."""
        # Agregar mensaje actual a STM
        self.stm.add("user", user_message, importance=0.6)

        # Recuperar
        result = self.retrieve(user_message, top_k=top_k)

        # Agregar historial reciente al contexto
        if history:
            recent = self.stm.get_recent(limit=10)
            history_text = "\n".join(
                f"{e.role}: {e.content}" for e in recent[-6:]
            )
            result["recent_history"] = history_text

        return result

    # ------------------------------------------------------------------ #
    # Multi-modal RAG
    # ------------------------------------------------------------------ #
    def retrieve_multimodal(
        self,
        query: str,
        image_paths: Optional[List[str]] = None,
        video_info: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """Recuperación multi-modal: texto + imágenes + video."""
        # Recuperación de texto normal
        text_result = self.retrieve(query, top_k=top_k)

        # Procesar imágenes y video con el modelo multimodal
        mm_results = self.multimodal.process(
            query=query,
            image_paths=image_paths,
            video_info=video_info,
        )

        return {
            "query": query,
            "text_hits": text_result["hits"],
            "text_context": text_result["context"],
            "multimodal": mm_results,
            "total_hits": text_result["total_hits"],
        }

    # ------------------------------------------------------------------ #
    # Contexto
    # ------------------------------------------------------------------ #
    def _build_context(self, hits: List[Dict[str, Any]]) -> str:
        """Construye string de contexto a partir de hits."""
        if not hits:
            return ""
        lines = ["[CONTEXTO RECUPERADO]"]
        for h in hits:
            source = h.get("source", "unknown")
            content = h.get("content", h.get("summary", ""))[:200]
            sim = h.get("similarity", 0)
            lines.append(f"- [{source}] sim={sim:.2f}: {content}")
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Stats
    # ------------------------------------------------------------------ #
    def stats(self) -> Dict[str, Any]:
        return {
            "stm": self.stm.stats(),
            "ltm": self.ltm.get_stats(),
            "vector": self.vs.get_stats(),
            "consolidator": self.consolidator.stats(),
        }
