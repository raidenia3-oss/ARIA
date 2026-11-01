# -*- coding: utf-8 -*-
"""ARIA OS - Vector Memory Store.

Almacenamiento vectorial para memoria semántica.
Usa sentence-transformers + ChromaDB si están disponibles, fallback a JSON.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ARIA.Memory.VectorStore")


@dataclass
class VectorEntry:
    """Entrada en el vector store."""
    entry_id: str
    content: str
    embedding: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class VectorMemoryStore:
    """Almacén vectorial con fallback a búsqueda por similitud de coseno simple."""

    def __init__(self, data_dir: str = "data/memory/vector") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._entries: Dict[str, VectorEntry] = {}
        self._embed_model = None
        self._init_embeddings()
        self._load()

    def _init_embeddings(self) -> None:
        """Intenta cargar sentence-transformers para embeddings reales."""
        try:
            from sentence_transformers import SentenceTransformer
            self._embed_model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("VectorMemoryStore: sentence-transformers cargado")
        except Exception as exc:
            logger.debug(f"VectorMemoryStore: sin embeddings reales ({exc})")

    def _embed(self, text: str) -> List[float]:
        """Genera embedding para un texto."""
        if self._embed_model:
            try:
                return self._embed_model.encode([text])[0].tolist()
            except Exception as exc:
                logger.debug(f"Embedding error: {exc}")
        # Deterministic fallback: hash-based pseudo-embedding
        h = hashlib.md5(text.encode()).hexdigest()
        vec = [float(int(h[i:i+2], 16)) / 255.0 for i in range(0, 32, 2)]
        # Pad to 384 dims
        while len(vec) < 384:
            vec.extend(vec[: min(len(vec), 384 - len(vec))])
        return vec[:384]

    def add(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Agrega una entrada con su embedding."""
        entry_id = hashlib.md5(f"{content}:{time.time()}".encode()).hexdigest()[:16]
        embedding = self._embed(content)
        entry = VectorEntry(
            entry_id=entry_id,
            content=content,
            embedding=embedding,
            metadata=metadata or {},
        )
        self._entries[entry_id] = entry
        self._save()
        return entry_id

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """Búsqueda por similitud de coseno."""
        if not self._entries:
            return []
        q_emb = self._embed(query)
        results = []
        for entry in self._entries.values():
            sim = self._cosine_similarity(q_emb, entry.embedding)
            if sim >= min_similarity:
                results.append({
                    "entry_id": entry.entry_id,
                    "content": entry.content,
                    "similarity": round(sim, 4),
                    "metadata": entry.metadata,
                })
        results.sort(key=lambda r: r["similarity"], reverse=True)
        return results[: max(1, top_k)]

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        if len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(x * x for x in b) ** 0.5
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "entries": len(self._entries),
            "has_real_embeddings": self._embed_model is not None,
            "data_dir": str(self.data_dir),
        }

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    def _file(self) -> Path:
        return self.data_dir / "vector_store.json"

    def _load(self) -> None:
        pf = self._file()
        if not pf.exists():
            return
        try:
            raw = json.loads(pf.read_text(encoding="utf-8"))
            self._entries = {
                d["entry_id"]: VectorEntry(**d) for d in raw
            }
            logger.info(f"VectorMemoryStore: {len(self._entries)} entradas cargadas")
        except Exception as exc:
            logger.warning(f"Error loading vector store: {exc}")

    def _save(self) -> None:
        pf = self._file()
        try:
            pf.write_text(
                json.dumps([e.__dict__ for e in self._entries.values()], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning(f"Error saving vector store: {exc}")
