# -*- coding: utf-8 -*-
"""ARIA OS - Vector Memory & RAG Routes.

Endpoints para memoria vectorial y RAG:
  POST /api/memory/vector/add           - Add document to vector store
  POST /api/memory/vector/search        - Semantic search
  POST /api/memory/vector/rag           - RAG query (retrieve + generate)
  GET  /api/memory/vector/collections   - List collections
  POST /api/memory/vector/collections   - Create collection
  DELETE /api/memory/vector/collections/{name} - Delete collection
  POST /api/memory/vector/embed         - Generate embeddings
  GET  /api/memory/vector/stats         - Collection statistics
  POST /api/memory/vector/consolidate   - Consolidate memories
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("ARIA.VectorMemory")

router = APIRouter(prefix="/api/memory/vector", tags=["vector-memory"])

# ============================================================================
# Models
# ============================================================================

class Document(BaseModel):
    id: Optional[str] = None
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    collection: str = "default"


class SearchRequest(BaseModel):
    query: str
    collection: str = "default"
    top_k: int = Field(default=10, ge=1, le=100)
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    filter: Optional[Dict[str, Any]] = None


class SearchResult(BaseModel):
    id: str
    content: str
    metadata: Dict[str, Any]
    score: float


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    total: int
    latency_ms: int


class RAGRequest(BaseModel):
    query: str
    collection: str = "default"
    top_k: int = Field(default=5, ge=1, le=20)
    max_tokens: int = Field(default=512, ge=1, le=4096)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    system_prompt: str = ""
    include_sources: bool = True


class RAGResponse(BaseModel):
    answer: str
    sources: List[SearchResult]
    latency_ms: int
    tokens_used: int


class CollectionInfo(BaseModel):
    name: str
    vector_size: int
    distance: str
    points_count: int
    status: str


class CreateCollectionRequest(BaseModel):
    name: str
    vector_size: int = 384
    distance: str = "cosine"  # cosine, euclid, dot


class EmbedRequest(BaseModel):
    texts: List[str]
    model: str = "sentence-transformers/all-MiniLM-L6-v2"


class EmbedResponse(BaseModel):
    embeddings: List[List[float]]
    model: str
    latency_ms: int


class ConsolidateRequest(BaseModel):
    source_collections: List[str]
    target_collection: str
    max_items: int = 1000


# ============================================================================
# Vector Store Backend (Qdrant or LanceDB)
# ============================================================================

_vector_store = None
_embedding_model = None


def _get_vector_store():
    """Get or initialize vector store."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


def _get_embedding_model():
    """Get or initialize embedding model."""
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            logger.info("Loaded sentence-transformers embedding model")
        except ImportError:
            logger.warning("sentence-transformers not available, using mock embeddings")
            _embedding_model = "mock"
    return _embedding_model


