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

Honesty contract (ARIA Phase A). Semantic similarity is only a claim this module
may make when a real embedding model produced the vectors. Every response that
carries vectors, similarity scores or retrieved documents carries
`data_source`, and `data_source` is derived structurally from the loaded model
object, never from a label parsed out of a string:
  * 200 with `data_source: "measured"` when sentence-transformers actually
    encoded the texts here and now.
  * 200 with `data_source: "unavailable"`, explicit nulls and a `detail`, when
    the datum was never measured because the embedding model is absent. The
    key is present and null so a client can tell "not measured" apart from
    "field I do not know about".
  * Placeholder vectors exist only to keep the `/embed` shape; they are
    deterministic, they carry no semantic information, and they are never
    indexed nor searched as if they were embeddings.
"""

from __future__ import annotations

import asyncio
import hashlib
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
# Honesty constants
# ============================================================================

#: A real embedding model encoded the data in this response.
DATA_SOURCE_MEASURED = "measured"
#: The datum could not be measured (no embedding model loaded).
DATA_SOURCE_UNAVAILABLE = "unavailable"

EMBEDDING_MODEL_REF = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_MODEL_MOCK_LABEL = "mock"
PLACEHOLDER_VECTOR_SIZE = 384

UNAVAILABLE_DETAIL = (
    "Vector memory unavailable: sentence-transformers is not installed, so no "
    "real embedding was computed. Nothing was indexed and no semantic "
    "similarity is reported. Install sentence-transformers to enable "
    f"{EMBEDDING_MODEL_REF}."
)

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
    #: Defaults to the honest value: a result is treated as unmeasured until
    #: the route that produced it stamps it as DATA_SOURCE_MEASURED.
    data_source: str = DATA_SOURCE_UNAVAILABLE


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    total: int
    latency_ms: int
    #: DATA_SOURCE_MEASURED only when the query and the indexed vectors were
    #: really encoded; DATA_SOURCE_UNAVAILABLE when results are empty because
    #: nothing could be measured.
    data_source: str = DATA_SOURCE_UNAVAILABLE
    #: The query embedding actually used, or None when none was computed.
    embedding: Optional[List[float]] = None
    detail: Optional[str] = None


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
    #: DATA_SOURCE_MEASURED only when the retrieved context came from real
    #: embeddings; DATA_SOURCE_UNAVAILABLE when no retrieval was possible.
    data_source: str = DATA_SOURCE_UNAVAILABLE
    detail: Optional[str] = None


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
    #: DATA_SOURCE_UNAVAILABLE whenever `model` is "mock": the vectors below
    #: are deterministic placeholders, not embeddings.
    data_source: str = DATA_SOURCE_UNAVAILABLE
    detail: Optional[str] = None


class ConsolidateRequest(BaseModel):
    source_collections: List[str]
    target_collection: str
    max_items: int = 1000


# ============================================================================
# Vector Store Backend (Qdrant or LanceDB)
# ============================================================================

_vector_store = None
_embedding_model = None


class _UnavailableEmbeddingModel:
    """Sentinel for "no real embedding model is loaded".

    A dedicated type instead of the string "mock" so availability is decided by
    identity against a typed sentinel, not by comparing a string value.
    """

    __slots__ = ()


_UNAVAILABLE_EMBEDDING_MODEL = _UnavailableEmbeddingModel()


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
            _embedding_model = SentenceTransformer(EMBEDDING_MODEL_REF)
            logger.info("Loaded sentence-transformers embedding model")
        except ImportError:
            logger.warning(
                "sentence-transformers not available: vector memory cannot "
                "embed, index or search; vector routes report "
                "data_source=unavailable"
            )
            _embedding_model = _UNAVAILABLE_EMBEDDING_MODEL
    return _embedding_model


def _embeddings_available() -> bool:
    """Structural check: is a real embedding model loaded?"""
    return _get_embedding_model() is not _UNAVAILABLE_EMBEDDING_MODEL


def _embedding_model_name() -> str:
    """Name of the loaded model, or the "mock" label when none is loaded."""
    return EMBEDDING_MODEL_REF if _embeddings_available() else EMBEDDING_MODEL_MOCK_LABEL


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

def _placeholder_vector(text: str, size: int = PLACEHOLDER_VECTOR_SIZE) -> List[float]:
    """Deterministic, non-semantic placeholder of the requested size.

    Deterministic (SHA-256 of the text) rather than random on purpose: the same
    text yields the same vector across processes and restarts, so a placeholder
    is reproducible and debuggable instead of irreproducible noise. A random
    vector would change on every call, which makes any stored trace of it
    uninterpretable and hides the fact that nothing was measured.

    This is NOT a degraded embedding: it carries no semantic information. Every
    response that hands one out must declare data_source="unavailable", and no
    placeholder may be indexed or searched as if it were an embedding.
    """
    seed = hashlib.sha256(text.encode("utf-8")).digest()
    values: List[float] = []
    counter = 0
    while len(values) < size:
        block = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
        # 32 bytes per block, mapped onto [-1.0, 1.0].
        values.extend(byte / 127.5 - 1.0 for byte in block)
        counter += 1
    return [round(value, 6) for value in values[:size]]


def _stamp_measured(results: List[SearchResult]) -> List[SearchResult]:
    """Mark results as produced from real embeddings."""
    for result in results:
        result.data_source = DATA_SOURCE_MEASURED
    return results


def _generate_embeddings(texts: List[str], model_name: str) -> List[List[float]]:
    """Generate embeddings for texts.

    Without a real embedding model this returns deterministic placeholders
    (see _placeholder_vector). They exist only so /embed, which is already
    labelled model="mock" + data_source="unavailable", keeps its shape. Routes
    that would store or search them (/add, /search, /rag) refuse to run instead.
    """
    model = _get_embedding_model()

    if model is _UNAVAILABLE_EMBEDDING_MODEL:
        return [_placeholder_vector(text) for text in texts]

    # Use sentence-transformers
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return embeddings.tolist()


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/add", response_model=Dict[str, Any])
async def add_documents(documents: List[Document]):
    """Add documents to vector store with automatic embedding generation."""
    # Use first document's collection or default
    collection = documents[0].collection if documents else "default"

    if not _embeddings_available():
        # Indexing placeholder vectors would build a decorative index: the
        # client would get a success and later "semantic" results derived from
        # nothing. 200 + data_source keeps "unavailable" distinguishable from
        # "error" for the client; no document is stored.
        return {
            "status": DATA_SOURCE_UNAVAILABLE,
            "added": 0,
            "ids": [],
            "collection": collection,
            "embeddings": None,
            "data_source": DATA_SOURCE_UNAVAILABLE,
            "detail": UNAVAILABLE_DETAIL,
        }

    store = _get_vector_store()

    # Generate embeddings
    texts = [doc.content for doc in documents]
    embeddings = _generate_embeddings(texts, EMBEDDING_MODEL_REF)

    # Ensure collection exists
    if collection not in [c.name for c in store.list_collections()]:
        store.create_collection(collection, len(embeddings[0]), "cosine")

    ids = store.add_documents(collection, documents, embeddings)

    return {
        "status": "ok",
        "added": len(ids),
        "ids": ids,
        "collection": collection,
        "data_source": DATA_SOURCE_MEASURED,
        "detail": None,
    }


@router.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest):
    """Semantic search in vector store."""
    start = time.time()

    if not _embeddings_available():
        # Similarity over placeholder vectors is not a semantic result, so no
        # result is returned at all rather than a ranked list of noise.
        return SearchResponse(
            query=req.query,
            results=[],
            total=0,
            latency_ms=int((time.time() - start) * 1000),
            data_source=DATA_SOURCE_UNAVAILABLE,
            embedding=None,
            detail=UNAVAILABLE_DETAIL,
        )

    store = _get_vector_store()

    # Generate query embedding
    query_embedding = _generate_embeddings([req.query], EMBEDDING_MODEL_REF)[0]

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
        results=_stamp_measured(results),
        total=len(results),
        latency_ms=int((time.time() - start) * 1000),
        data_source=DATA_SOURCE_MEASURED,
        embedding=query_embedding,
        detail=None,
    )


@router.post("/rag", response_model=RAGResponse)
async def rag_query(req: RAGRequest):
    """RAG: Retrieve relevant docs + generate answer using local LLM."""
    start = time.time()

    if not _embeddings_available():
        # Retrieval over placeholder vectors would hand the LLM a fabricated
        # context and make it answer from noise while citing [Fuente X]. The
        # LLM is not called at all here.
        return RAGResponse(
            answer=(
                "No puedo responder con la base de conocimiento: la memoria "
                "vectorial no esta disponible, asi que no hay contexto "
                "recuperado que puedas citar."
            ),
            sources=[],
            latency_ms=int((time.time() - start) * 1000),
            tokens_used=0,
            data_source=DATA_SOURCE_UNAVAILABLE,
            detail=UNAVAILABLE_DETAIL,
        )

    store = _get_vector_store()

    # Step 1: Retrieve relevant documents
    query_embedding = _generate_embeddings([req.query], EMBEDDING_MODEL_REF)[0]

    sources = _stamp_measured(store.search(
        collection=req.collection,
        query_vector=query_embedding,
        top_k=req.top_k,
        threshold=0.3  # Lower threshold for better recall
    ))
    
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
        tokens_used=len(answer.split()),
        data_source=DATA_SOURCE_MEASURED,
        detail=None,
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

    available = _embeddings_available()
    model_name = req.model if available else EMBEDDING_MODEL_MOCK_LABEL

    embeddings = _generate_embeddings(req.texts, model_name)

    return EmbedResponse(
        embeddings=embeddings,
        model=model_name,
        latency_ms=int((time.time() - start) * 1000),
        data_source=DATA_SOURCE_MEASURED if available else DATA_SOURCE_UNAVAILABLE,
        detail=None if available else (
            "Placeholder vectors, not embeddings: deterministic hashes of each "
            "text with no semantic information, returned because the "
            f"{EMBEDDING_MODEL_REF} model is not installed. Do not index or "
            "search them."
        ),
    )


@router.get("/stats", response_model=Dict[str, Any])
async def get_stats(collection: str = "default"):
    """Get collection statistics."""
    store = _get_vector_store()
    stats = store.get_collection_stats(collection)
    stats["backend"] = store.backend
    available = _embeddings_available()
    stats["data_source"] = DATA_SOURCE_MEASURED if available else DATA_SOURCE_UNAVAILABLE
    if not available:
        stats["detail"] = (
            "Points counted here may hold placeholder vectors indexed before "
            "this endpoint stopped storing them; their provenance cannot be "
            "verified and they are not searchable as semantics."
        )
    return stats


@router.post("/consolidate", response_model=Dict[str, Any])
async def consolidate_memories(req: ConsolidateRequest):
    """Consolidate memories from multiple collections into one."""
    store = _get_vector_store()
    # No embedding is generated here: stored vectors are copied verbatim, so no
    # semantic claim is made about them. Their provenance is not re-verified.
    data_source = (
        DATA_SOURCE_MEASURED if _embeddings_available() else DATA_SOURCE_UNAVAILABLE
    )
    provenance_detail = (
        "Vectors are copied verbatim from the source collections; their origin "
        "is not re-verified here, so a collection populated with placeholder "
        "vectors stays unsearchable as semantics."
    )

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
            "target_collection": req.target_collection,
            "data_source": data_source,
            "detail": provenance_detail,
        }

    return {
        "status": "empty",
        "message": "No documents to consolidate",
        "data_source": data_source,
        "detail": provenance_detail,
    }


# ============================================================================
# Health Check
# ============================================================================

@router.get("/health")
async def vector_memory_health():
    """Health check for vector memory system."""
    store = _get_vector_store()
    available = _embeddings_available()

    return {
        "vector_store": store.backend,
        "embedding_model": _embedding_model_name(),
        "collections": len(store.list_collections()),
        "timestamp": time.time(),
        "data_source": DATA_SOURCE_MEASURED if available else DATA_SOURCE_UNAVAILABLE,
        "detail": None if available else UNAVAILABLE_DETAIL,
    }