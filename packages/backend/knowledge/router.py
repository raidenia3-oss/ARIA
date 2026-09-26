"""AURA Knowledge RAG REST API (BLOQUE 72).

Endpoints para gestion de colecciones de documentos y busqueda semantica
local sobre la base de conocimiento vectorial. 100% offline.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.knowledge.rag import (
    get_knowledge_engine,
    reset_knowledge_engine,
)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class CollectionCreateRequest(BaseModel):
    name: str = ""
    description: str = ""
    metadata: Dict[str, Any] = {}


class CollectionIngestRequest(BaseModel):
    text: str
    doc_id: Optional[str] = None
    metadata: Dict[str, Any] = {}
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None


class CollectionSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    min_score: Optional[float] = None


@router.post("/collections", response_model=Dict[str, Any])
async def create_collection(payload: CollectionCreateRequest):
    engine = get_knowledge_engine()
    return engine.create_collection(
        collection_id=payload.name.lower().replace(" ", "_"),
        name=payload.name,
        description=payload.description,
        metadata=payload.metadata,
    )


@router.get("/collections", response_model=List[str])
async def list_collections():
    engine = get_knowledge_engine()
    return engine.list_collections()


@router.delete("/collections/{collection_id}", response_model=Dict[str, Any])
async def delete_collection(collection_id: str):
    engine = get_knowledge_engine()
    result = engine.delete_collection(collection_id)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Collection not found")
    return result


@router.get("/collections/{collection_id}/status", response_model=Dict[str, Any])
async def get_collection_status(collection_id: str):
    engine = get_knowledge_engine()
    return engine.get_collection(collection_id).to_dict()


@router.post("/collections/{collection_id}/documents", response_model=Dict[str, Any])
async def add_document(collection_id: str, payload: CollectionIngestRequest):
    engine = get_knowledge_engine()
    doc_id = payload.doc_id or f"doc_{collection_id}"
    return engine.index_text(
        text=payload.text,
        collection=collection_id,
        doc_id=doc_id,
        metadata=payload.metadata,
        chunk_size=payload.chunk_size,
        chunk_overlap=payload.chunk_overlap,
    )


@router.post("/collections/{collection_id}/index/text", response_model=Dict[str, Any])
async def index_text_endpoint(collection_id: str, payload: CollectionIngestRequest):
    engine = get_knowledge_engine()
    doc_id = payload.doc_id or f"doc_{collection_id}"
    return engine.index_text(
        text=payload.text,
        collection=collection_id,
        doc_id=doc_id,
        metadata=payload.metadata,
        chunk_size=payload.chunk_size,
        chunk_overlap=payload.chunk_overlap,
    )


@router.post("/collections/{collection_id}/search", response_model=Dict[str, Any])
async def search_endpoint(collection_id: str, payload: CollectionSearchRequest):
    engine = get_knowledge_engine()
    sr = engine.search_text(
        query=payload.query,
        collection=collection_id,
        top_k=payload.top_k,
        min_score=payload.min_score,
    )
    return {
        "status": sr.status,
        "query": sr.query,
        "collection": sr.collection,
        "total_hits": sr.total_hits,
        "results": [h.model_dump(mode="json") for h in sr.results],
        "context": sr.context,
    }


@router.post("/inject", response_model=Dict[str, Any])
async def inject_endpoint(
    query: str = "",
    collection: str = "default",
    top_k: int = 5,
    max_chars: int = 2000,
):
    engine = get_knowledge_engine()
    ctx = engine.inject_context(query, collection=collection, top_k=top_k, max_chars=max_chars)
    return {"status": "ok", "context": ctx}


@router.post("/collections/{collection_id}/purge", response_model=Dict[str, Any])
async def purge_collection(collection_id: str):
    engine = get_knowledge_engine()
    return engine.purge_collection(collection_id)


@router.post("/reset", response_model=Dict[str, Any])
async def reset_endpoint():
    engine = get_knowledge_engine()
    return engine.reset()


@router.get("/status", response_model=Dict[str, Any])
async def status_endpoint():
    engine = get_knowledge_engine()
    return engine.status().to_dict()