class VectorStore:
    """Abstract vector store supporting Qdrant and LanceDB."""
    
    def __init__(self):
        self.backend = self._detect_backend()
        self.collections = {}
        self._init_backend()
    
    def _detect_backend(self) -> str:
        # Check for Qdrant
        try:
            import qdrant_client
            return "qdrant"
        except ImportError:
            pass
        
        # Check for LanceDB
        try:
            import lancedb
            return "lancedb"
        except ImportError:
            pass
        
        # Fallback to in-memory
        return "memory"
    
    def _init_backend(self):
        if self.backend == "qdrant":
            self._init_qdrant()
        elif self.backend == "lancedb":
            self._init_lancedb()
        else:
            self._init_memory()
    
    def _init_qdrant(self):
        from qdrant_client import QdrantClient
        from qdrant_client.http import models
        
        # Try to connect to Qdrant server
        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        qdrant_api_key = os.getenv("QDRANT_API_KEY")
        
        try:
            self.client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
            # Test connection
            self.client.get_collections()
            logger.info(f"Connected to Qdrant at {qdrant_url}")
        except Exception as e:
            logger.warning(f"Qdrant not available: {e}, falling back to memory")
            self.backend = "memory"
            self._init_memory()
    
    def _init_lancedb(self):
        import lancedb
        
        db_path = os.getenv("LANCEDB_PATH", str(Path.home() / ".aria" / "lancedb"))
        Path(db_path).mkdir(parents=True, exist_ok=True)
        
        try:
            self.db = lancedb.connect(db_path)
            logger.info(f"Connected to LanceDB at {db_path}")
        except Exception as e:
            logger.warning(f"LanceDB not available: {e}, falling back to memory")
            self.backend = "memory"
            self._init_memory()
    
    def _init_memory(self):
        self.memory_store = {}
        logger.info("Using in-memory vector store")
    
    def create_collection(self, name: str, vector_size: int, distance: str) -> bool:
        if self.backend == "qdrant":
            from qdrant_client.http import models
            try:
                self.client.create_collection(
                    collection_name=name,
                    vectors_config=models.VectorParams(
                        size=vector_size,
                        distance=models.Distance.COSINE if distance == "cosine" else models.Distance.EUCLID
                    )
                )
                return True
            except Exception as e:
                logger.error(f"Failed to create Qdrant collection: {e}")
                return False
        
        elif self.backend == "lancedb":
            # LanceDB creates tables on first insert
            return True
        
        else:
            self.memory_store[name] = {
                "vector_size": vector_size,
                "distance": distance,
                "points": {}
            }
            return True
    
    def list_collections(self) -> List[CollectionInfo]:
        if self.backend == "qdrant":
            try:
                collections = self.client.get_collections().collections
                return [
                    CollectionInfo(
                        name=c.name,
                        vector_size=c.config.params.vectors.size if c.config.params.vectors else 0,
                        distance=str(c.config.params.vectors.distance) if c.config.params.vectors else "cosine",
                        points_count=0,  # Would need to count
                        status="active"
                    )
                    for c in collections
                ]
            except Exception as e:
                logger.error(f"Failed to list Qdrant collections: {e}")
                return []
        
        elif self.backend == "lancedb":
            try:
                tables = self.db.table_names()
                return [
                    CollectionInfo(
                        name=t,
                        vector_size=384,
                        distance="cosine",
                        points_count=0,
                        status="active"
                    )
                    for t in tables
                ]
            except Exception as e:
                logger.error(f"Failed to list LanceDB tables: {e}")
                return []
        
        else:
            return [
                CollectionInfo(
                    name=name,
                    vector_size=info["vector_size"],
                    distance=info["distance"],
                    points_count=len(info["points"]),
                    status="active"
                )
                for name, info in self.memory_store.items()
            ]
    
    def delete_collection(self, name: str) -> bool:
        if self.backend == "qdrant":
            try:
                self.client.delete_collection(collection_name=name)
                return True
            except Exception as e:
                logger.error(f"Failed to delete Qdrant collection: {e}")
                return False
        
        elif self.backend == "lancedb":
            try:
                self.db.drop_table(name)
                return True
            except Exception as e:
                logger.error(f"Failed to drop LanceDB table: {e}")
                return False
        
        else:
            if name in self.memory_store:
                del self.memory_store[name]
                return True
            return False
    
    def add_documents(self, collection: str, documents: List[Document], embeddings: List[List[float]]) -> List[str]:
        if len(documents) != len(embeddings):
            raise ValueError("Documents and embeddings count mismatch")
        
        ids = []
        
        if self.backend == "qdrant":
            from qdrant_client.http import models
            points = []
            for doc, emb in zip(documents, embeddings):
                point_id = doc.id or str(uuid.uuid4())
                ids.append(point_id)
                points.append(models.PointStruct(
                    id=point_id,
                    vector=emb,
                    payload={"content": doc.content, **doc.metadata}
                ))
            
            self.client.upsert(collection_name=collection, points=points)
        
        elif self.backend == "lancedb":
            import pyarrow as pa
            table_name = collection.replace("-", "_")
            
            # Create table if not exists
            if table_name not in self.db.table_names():
                data = [{
                    "id": str(uuid.uuid4()),
                    "vector": [0.0] * len(embeddings[0]),
                    "content": "",
                    "metadata": "{}"
                }]
                table = self.db.create_table(table_name, data=pa.Table.from_pylist(data))
            else:
                table = self.db.open_table(table_name)
            
            for doc, emb in zip(documents, embeddings):
                point_id = doc.id or str(uuid.uuid4())
                ids.append(point_id)
                table.add([{
                    "id": point_id,
                    "vector": emb,
                    "content": doc.content,
                    "metadata": str(doc.metadata)
                }])
        
        else:
            if collection not in self.memory_store:
                self.create_collection(collection, len(embeddings[0]), "cosine")
            
            for doc, emb in zip(documents, embeddings):
                point_id = doc.id or str(uuid.uuid4())
                ids.append(point_id)
                self.memory_store[collection]["points"][point_id] = {
                    "vector": emb,
                    "content": doc.content,
                    "metadata": doc.metadata
                }
        
        return ids
    
    def search(self, collection: str, query_vector: List[float], top_k: int, threshold: float, filter: Optional[Dict] = None) -> List[SearchResult]:
        if self.backend == "qdrant":
            from qdrant_client.http import models
            try:
                search_result = self.client.search(
                    collection_name=collection,
                    query_vector=query_vector,
                    limit=top_k,
                    score_threshold=threshold,
                    query_filter=models.Filter(**filter) if filter else None
                )
                
                return [
                    SearchResult(
                        id=str(hit.id),
                        content=hit.payload.get("content", ""),
                        metadata={k: v for k, v in hit.payload.items() if k != "content"},
                        score=hit.score
                    )
                    for hit in search_result
                ]
            except Exception as e:
                logger.error(f"Qdrant search failed: {e}")
                return []
        
        elif self.backend == "lancedb":
            try:
                table = self.db.open_table(collection.replace("-", "_"))
                results = table.search(query_vector).limit(top_k).to_list()
                
                return [
                    SearchResult(
                        id=r["id"],
                        content=r["content"],
                        metadata=eval(r["metadata"]) if isinstance(r["metadata"], str) else r["metadata"],
                        score=1.0 - r["_distance"]  # Convert distance to similarity
                    )
                    for r in results if (1.0 - r["_distance"]) >= threshold
                ]
            except Exception as e:
                logger.error(f"LanceDB search failed: {e}")
                return []
        
        else:
            # In-memory cosine similarity search
            import numpy as np
            
            if collection not in self.memory_store:
                return []
            
            points = self.memory_store[collection]["points"]
            query_vec = np.array(query_vector)
            
            results = []
            for point_id, point in points.items():
                vec = np.array(point["vector"])
                # Cosine similarity
                sim = np.dot(query_vec, vec) / (np.linalg.norm(query_vec) * np.linalg.norm(vec) + 1e-8)
                
                if sim >= threshold:
                    results.append(SearchResult(
                        id=point_id,
                        content=point["content"],
                        metadata=point["metadata"],
                        score=float(sim)
                    ))
            
            # Sort by score descending
            results.sort(key=lambda x: x.score, reverse=True)
            return results[:top_k]
    
    def get_collection_stats(self, collection: str) -> Dict[str, Any]:
        if self.backend == "qdrant":
            try:
                info = self.client.get_collection(collection_name=collection)
                return {
                    "name": collection,
                    "vectors_count": info.vectors_count,
                    "points_count": info.points_count,
                    "status": info.status
                }
            except Exception as e:
                logger.error(f"Failed to get Qdrant collection stats: {e}")
                return {}
        
        elif self.backend == "lancedb":
            try:
                table = self.db.open_table(collection.replace("-", "_"))
                count = len(table.to_pandas())
                return {
                    "name": collection,
                    "points_count": count,
                    "status": "active"
                }
            except Exception as e:
                logger.error(f"Failed to get LanceDB table stats: {e}")
                return {}
        
        else:
            if collection in self.memory_store:
                return {
                    "name": collection,
                    "points_count": len(self.memory_store[collection]["points"]),
                    "status": "active"
                }
            return {}


