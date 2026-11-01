"""Local Semantic Memory & Vector RAG Engine (BLOQUE 41).

Motor de indexación y búsqueda semántica 100% local para la base literaria
AURA/AME. Emplea embeddings derivados de feature hashing + n-gramas de
caracteres sobre NumPy: NO requiere conexión a internet, NO usa bases de datos
vectoriales comerciales ni servicios de embedding en la nube.

Pipeline:
1. LocalEmbeddingVectorizer: text -> vector numpy (dim fija, L2-normalizado)
   mediante hashing con signo sobre word-tokens y n-gramas de caracteres (n=4).
2. VectorRAGEngine: recolecta canon, characters, chapters, continuity vía
   StoryStorage/CanonTracker/CharacterBible/ChapterPlanner; fragmenta en chunks
   solapados; vectoriza y persiste on-disk en <store_dir>/indices/work_<id>.rag.json.
3. Semantic search por similitud coseno (dot de vectores normalizados).
4. JanContextInjector: recupera top-k fragments y produce un bloque de lore
   listo para inyectar en el system prompt / contexto de Jan (local LLM).

Almacenamiento: JSON en disco (base64 de vectores para evitar redondeos).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from backend.story_memory.story_storage import StoryStorage
from backend.story_memory.canon_tracker import CanonTracker
from backend.story_memory.character_bible import CharacterBible
from backend.story_memory.chapter_planner import ChapterPlanner

# --- stopword mínima para español (sin depender de nltk/spacy). ---
_ES_STOP = frozenset(
    "de la que e el y a los del se las por un para con una su al lo un como le ya o va mas "
    "entre cuando hasta no todo uno les te ti eso esto estos esas aquellos todas lugar otra "
    "otro otros donde quien que cual como cuando cuanto".split()
)
_WORD_RE = re.compile(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]+")
_CHUNK_SIZE = int(os.getenv("AURA_VECTOR_CHUNK_SIZE", "150"))
_CHUNK_OVERLAP = int(os.getenv("AURA_VECTOR_CHUNK_OVERLAP", "50"))
_DEFAULT_DIM = int(os.getenv("AURA_VECTOR_DIM", "512"))
_NGRAM_N = 4


class LocalEmbeddingVectorizer:
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
        h = hashlib.md5(token.encode("utf-8", errors="ignore")).digest()
        return 1 if (h[0] & 1) == 0 else -1

    def _token_bin(self, token: str) -> int:
        h = hashlib.md5(token.encode("utf-8", errors="ignore")).digest()
        return int.from_bytes(h[:8], "little") % self.dim

    def vectorize(self, text: str) -> np.ndarray:
        """Vectoriza texto a un vector numpy de dim self.dim."""
        vec = np.zeros(self.dim, dtype=np.float64)
        if not text:
            return self._normalize(vec)
        for tok in self._word_tokens(text):
            if tok in _ES_STOP or len(tok) < 2:
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
# ---- serialización vector <-> base64 (evita redondeos JSON) ----
def _vec_to_b64(vec: np.ndarray) -> str:
    return base64.b64encode(np.asarray(vec, dtype=np.float32).tobytes()).decode("ascii")


def _b64_to_vec(b64: str, dim: int) -> np.ndarray:
    raw = base64.b64decode(b64)
    return np.frombuffer(raw, dtype=np.float32).astype(np.float64)


def chunk_text(text: str, size: int = _CHUNK_SIZE, overlap: int = _CHUNK_OVERLAP) -> List[str]:
    """Fragmenta texto en chunks de `size` con solapamiento `overlap`."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    chunks: List[str] = []
    step = max(1, size - overlap)
    for start in range(0, len(text), step):
        chunk = text[start : start + size]
        chunks.append(chunk)
        if start + size >= len(text):
            break
    return chunks


