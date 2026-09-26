"""Memory router for AURA - Vector RAG endpoints and Swarm context injection."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from backend.services.memory_engine import MemoryEngine

router = APIRouter()
logger = logging.getLogger("AURAMemory")

try:
    from backend.orchestrator import orchestrator
except Exception:
    orchestrator = None

memory_engine = MemoryEngine(orchestrator=orchestrator)


@router.on_event("startup")
async def _on_startup() -> None:
    logger.info("Memory Engine ready with %d memories", memory_engine.get_status()["total_memories"])


@router.post("/memory/remember")
async def remember(payload: Dict[str, Any]) -> Dict[str, Any]:
    text = str(payload.get("text", "")).strip()
    memory_type = str(payload.get("type", "episodic"))
    source = str(payload.get("source", "user"))
    session_id = str(payload.get("session_id", ""))
    metadata = payload.get("metadata")
    if not text:
        raise HTTPException(status_code=422, detail="text is required")
    result = memory_engine.remember(text, memory_type=memory_type, source=source, session_id=session_id, metadata=metadata)
    return result


@router.get("/memory/search")
async def search_memory(q: str = "", limit: int = 10, min_relevance: float = 0.25) -> Dict[str, Any]:
    if not q:
        raise HTTPException(status_code=422, detail="q is required")
    result = memory_engine.search(q, max_results=limit, min_relevance=min_relevance)
    return result


@router.delete("/memory/forget")
async def forget_memory(memory_id: str = "") -> Dict[str, Any]:
    if not memory_id:
        raise HTTPException(status_code=422, detail="memory_id is required")
    result = memory_engine.forget(memory_id)
    return result


@router.get("/memory/status")
async def memory_status() -> Dict[str, Any]:
    return memory_engine.get_status()


@router.post("/memory/inject")
async def inject_context(payload: Dict[str, Any]) -> Dict[str, Any]:
    query = str(payload.get("query", "")).strip()
    max_results = int(payload.get("max_results", 5))
    if not query:
        raise HTTPException(status_code=422, detail="query is required")
    context = memory_engine.inject_context(query, max_results=max_results)
    return {"status": "ok", "query": query, "context_count": len(context), "context": context}
