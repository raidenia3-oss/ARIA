"""BLOQUE 72 - Local Vector Knowledge Base & Advanced RAG Pipeline Engine.

Data models for the general-purpose knowledge RAG subsystem.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CollectionStatus(str, Enum):
    EMPTY = "empty"
    INDEXING = "indexing"
    READY = "ready"
    ERROR = "error"


class DocumentStatus(str, Enum):
    PENDING = "pending"
    INDEXED = "indexed"
    FAILED = "failed"


class IndexStrategy(str, Enum):
    """How text is split before embedding."""

    PARAGRAPH = "paragraph"
    SENTENCE = "sentence"
    FIXED = "fixed"
    RECURSIVE = "recursive"


class KnowledgeDocument(BaseModel):
    """A document submitted for indexing into a knowledge collection."""

    doc_id: str
    collection: str = "default"
    title: str = ""
    source_type: str = "manual"  # manual, guide, research, game, api, note
    text: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    status: DocumentStatus = DocumentStatus.PENDING
    chunk_count: int = 0
    created_at: float = 0.0
    updated_at: float = 0.0


class SearchHit(BaseModel):
    """A single semantic search result."""

    doc_id: str
    collection: str
    title: str = ""
    source_type: str = ""
    chunk_id: str = ""
    text: str = ""
    score: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SearchRequest(BaseModel):
    """Semantic search request body."""

    query: str
    top_k: int = 5
    collection: str = "default"
    min_score: float = 0.0
    max_chars: int = 2000


class SearchResponse(BaseModel):
    """Semantic search response."""

    status: str = "ok"
    query: str = ""
    collection: str = ""
    total_hits: int = 0
    results: List[SearchHit] = Field(default_factory=list)
    context: str = ""


class CollectionInfo(BaseModel):
    """Status of a knowledge collection."""

    collection: str
    status: CollectionStatus = CollectionStatus.EMPTY
    document_count: int = 0
    chunk_count: int = 0
    dim: int = 0
    updated_at: float = 0.0
    strategy: str = "recursive"

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")


class RAGConfig(BaseModel):
    """Configuration for the RAG engine."""

    dim: int = 512
    ngram_n: int = 4
    chunk_size: int = 400
    chunk_overlap: int = 80
    top_k_default: int = 5
    min_score: float = 0.0
    max_context_chars: int = 2000
    store_dir: str = "knowledge_store"

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")


class RAGStatus(BaseModel):
    """Aggregate status of the knowledge RAG subsystem."""

    enabled: bool = True
    collections: List[CollectionInfo] = Field(default_factory=list)
    total_documents: int = 0
    total_chunks: int = 0
    config: RAGConfig = Field(default_factory=RAGConfig)
    store_dir: str = "knowledge_store"

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")