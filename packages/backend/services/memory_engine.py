"""Memory Engine for AURA - Vector RAG and long-term memory store.

- Embeddings: Ollama endpoint > FastEmbed > SentenceTransformers > TF-IDF fallback
- Vector store: ChromaDB (persistent), with cosine similarity
- Memory types: episodic (conversation), semantic (preferences), procedural (notes)
- Temporal weighting and relevance filtering
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("AURAMemoryEngine")

OLLAMA_EMBEDDING_URL = os.getenv("OLLAMA_EMBEDDING_URL", "http://localhost:11434/api/embeddings")
OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
CHROMA_DB_PATH = os.getenv("AURA_MEMORY_DB", "./aura_memory_db")
MEMORY_COLLECTION = "aura_memories"
RECENCY_DECAY_HOURS = 24.0
RECENCY_DECAY_FACTOR = 0.95
MAX_MEMORIES_PER_QUERY = 10
RELEVANCE_THRESHOLD = 0.25


@dataclass
class MemoryRecord:
    memory_id: str
    text: str
    embedding: Optional[List[float]] = None
    memory_type: str = "episodic"
    source: str = "user"
    session_id: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    relevance_score: float = 0.0
    recency_score: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "text": self.text,
            "memory_type": self.memory_type,
            "source": self.source,
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
            "relevance_score": self.relevance_score,
            "recency_score": self.recency_score,
        }


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    if a.ndim == 1:
        a = a.reshape(1, -1)
    if b.ndim == 1:
        b = b.reshape(1, -1)
    dot = np.dot(a, b.T)
    norm_a = np.linalg.norm(a, axis=1, keepdims=True)
    norm_b = np.linalg.norm(b, axis=1, keepdims=True)
    denom = norm_a * norm_b.T
    denom[denom == 0] = 1e-10
    return float(np.max(dot / denom))


def _simple_tfidf_embed(texts: List[str], n_features: int = 256) -> np.ndarray:
    vocab: Dict[str, int] = {}
    for text in texts:
        for token in re.findall(r"\w+", text.lower()):
            if token not in vocab:
                vocab[token] = len(vocab)
    matrix = np.zeros((len(texts), min(n_features, max(1, len(vocab)))), dtype=np.float32)
    for i, text in enumerate(texts):
        tokens = re.findall(r"\w+", text.lower())
        for token in tokens:
            idx = vocab.get(token)
            if idx is not None and idx < matrix.shape[1]:
                matrix[i, idx] += 1
    row_sums = matrix.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1.0
    matrix = matrix / row_sums
    return matrix


class EmbeddingProvider:
    def __init__(self) -> None:
        self._model = None
        self._try_load_local()

    def _try_load_local(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception:
            self._model = None

    def embed(self, text: str) -> List[float]:
        if self._model is not None:
            try:
                return self._model.encode(text, normalize_embeddings=True).tolist()
            except Exception:
                pass
        try:
            import requests as req
            payload = {"model": OLLAMA_EMBEDDING_MODEL, "prompt": text}
            resp = req.post(OLLAMA_EMBEDDING_URL, json=payload, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                vec = data.get("embedding", [])
                if vec:
                    norm = sum(v * v for v in vec) ** 0.5
                    if norm > 0:
                        vec = [v / norm for v in vec]
                    return vec
        except Exception:
            pass
        try:
            import fastembed
            model = fastembed.TextEmbedding("all-MiniLM-L6-v2")
            vec = next(model.embed([text]))
            norm = sum(v * v for v in vec) ** 0.5
            if norm > 0:
                vec = [v / norm for v in vec]
            return vec
        except Exception:
            pass
        vecs = _simple_tfidf_embed([text])
        vec = vecs[0].tolist() if len(vecs) else [0.0] * 256
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if self._model is not None:
            try:
                return self._model.encode(texts, normalize_embeddings=True).tolist()
            except Exception:
                pass
        return [self.embed(t) for t in texts]


class MemoryStore:
    def __init__(self, db_path: str = CHROMA_DB_PATH) -> None:
        self._lock = threading.Lock()
        self._memories: Dict[str, MemoryRecord] = {}
        self._load_chroma(db_path)

    def _load_chroma(self, db_path: str) -> None:
        try:
            import chromadb
            self._client = chromadb.PersistentClient(path=db_path)
            self._collection = self._client.get_or_create_collection(
                name=MEMORY_COLLECTION,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:
            logger.debug("ChromaDB init failed: %s", exc)
            self._client = None
            self._collection = None

    def _chroma_upsert(self, record: MemoryRecord) -> None:
        if self._collection is None:
            return
        try:
            self._collection.upsert(
                documents=[record.text],
                embeddings=[record.embedding or [0.0] * 256],
                metadatas=[{
                    "memory_type": record.memory_type,
                    "source": record.source,
                    "session_id": record.session_id,
                    "created_at": record.created_at,
                    "updated_at": record.updated_at,
                    "metadata": json.dumps(record.metadata),
                }],
                ids=[record.memory_id],
            )
        except Exception as exc:
            logger.debug("Chroma upsert failed: %s", exc)

    def _chroma_query(self, query_embedding: List[float], n_results: int = MAX_MEMORIES_PER_QUERY) -> List[Tuple[str, float]]:
        if self._collection is None:
            return []
        try:
            result = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                include=["distances"],
            )
            ids = result.get("ids", [[]])[0]
            distances = result.get("distances", [[]])[0]
            return list(zip(ids, [1.0 - d for d in distances]))
        except Exception as exc:
            logger.debug("Chroma query failed: %s", exc)
            return []

    def add(self, record: MemoryRecord) -> None:
        with self._lock:
            self._memories[record.memory_id] = record
            self._chroma_upsert(record)

    def update(self, memory_id: str, **kwargs) -> Optional[MemoryRecord]:
        with self._lock:
            record = self._memories.get(memory_id)
            if not record:
                return None
            for key, value in kwargs.items():
                if hasattr(record, key):
                    setattr(record, key, value)
            record.updated_at = time.time()
            self._chroma_upsert(record)
            return record

    def delete(self, memory_id: str) -> bool:
        with self._lock:
            record = self._memories.pop(memory_id, None)
            if record is None:
                return False
            if self._collection is not None:
                try:
                    self._collection.delete(ids=[memory_id])
                except Exception:
                    pass
            return True

    def get(self, memory_id: str) -> Optional[MemoryRecord]:
        return self._memories.get(memory_id)

    def search(self, query_embedding: List[float], max_results: int = MAX_MEMORIES_PER_QUERY, min_relevance: float = RELEVANCE_THRESHOLD) -> List[MemoryRecord]:
        results = self._chroma_query(query_embedding, n_results=max_results * 2)
        now = time.time()
        scored: List[Tuple[MemoryRecord, float]] = []
        for mem_id, similarity in results:
            record = self._memories.get(mem_id)
            if not record:
                continue
            age_hours = (now - record.created_at) / 3600.0
            recency = RECENCY_DECAY_FACTOR ** (age_hours / RECENCY_DECAY_HOURS)
            record.recency_score = recency
            record.relevance_score = similarity
            combined = (similarity * 0.7) + (recency * 0.3)
            if combined >= min_relevance:
                scored.append((record, combined))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [r for r, _ in scored[:max_results]]

    def list_all(self, memory_type: Optional[str] = None, source: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            records = list(self._memories.values())
        if memory_type:
            records = [r for r in records if r.memory_type == memory_type]
        if source:
            records = [r for r in records if r.source == source]
        records.sort(key=lambda r: r.updated_at, reverse=True)
        return [r.to_dict() for r in records[:limit]]

    def count(self) -> int:
        with self._lock:
            return len(self._memories)


class MemoryEngine:
    def __init__(self, orchestrator: Any = None) -> None:
        self.orchestrator = orchestrator
        self._embedding_provider = EmbeddingProvider()
        self._store = MemoryStore()
        self._recent_queries: List[Dict[str, Any]] = []

    def remember(self, text: str, memory_type: str = "episodic", source: str = "user", session_id: str = "", metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not text or not text.strip():
            return {"status": "error", "error": "empty_text"}
        memory_id = hashlib.sha256(f"{text}:{time.time()}".encode("utf-8")).hexdigest()[:24]
        embedding = self._embedding_provider.embed(text)
        record = MemoryRecord(
            memory_id=memory_id,
            text=text.strip(),
            embedding=embedding,
            memory_type=memory_type,
            source=source,
            session_id=session_id or "",
            metadata=metadata or {},
        )
        self._store.add(record)
        return {"status": "ok", "memory_id": memory_id, "type": memory_type}

    def search(self, query: str, max_results: int = MAX_MEMORIES_PER_QUERY, min_relevance: float = RELEVANCE_THRESHOLD) -> Dict[str, Any]:
        if not query or not query.strip():
            return {"status": "error", "error": "empty_query"}
        query_embedding = self._embedding_provider.embed(query.strip())
        results = self._store.search(query_embedding, max_results=max_results, min_relevance=min_relevance)
        self._recent_queries.append({"query": query, "count": len(results), "timestamp": time.time()})
        self._recent_queries = self._recent_queries[-20:]
        return {
            "status": "ok",
            "query": query,
            "count": len(results),
            "results": [r.to_dict() for r in results],
        }

    def forget(self, memory_id: str) -> Dict[str, Any]:
        deleted = self._store.delete(memory_id)
        return {"status": "ok" if deleted else "not_found", "memory_id": memory_id, "deleted": deleted}

    def inject_context(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        result = self.search(query, max_results=max_results)
        context = []
        for mem in result.get("results", []):
            context.append({
                "memory_id": mem.get("memory_id"),
                "text": mem.get("text"),
                "score": mem.get("relevance_score", 0.0),
                "recency": mem.get("recency_score", 0.0),
                "type": mem.get("memory_type"),
            })
        if self.orchestrator and hasattr(self.orchestrator, "set_memory_context"):
            try:
                self.orchestrator.set_memory_context(context)
            except Exception:
                pass
        return context

    def get_status(self) -> Dict[str, Any]:
        return {
            "total_memories": self._store.count(),
            "recent_queries": self._recent_queries[-5:],
            "embedding_backend": "ollama" if OLLAMA_EMBEDDING_URL else "fallback",
            "vector_store": "chromadb",
        }
