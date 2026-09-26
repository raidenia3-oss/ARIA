# -*- coding: utf-8 -*-
"""AURA OS - Advanced RAG Engine.

Busca contexto semántico en ChromaDB + sentence-transformers
e inyecta en prompts para respuestas personalizadas.
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("AURA.AdvancedRAG")

# Lazy imports (no rompen el arranque)
_chroma = None
_st = None
_collection = None
_embed_fn = None


def _init_chroma():
    """Lazy init de ChromaDB."""
    global _chroma, _collection
    if _chroma is not None:
        return True
    try:
        import chromadb
        _chroma = chromadb
        # Usar directorio temporal para evitar locks del proceso principal
        import tempfile
        persist_dir = os.path.join(tempfile.gettempdir(), "aura_rag_chroma")
        os.makedirs(persist_dir, exist_ok=True)
        client = chromadb.PersistentClient(path=persist_dir)
        _collection = client.get_or_create_collection(
            name="aura_rag_inteligente",
            metadata={"hnsw:space": "cosine"},
        )
        return True
    except Exception as exc:
        logger.warning("ChromaDB init fallo: %s", exc)
        return False


def _init_embeddings():
    """Lazy init de sentence-transformers."""
    global _embed_fn
    if _embed_fn is not None:
        return True
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        _embed_fn = lambda texts: model.encode(texts, convert_to_numpy=True).tolist()
        return True
    except Exception as exc:
        logger.warning("SentenceTransformer init fallo: %s", exc)
        return False


def _embed(texts: List[str]):
    """Genera embeddings para una lista de textos."""
    if not _init_embeddings():
        return None
    try:
        return _embed_fn(texts)
    except Exception as exc:
        logger.debug("embed fallo: %s", exc)
        return None


class AdvancedRAG:
    """Motor RAG semántico: indexa conversaciones y busca contexto similar."""

    def __init__(self, collection_name: str = "aura_conversations") -> None:
        self.collection_name = collection_name
        self._collection = None
        self._ready = False

    def _ensure(self) -> bool:
        """Asegura ChromaDB + embeddings listos."""
        if self._ready:
            return True
        if not _init_chroma():
            return False
        if not _init_embeddings():
            return False
        self._collection = _collection
        self._ready = True
        return True

    def index(
        self,
        text: str,
        chat_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Indexa un fragmento de conversación en el vector store."""
        if not self._ensure():
            return False
        try:
            doc_id = hashlib.md5(f"{chat_id}:{text}".encode()).hexdigest()[:16]
            vecs = _embed([text])
            if not vecs:
                return False
            meta = dict(metadata or {})
            meta["chat_id"] = chat_id
            meta["ts"] = time.time()
            meta["text_preview"] = text[:200]
            self._collection.add(
                ids=[doc_id],
                embeddings=[vecs[0]],
                documents=[text],
                metadatas=[meta],
            )
            return True
        except Exception as exc:
            logger.debug("index fallo: %s", exc)
            return False

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """Búsqueda semántica: retorna [{chat_id, similarity, snippet, metadata}]."""
        if not self._ensure():
            return []
        try:
            qvecs = _embed([query])
            if not qvecs:
                return []
            results = self._collection.query(
                query_embeddings=[qvecs[0]],
                n_results=min(top_k, 10),
                include=["documents", "metadatas", "distances"],
            )
            out: List[Dict[str, Any]] = []
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            dists = results.get("distances", [[]])[0]
            for doc, meta, dist in zip(docs, metas, dists):
                sim = max(0.0, 1.0 - float(dist))  # cosine distance → similarity
                if sim < min_similarity:
                    continue
                out.append({
                    "chat_id": meta.get("chat_id", ""),
                    "similarity": round(sim, 4),
                    "snippet": (doc or "")[:300],
                    "metadata": meta,
                })
            return out
        except Exception as exc:
            logger.debug("search fallo: %s", exc)
            return []

    def build_context(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.5,
    ) -> str:
        """Construye un string de contexto inyectable en prompts."""
        hits = self.search(query, top_k=top_k, min_similarity=min_similarity)
        if not hits:
            return ""
        lines = ["[CONTEXTO RAG - conversaciones previas similares]"]
        for h in hits:
            lines.append(
                f"- chat_id={h['chat_id']} sim={h['similarity']:.2f}: {h['snippet'][:200]}"
            )
        return "\n".join(lines)

    def stats(self) -> Dict[str, Any]:
        """Estadísticas del índice."""
        if not self._ensure():
            return {"ready": False, "count": 0}
        try:
            return {"ready": True, "count": self._collection.count()}
        except Exception:
            return {"ready": True, "count": 0}

    def reset(self) -> bool:
        """Reinicia el índice (no implementado en PersistentClient)."""
        return False


# Singleton
_rag: Optional[AdvancedRAG] = None


def get_rag() -> AdvancedRAG:
    global _rag
    if _rag is None:
        _rag = AdvancedRAG()
    return _rag


def reset_rag() -> None:
    global _rag
    _rag = None