class VectorRAGEngine:
    """Motor local de indexación y búsquedas semánticas literarias (offline)."""

    def __init__(self, store_dir: Optional[str] = None, vectorizer: Optional[LocalEmbeddingVectorizer] = None) -> None:
        self.store_dir = os.getenv(
            "AURA_STORY_DIR",
            store_dir or os.path.join(os.getcwd(), "story_memory"),
        )
        self.index_dir = os.path.join(self.store_dir, "indices")
        os.makedirs(self.index_dir, exist_ok=True)
        self.vectorizer = vectorizer or LocalEmbeddingVectorizer()
        self._lock = threading.RLock()

    def _index_path(self, work_id: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9_-]", "_", work_id)
        return os.path.join(self.index_dir, f"work_{safe}.rag.json")

    def _load_index(self, work_id: str) -> Dict[str, Any]:
        path = self._index_path(work_id)
        if not os.path.exists(path):
            return {"work_id": work_id, "dim": self.vectorizer.dim, "fragments": []}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data

    def _save_index(self, work_id: str, index: Dict[str, Any]) -> None:
        path = self._index_path(work_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    def _collect_sources(self, work_id: str) -> List[Dict[str, Any]]:
        """Recopila fragmentos textuales de canon, characters, chapters, continuity."""
        sources: List[Dict[str, Any]] = []
        storage = StoryStorage(store_dir=self.store_dir)
        ct = CanonTracker()
        cb = CharacterBible()
        cp = ChapterPlanner()

        for ev in ct.get_all_events(work_id):
            sources.append({
                "source": "canon" if ev.get("certainty", "canon") == "canon" else "continuity",
                "ref_id": ev.get("event_id", ""),
                "text": ev.get("description", ""),
                "metadata": {"timestamp": ev.get("timestamp", 0), "event_source": ev.get("source", "")},
            })

        char_fields = ("name", "voice", "personality", "objectives", "conflicts", "relationships", "backstory", "aliases")
        for ch in cb.list(work_id):
            parts: List[str] = []
            for fld in char_fields:
                v = ch.get(fld)
                if not v:
                    continue
                if isinstance(v, list):
                    parts.append(", ".join(str(x) for x in v))
                elif isinstance(v, dict):
                    parts.append(", ".join(f"{k}: {val}" for k, val in v.items()))
                else:
                    parts.append(str(v))
            text = "; ".join(parts)
            if text:
                sources.append({
                    "source": "character", "ref_id": ch.get("char_id", ""),
                    "text": text,
                    "metadata": {"name": ch.get("name", ""), "char_id": ch.get("char_id", "")},
                })

        for ch in cp.list_chapters(work_id):
            text_parts: List[str] = []
            if ch.get("title"):
                text_parts.append(f"Capitulo {ch.get('order', '?')}: {ch.get('title')}")
            if ch.get("beat_summary"):
                text_parts.append(ch.get("beat_summary"))
            for sc in ch.get("scenes", []) or []:
                if isinstance(sc, dict) and sc.get("content"):
                    text_parts.append(str(sc["content"]))
            text = ". ".join(text_parts)
            if text:
                sources.append({
                    "source": "chapter", "ref_id": ch.get("chapter_id", ""),
                    "text": text,
                    "metadata": {"order": ch.get("order", 0), "status": ch.get("status", "")},
                })
        return sources
    def index_work(self, work_id: str) -> Dict[str, Any]:
        """Construye / rehace el índice semántico de una obra en disco."""
        with self._lock:
            storage = StoryStorage(store_dir=self.store_dir)
            if not storage.work_exists(work_id):
                return {"status": "error", "error": "work_not_found", "work_id": work_id}

            sources = self._collect_sources(work_id)
            fragments: List[Dict[str, Any]] = []
            for src in sources:
                for i, chunk in enumerate(chunk_text(src["text"])):
                    vec = self.vectorizer.vectorize(chunk)
                    fragments.append({
                        "id": f"{src['source']}:{src['ref_id']}:{i}",
                        "source": src["source"],
                        "ref_id": src["ref_id"],
                        "text": chunk,
                        "vector_b64": _vec_to_b64(vec),
                        "metadata": src.get("metadata", {}),
                    })
            source_counts = {s: sum(1 for f in fragments if f["source"] == s)
                             for s in {"canon", "continuity", "character", "chapter"}}
            index = {
                "work_id": work_id,
                "dim": self.vectorizer.dim,
                "ngram_n": self.vectorizer.n,
                "fragment_count": len(fragments),
                "source_counts": source_counts,
                "updated_at": time.time(),
                "fragments": fragments,
            }
            self._save_index(work_id, index)
            return {
                "status": "ok",
                "work_id": work_id,
                "indexed_fragments": len(fragments),
                "sources": list(source_counts.keys()),
            }

    def get_status(self, work_id: str) -> Dict[str, Any]:
        path = self._index_path(work_id)
        if not os.path.exists(path):
            return {"status": "not_indexed", "work_id": work_id, "fragments": 0}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {
                "status": "indexed",
                "work_id": work_id,
                "fragments": data.get("fragment_count", 0),
                "dim": data.get("dim", self.vectorizer.dim),
                "updated_at": data.get("updated_at", 0),
                "source_counts": data.get("source_counts", {}),
            }
        except (json.JSONDecodeError, OSError):
            return {"status": "corrupted", "work_id": work_id, "fragments": 0}

    def semantic_search(self, work_id: str, query: str, top_k: int = 5) -> Dict[str, Any]:
        """Búsqueda semántica por similitud coseno (offline)."""
        index = self._load_index(work_id)
        if not index.get("fragments"):
            return {"status": "ok", "work_id": work_id, "query": query, "results": [], "context": ""}
        qvec = self.vectorizer.vectorize(query)
        dim = index.get("dim", self.vectorizer.dim)
        results: List[Tuple[float, Dict[str, Any]]] = []
        for frag in index["fragments"]:
            try:
                fvec = _b64_to_vec(frag["vector_b64"], dim)
            except Exception:
                continue
            sim = float(np.dot(qvec, fvec))  # vectores L2-normalizados -> coseno
            results.append((sim, frag))
        results.sort(key=lambda x: x[0], reverse=True)
        top = results[: max(1, min(top_k, len(results)))]
        hits = [
            {"score": round(sim, 4), "source": frag["source"], "ref_id": frag["ref_id"],
             "text": frag["text"], "metadata": frag.get("metadata", {})}
            for sim, frag in top
        ]
        return {"status": "ok", "work_id": work_id, "query": query,
                "results": hits, "context": self._build_context(hits)}

    def inject_context(self, work_id: str, query: str, top_k: int = 5, max_chars: int = 2000) -> str:
        """Jan Context Injector: bloque de lore relevante para system prompt."""
        res = self.semantic_search(work_id, query, top_k=top_k)
        return self._build_context(res["results"], max_chars=max_chars)

    @staticmethod
    def _build_context(hits: List[Dict[str, Any]], max_chars: int = 2000) -> str:
        if not hits:
            return ""
        lines: List[str] = ["[LORE - contexto semantico local]"]
        total = 0
        for h in hits:
            snippet = h["text"].strip().replace("\n", " ")
            line = f"[{h['source']}:{h['ref_id']} score={h['score']}] {snippet}"
            if total + len(line) > max_chars and total > 0:
                break
            lines.append(line)
            total += len(line)
        return " | ".join(lines)


_engine: Optional["VectorRAGEngine"] = None
_lock_init = threading.Lock()


def get_vector_engine(store_dir: Optional[str] = None) -> "VectorRAGEngine":
    global _engine
    if _engine is None:
        with _lock_init:
            if _engine is None:
                _engine = VectorRAGEngine(store_dir=store_dir or os.getenv("AURA_STORY_DIR"))
    return _engine


def set_engine_store_path(path: str) -> None:
    global _engine
    with _lock_init:
        _engine = VectorRAGEngine(store_dir=path)


def reset_vector_engine() -> None:
    global _engine
    with _lock_init:
        _engine = None