# ============================================================================
# Embedding Generation
# ============================================================================

def _generate_embeddings(texts: List[str], model_name: str) -> List[List[float]]:
    """Generate embeddings for texts."""
    model = _get_embedding_model()
    
    if model == "mock":
        # Return random embeddings for testing
        import random
        return [[random.uniform(-1, 1) for _ in range(384)] for _ in texts]
    
    # Use sentence-transformers
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return embeddings.tolist()


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/add", response_model=Dict[str, Any])
async def add_documents(documents: List[Document]):
    """Add documents to vector store with automatic embedding generation."""
    store = _get_vector_store()
    
    # Generate embeddings
    texts = [doc.content for doc in documents]
    embeddings = _generate_embeddings(texts, "default")
    
    # Use first document's collection or default
    collection = documents[0].collection if documents else "default"
    
    # Ensure collection exists
    if collection not in [c.name for c in store.list_collections()]:
        store.create_collection(collection, len(embeddings[0]), "cosine")
    
    ids = store.add_documents(collection, documents, embeddings)
    
    return {
        "status": "ok",
        "added": len(ids),
        "ids": ids,
        "collection": collection
    }


@router.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest):
    """Semantic search in vector store."""
    store = _get_vector_store()
    start = time.time()
    
    # Generate query embedding
    query_embedding = _generate_embeddings([req.query], "default")[0]
    
    # Search
    results = store.search(
        collection=req.collection,
        query_vector=query_embedding,
        top_k=req.top_k,
        threshold=req.threshold,
        filter=req.filter
    )
    
    return SearchResponse(
        query=req.query,
        results=results,
        total=len(results),
        latency_ms=int((time.time() - start) * 1000)
    )


