import os
import json
import uuid
from typing import Optional

import chromadb
from chromadb.config import Settings

_VECTOR_DB_DIR = os.path.join(os.path.dirname(__file__), "vector_db")
_COLLECTION_NAME = "aura_knowledge"


class AuraVectorMemory:
    """Memoria vectorial persistente con ChromaDB.

    Convierte texto plano a embeddings utilizando el modelo por defecto
    de ChromaDB (all-MiniLM-L6-v2, ejecutado localmente) y permite
    búsquedas semánticas sobre el conocimiento almacenado.
    """

    def __init__(self) -> None:
        os.makedirs(_VECTOR_DB_DIR, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=_VECTOR_DB_DIR,
            settings=Settings(anonymized_telemetry=False),
        )
        try:
            self.collection = self.client.get_collection(_COLLECTION_NAME)
        except Exception:
            self.collection = self.client.create_collection(
                name=_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )

    # ──────────────────────────────────────
    # Chunking
    # ──────────────────────────────────────
    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
        tokens = text.split()
        chunks: list[str] = []
        start = 0
        while start < len(tokens):
            end = start + chunk_size
            chunk = " ".join(tokens[start:end])
            if chunk:
                chunks.append(chunk)
            start += chunk_size - overlap
            if start >= len(tokens):
                break
        return chunks or [text]

    # ──────────────────────────────────────
    # Añadir documento
    # ──────────────────────────────────────
    def add_document(
        self, text: str, metadata: Optional[dict] = None, doc_id: Optional[str] = None
    ) -> dict:
        chunks = self._chunk_text(text)
        ids: list[str] = []
        metadatas: list[dict] = []
        documents: list[str] = []

        base_id = doc_id or str(uuid.uuid4())
        meta = metadata or {}

        for i, chunk in enumerate(chunks):
            chunk_id = f"{base_id}_{i}"
            ids.append(chunk_id)
            documents.append(chunk)
            chunk_meta = {"doc_id": base_id, "chunk": i, **meta}
            metadatas.append(chunk_meta)

        self.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )
        return {
            "doc_id": base_id,
            "chunks": len(chunks),
            "total_chars": len(text),
        }

    # ──────────────────────────────────────
    # Búsqueda semántica
    # ──────────────────────────────────────
    def search_similar(self, query: str, limit: int = 3) -> list[dict]:
        if self.collection.count() == 0:
            return []
        results = self.collection.query(
            query_texts=[query],
            n_results=min(limit, self.collection.count()),
        )
        hits: list[dict] = []
        for i in range(len(results.get("ids", [[]])[0])):
            hits.append(
                {
                    "id": results["ids"][0][i],
                    "text": results["documents"][0][i],
                    "score": results["distances"][0][i] if results.get("distances") else None,
                    "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                }
            )
        return hits

    # ──────────────────────────────────────
    # Conteo
    # ──────────────────────────────────────
    def count(self) -> int:
        return self.collection.count()

    # ──────────────────────────────────────
    # Reset
    # ──────────────────────────────────────
    def reset(self) -> None:
        self.client.delete_collection(_COLLECTION_NAME)
        self.collection = self.client.create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )


# Singleton global
_vector_memory: Optional[AuraVectorMemory] = None


def get_vector_memory() -> AuraVectorMemory:
    global _vector_memory
    if _vector_memory is None:
        _vector_memory = AuraVectorMemory()
    return _vector_memory
