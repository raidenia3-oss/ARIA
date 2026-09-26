"""AURA Local Vector Knowledge Base & Advanced RAG Pipeline Engine (BLOQUE 72).

Subsistema backend 100%% local para indexar, consultar y recuperar fragmentos
de documentacion, manuales, guias y datos de investigacion de forma semantica
sin dependencias de nube.

Arquitectura:
- KnowledgeVectorizer: feature hashing + char n-grams sobre NumPy (offline).
- KnowledgeStore: persistencia JSON on-disk (base64 de vectores).
- RAGEngine: index/search/inject/purge/reset thread-safe.
- REST en /api/knowledge (router separado, montado en app.py).
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

import numpy as np

from backend.knowledge.models import (
    CollectionInfo,
    CollectionStatus,
    DocumentStatus,
    IndexStrategy,
    KnowledgeDocument,
    RAGConfig,
    RAGStatus,
    SearchHit,
    SearchRequest,
    SearchResponse,
)
from fastapi import APIRouter, HTTPException, Query  # noqa: F401
from pydantic import BaseModel  # noqa: F401

_KB_DIR = os.getenv("AURA_KNOWLEDGE_DIR", str(Path(__file__).resolve().parent.parent / "knowledge_db"))
_KB_DIR = str(Path(_KB_DIR).resolve())
_COLLECTIONS_DIR = os.path.join(_KB_DIR, "collections")
_INDEX_FILENAME = "index.json"
_CHUNK_SIZE = int(os.getenv("AURA_KB_CHUNK_SIZE", "200"))
_CHUNK_OVERLAP = int(os.getenv("AURA_KB_CHUNK_OVERLAP", "50"))
_DEFAULT_DIM = int(os.getenv("AURA_KB_DIM", "512"))
_NGRAM_N = int(os.getenv("AURA_KB_NGRAM", "4"))

_KB_STOP = frozenset(
    "de la que e el y a los del se las por un para con una su al lo un como le ya o va mas "
    "entre cuando hasta no todo uno les ti eso esto estos esas aquellos toda lugar otra "
    "otro otros donde quien que cual como cuando cuanto este esta estoy estas estamos estan "
    "ser para saber si no the and a an of to in for on with at by from up about into "
    "over under again further then once here there when where why how all any both each "
    "few more most other some such no nor not only own same so than too very s t can will "
    "just should now".split()
)

_WORD_RE = re.compile(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]+")


def chunk_text(
    text: str,
    strategy: str = IndexStrategy.RECURSIVE,
    chunk_size: int = _CHUNK_SIZE,
    chunk_overlap: int = _CHUNK_OVERLAP,
) -> List[str]:
    """Fragmenta texto segun la estrategia indicada."""
    text = (text or "").strip()
    if not text:
        return []
    if strategy == IndexStrategy.PARAGRAPH:
        parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        return parts if parts else [text]
    if strategy == IndexStrategy.SENTENCE:
        parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        return parts if parts else [text]
    if strategy == IndexStrategy.FIXED:
        step = max(1, chunk_size - chunk_overlap)
        chunks: List[str] = []
        for start in range(0, len(text), step):
            chunks.append(text[start : start + chunk_size].strip())
            if start + chunk_size >= len(text):
                break
        return [c for c in chunks if c]
    # RECURSIVE: intenta parrafo; si muy largo,分裂a oracion; si todavia grande, fixed.
    parts: List[str] = []
    for para in [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]:
        if len(para) <= chunk_size:
            parts.append(para)
            continue
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", para) if s.strip()]
        cur = ""
        for s in sents:
            if not cur:
                cur = s
            elif len(cur) + 1 + len(s) <= chunk_size:
                cur = cur + " " + s
            else:
                parts.append(cur)
                cur = s
        if cur:
            parts.append(cur)
    out: List[str] = []
    for p in parts:
        if len(p) <= chunk_size:
            out.append(p)
        else:
            step = max(1, chunk_size - chunk_overlap)
            for start in range(0, len(p), step):
                out.append(p[start : start + chunk_size].strip())
    return [c for c in out if c]


def _vec_to_b64(vec: np.ndarray) -> str:
    return base64.b64encode(np.asarray(vec, dtype=np.float32).tobytes()).decode("ascii")


def _b64_to_vec(b64: str, dim: int) -> np.ndarray:
    raw = base64.b64decode(b64)
    return np.frombuffer(raw, dtype=np.float32).astype(np.float64)


def _now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


def _ensure_collections_dir() -> None:
    Path(_COLLECTIONS_DIR).mkdir(parents=True, exist_ok=True)


class KnowledgeVectorizer:
    """Vectorizador local offline basado en feature hashing (sin red)."""

    def __init__(self, dim: int = _DEFAULT_DIM, n: int = _NGRAM_N) -> None:
        if dim <= 0:
            raise ValueError("dim must be positive")
        self.dim = dim
        self.n = n

    @staticmethod
    def _word_tokens(text: str) -> List[str]:
        return [t.lower() for t in _WORD_RE.findall(text)]

    def _char_ngrams(self, text: str) -> List[str]:
        t = text.lower()
        n = self.n
        if len(t) < n:
            return [t] if t else []
        return [t[i : i + n] for i in range(len(t) - n + 1)]

    def _token_sign(self, token: str) -> int:
        h = hashlib_md5(token)
        return 1 if (h[0] & 1) == 0 else -1

    def _token_bin(self, token: str) -> int:
        h = hashlib_md5(token)
        return int.from_bytes(h[:8], "little") % self.dim

    def vectorize(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float64)
        if not text:
            return self._normalize(vec)
        for tok in self._word_tokens(text):
            if tok in _KB_STOP or len(tok) < 2:
                continue
            vec[self._token_bin(tok)] += self._token_sign(tok)
        for gram in self._char_ngrams(text):
            vec[self._token_bin(gram)] += self._token_sign(gram)
        return self._normalize(vec)

    @staticmethod
    def _normalize(vec: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(vec)
        if norm > 0:
            return vec / norm
        return vec


def hashlib_md5(token: str) -> bytes:
    import hashlib

    return hashlib.md5(token.encode("utf-8", errors="ignore")).digest()


@dataclass
class _Fragment:
    chunk_id: str
    doc_id: str
    collection_id: str
    text: str
    vector_b64: str
    title: str = ""
    source_type: str = "manual"
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0


class KnowledgeStore:
    """Persistencia JSON on-disk para colecciones de conocimiento."""

    def __init__(self, store_dir: Optional[str] = None) -> None:
        self.store_dir = str(store_dir or _COLLECTIONS_DIR)
        Path(self.store_dir).mkdir(parents=True, exist_ok=True)

    def _coll_dir(self, collection_id: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9_-]", "_", collection_id)
        return os.path.join(self.store_dir, safe)

    def _index_path(self, collection_id: str) -> str:
        return os.path.join(self._coll_dir(collection_id), _INDEX_FILENAME)

    def collection_exists(self, collection_id: str) -> bool:
        return os.path.isdir(self._coll_dir(collection_id))

    def list_collections(self) -> List[str]:
        if not os.path.isdir(self.store_dir):
            return []
        out = []
        for entry in os.listdir(self.store_dir):
            full = os.path.join(self.store_dir, entry)
            if os.path.isdir(full) and os.path.exists(os.path.join(full, _INDEX_FILENAME)):
                out.append(entry)
        return sorted(out)

    def save_collection(self, collection_id: str, data: Dict[str, Any]) -> None:
        cdir = self._coll_dir(collection_id)
        Path(cdir).mkdir(parents=True, exist_ok=True)
        path = self._index_path(collection_id)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    def load_collection(self, collection_id: str) -> Optional[Dict[str, Any]]:
        path = self._index_path(collection_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def delete_collection(self, collection_id: str) -> bool:
        cdir = self._coll_dir(collection_id)
        if not os.path.isdir(cdir):
            return False
        shutil.rmtree(cdir, ignore_errors=True)
        return True

class RAGEngine:
    def __init__(self, store_dir=None, config=None, vectorizer=None):
        self.config = config or RAGConfig(store_dir=store_dir or _KB_DIR)
        self.store = KnowledgeStore(store_dir=self.config.store_dir)
        self.vectorizer = vectorizer or KnowledgeVectorizer(dim=self.config.dim, n=self.config.ngram_n)
        self._lock = threading.RLock()

    def _coll_dir(self, collection_id):
        safe = re.sub(r"[^A-Za-z0-9_-]", "_", collection_id)
        return os.path.join(self.store.store_dir, safe)

    def _index_path(self, collection_id):
        return os.path.join(self._coll_dir(collection_id), _INDEX_FILENAME)

    def _load_index(self, collection_id):
        path = self._index_path(collection_id)
        if not os.path.exists(path):
            return {"collection_id": collection_id, "dim": self.vectorizer.dim, "fragments": [], "status": "empty", "strategy": "recursive", "documents": {}}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"collection_id": collection_id, "dim": self.vectorizer.dim, "fragments": [], "status": "error", "strategy": "recursive", "documents": {}}

    def _save_index(self, collection_id, data):
        cdir = self._coll_dir(collection_id)
        Path(cdir).mkdir(parents=True, exist_ok=True)
        path = self._index_path(collection_id)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    def list_collections(self):
        return self.store.list_collections()

    def create_collection(self, collection_id, name="", description="", metadata=None):
        if not collection_id:
            return {"status": "error", "detail": "collection_id required"}
        safe = re.sub(r"[^A-Za-z0-9_-]", "_", collection_id)
        if self.store.collection_exists(safe):
            return {"status": "exists", "collection_id": safe}
        data = {
            "collection_id": safe,
            "name": name or safe,
            "description": description,
            "metadata": metadata or {},
            "dim": self.vectorizer.dim,
            "strategy": "recursive",
            "status": "empty",
            "documents": {},
            "fragments": [],
            "created_at": _now_ts(),
            "updated_at": _now_ts(),
        }
        self._save_index(safe, data)
        return {"status": "ok", "collection_id": safe}

    def delete_collection(self, collection_id):
        safe = re.sub(r"[^A-Za-z0-9_-]", "_", collection_id)
        if not self.store.collection_exists(safe):
            return {"status": "not_found", "collection_id": safe}
        self.store.delete_collection(safe)
        return {"status": "ok", "collection_id": safe}

    def get_collection(self, collection_id):
        safe = re.sub(r"[^A-Za-z0-9_-]", "_", collection_id)
        data = self._load_index(safe)
        docs = data.get("documents", {}) or {}
        return CollectionInfo(
            collection=safe,
            status=CollectionStatus(data.get("status", "empty")),
            document_count=len(docs),
            chunk_count=len(data.get("fragments", [])),
            dim=data.get("dim", self.vectorizer.dim),
            updated_at=data.get("updated_at", 0.0),
            strategy=data.get("strategy", "recursive"),
        )

    def index_text(self, text, collection="default", title="", source_type="manual", doc_id=None, metadata=None, strategy="recursive", chunk_size=None, chunk_overlap=None):
        safe = re.sub(r"[^A-Za-z0-9_-]", "_", collection)
        with self._lock:
            data = self._load_index(safe)
            if data.get("status") == "error" and not data.get("fragments"):
                data = {"collection_id": safe, "dim": self.vectorizer.dim, "strategy": strategy, "status": "empty", "documents": {}, "fragments": []}
            doc_id = doc_id or f"doc_{uuid.uuid4().hex[:10]}"
            cs = chunk_size or self.config.chunk_size
            co = chunk_overlap or self.config.chunk_overlap
            chunks = chunk_text(text, strategy=strategy, chunk_size=cs, chunk_overlap=co)
            if not chunks:
                return {"status": "ok", "collection_id": safe, "doc_id": doc_id, "chunks": 0}
            existing = {f["chunk_id"]: f for f in data.get("fragments", [])}
            for i, ch in enumerate(chunks):
                vec = self.vectorizer.vectorize(ch)
                cid = f"{doc_id}_{i}"
                existing[cid] = {
                    "chunk_id": cid,
                    "doc_id": doc_id,
                    "collection_id": safe,
                    "text": ch,
                    "vector_b64": _vec_to_b64(vec),
                    "title": title,
                    "source_type": source_type,
                    "metadata": metadata or {},
                    "created_at": _now_ts(),
                }
            data["fragments"] = list(existing.values())
            docs = data.get("documents", {}) or {}
            docs[doc_id] = {
                "doc_id": doc_id,
                "title": title,
                "source_type": source_type,
                "chunk_count": len(chunks),
                "metadata": metadata or {},
                "updated_at": _now_ts(),
            }
            data["documents"] = docs
            data["status"] = "ready"
            data["updated_at"] = _now_ts()
            data["strategy"] = strategy
            self._save_index(safe, data)
            return {"status": "ok", "collection_id": safe, "doc_id": doc_id, "chunks": len(chunks)}

    def purge_collection(self, collection_id):
        safe = re.sub(r"[^A-Za-z0-9_-]", "_", collection_id)
        with self._lock:
            data = self._load_index(safe)
            data["fragments"] = []
            data["documents"] = {}
            data["status"] = "empty"
            data["updated_at"] = _now_ts()
            self._save_index(safe, data)
        return {"status": "ok", "collection_id": safe}

    def reset(self):
        with self._lock:
            for cid in self.store.list_collections():
                self.store.delete_collection(cid)
        return {"status": "ok"}

    def search_text(self, query, collection="default", top_k=None, min_score=None):
        safe = re.sub(r"[^A-Za-z0-9_-]", "_", collection)
        data = self._load_index(safe)
        frags = data.get("fragments", [])
        if not frags:
            return SearchResponse(status="ok", query=query, collection=safe, total_hits=0, results=[], context="")
        qvec = self.vectorizer.vectorize(query)
        dim = data.get("dim", self.vectorizer.dim)
        tk = top_k if top_k is not None else self.config.top_k_default
        ms = min_score if min_score is not None else self.config.min_score
        scored = []
        for f in frags:
            try:
                fvec = _b64_to_vec(f["vector_b64"], dim)
            except Exception:
                continue
            sim = float(np.dot(qvec, fvec))
            if sim >= ms:
                scored.append((sim, f))
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[: max(1, min(tk, len(scored)))]
        hits = [SearchHit(doc_id=f["doc_id"], collection=safe, title=f.get("title",""), source_type=f.get("source_type",""), chunk_id=f["chunk_id"], text=f["text"], score=round(s, 4), metadata=f.get("metadata", {})) for s, f in top]
        ctx = self._build_context(hits)
        return SearchResponse(status="ok", query=query, collection=safe, total_hits=len(scored), results=hits, context=ctx)

    def inject_context(self, query, collection="default", top_k=None, max_chars=None):
        sr = self.search_text(query, collection=collection, top_k=top_k)
        return self._build_context(sr.results, max_chars=max_chars or self.config.max_context_chars)

    @staticmethod
    def _build_context(hits, max_chars=2000):
        if not hits:
            return ""
        lines = ["[CONOCIMIENTO - contexto semantico local]"]
        total = 0
        for h in hits:
            snippet = h.text.strip().replace("\n", " ")
            line = f"[{h.collection}:{h.chunk_id} score={h.score}] {snippet}"
            if total + len(line) > max_chars and total > 0:
                break
            lines.append(line)
            total += len(line)
        return " | ".join(lines)

    def status(self):
        cols = []
        td = tc = 0
        for cid in self.store.list_collections():
            info = self.get_collection(cid)
            cols.append(info)
            td += info.document_count
            tc += info.chunk_count
        return RAGStatus(enabled=True, collections=cols, total_documents=td, total_chunks=tc, config=self.config, store_dir=self.config.store_dir)


_engine = None
_engine_lock = threading.Lock()


def get_rag_engine(store_dir=None, config=None, vectorizer=None):
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = RAGEngine(store_dir=store_dir, config=config, vectorizer=vectorizer)
    return _engine


def reset_rag_engine():
    global _engine
    with _engine_lock:
        _engine = None


def set_rag_engine(engine):
    global _engine
    with _engine_lock:
        _engine = engine


KnowledgeVectorEngine = RAGEngine
get_knowledge_engine = get_rag_engine
reset_knowledge_engine = reset_rag_engine