@router.post("/rag", response_model=RAGResponse)
async def rag_query(req: RAGRequest):
    """RAG: Retrieve relevant docs + generate answer using local LLM."""
    store = _get_vector_store()
    start = time.time()
    
    # Step 1: Retrieve relevant documents
    query_embedding = _generate_embeddings([req.query], "default")[0]
    
    sources = store.search(
        collection=req.collection,
        query_vector=query_embedding,
        top_k=req.top_k,
        threshold=0.3  # Lower threshold for better recall
    )
    
    # Step 2: Build context from sources
    if sources:
        context_parts = []
        for i, src in enumerate(sources):
            context_parts.append(f"[Fuente {i+1}]: {src.content}")
        
        context = "\n\n".join(context_parts)
        
        # Step 3: Generate answer using local LLM
        system_prompt = req.system_prompt or (
            "Eres ARIA, un asistente personal con acceso a una base de conocimiento privada. "
            "Responde SOLO usando la información del contexto proporcionado. "
            "Si la información no está en el contexto, responde: 'No tengo esa información en mi base de conocimiento.' "
            "Cita las fuentes usando [Fuente X]."
        )
        
        prompt = f"""Contexto de la base de conocimiento:
{context}

Pregunta: {req.query}

Respuesta basada únicamente en el contexto:"""
    else:
        # No relevant sources found
        context = ""
        system_prompt = req.system_prompt or "Eres ARIA, un asistente personal."
        prompt = f"No tengo información relevante en mi base de conocimiento para esta pregunta.\n\nPregunta: {req.query}\n\nRespuesta:"
    
    # Call local LLM inference
    try:
        import aiohttp
        payload = {
            "model": "dolphin-2_6-phi-2:latest",
            "prompt": prompt,
            "system": system_prompt,
            "options": {
                "num_predict": req.max_tokens,
                "temperature": req.temperature,
                "top_p": 0.9,
            },
            "stream": False
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://localhost:11434/api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    answer = result.get("response", "")
                else:
                    answer = "Error generando respuesta"
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        answer = f"Error: {str(e)}"
    
    latency_ms = int((time.time() - start) * 1000)
    
    return RAGResponse(
        answer=answer,
        sources=sources if req.include_sources else [],
        latency_ms=latency_ms,
        tokens_used=len(answer.split())
    )


@router.get("/collections", response_model=List[CollectionInfo])
async def list_collections():
    """List all vector collections."""
    store = _get_vector_store()
    return store.list_collections()


@router.post("/collections", response_model=Dict[str, Any])
async def create_collection(req: CreateCollectionRequest):
    """Create a new vector collection."""
    store = _get_vector_store()
    
    success = store.create_collection(req.name, req.vector_size, req.distance)
    
    if success:
        return {"status": "created", "collection": req.name}
    else:
        raise HTTPException(status_code=500, detail="Failed to create collection")


@router.delete("/collections/{name}", response_model=Dict[str, Any])
async def delete_collection(name: str):
    """Delete a vector collection."""
    store = _get_vector_store()
    
    success = store.delete_collection(name)
    
    if success:
        return {"status": "deleted", "collection": name}
    else:
        raise HTTPException(status_code=404, detail="Collection not found")


@router.post("/embed", response_model=EmbedResponse)
async def generate_embeddings(req: EmbedRequest):
    """Generate embeddings for texts."""
    start = time.time()
    
    model = _get_embedding_model()
    model_name = req.model if model != "mock" else "mock"
    
    embeddings = _generate_embeddings(req.texts, model_name)
    
    return EmbedResponse(
        embeddings=embeddings,
        model=model_name,
        latency_ms=int((time.time() - start) * 1000)
    )


@router.get("/stats", response_model=Dict[str, Any])
async def get_stats(collection: str = "default"):
    """Get collection statistics."""
    store = _get_vector_store()
    stats = store.get_collection_stats(collection)
    stats["backend"] = store.backend
    return stats


@router.post("/consolidate", response_model=Dict[str, Any])
async def consolidate_memories(req: ConsolidateRequest):
    """Consolidate memories from multiple collections into one."""
    store = _get_vector_store()
    
    all_docs = []
    all_embeddings = []
    
    for src_col in req.source_collections:
        # Get all documents from source collection
        # This is a simplified version - would need pagination for large collections
        try:
            if store.backend == "qdrant":
                from qdrant_client.http import models
                result = store.client.scroll(
                    collection_name=src_col,
                    limit=req.max_items,
                    with_payload=True,
                    with_vectors=True
                )
                for point in result[0]:
                    all_docs.append(Document(
                        id=str(point.id),
                        content=point.payload.get("content", ""),
                        metadata={k: v for k, v in point.payload.items() if k != "content"},
                        collection=req.target_collection
                    ))
                    all_embeddings.append(point.vector)
            
            elif store.backend == "memory" and src_col in store.memory_store:
                for point_id, point in store.memory_store[src_col]["points"].items():
                    all_docs.append(Document(
                        id=point_id,
                        content=point["content"],
                        metadata=point["metadata"],
                        collection=req.target_collection
                    ))
                    all_embeddings.append(point["vector"])
        except Exception as e:
            logger.error(f"Failed to read from {src_col}: {e}")
    
    if all_docs:
        # Create target collection if needed
        if req.target_collection not in [c.name for c in store.list_collections()]:
            store.create_collection(req.target_collection, len(all_embeddings[0]), "cosine")
        
        ids = store.add_documents(req.target_collection, all_docs, all_embeddings)
        return {
            "status": "ok",
            "consolidated": len(ids),
            "source_collections": req.source_collections,
            "target_collection": req.target_collection
        }
    
    return {"status": "empty", "message": "No documents to consolidate"}


# ============================================================================
# Health Check
# ============================================================================

@router.get("/health")
async def vector_memory_health():
    """Health check for vector memory system."""
    store = _get_vector_store()
    model = _get_embedding_model()
    
    return {
        "vector_store": store.backend,
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2" if model != "mock" else "mock",
        "collections": len(store.list_collections()),
        "timestamp": time.time()
    }