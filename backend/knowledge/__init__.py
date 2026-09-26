"""BLOQUE 72 - Local Vector Knowledge Base & Advanced RAG Pipeline Engine.

100% local semantic retrieval: feature-hashing + character n-gram embeddings
over NumPy, persisted on-disk as JSON. No cloud vector DBs, no external APIs.
"""

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

__all__ = [
    "CollectionInfo",
    "CollectionStatus",
    "DocumentStatus",
    "IndexStrategy",
    "KnowledgeDocument",
    "RAGConfig",
    "RAGStatus",
    "SearchHit",
    "SearchRequest",
    "SearchResponse",
]

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
