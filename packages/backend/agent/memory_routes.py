"""AURA Agent Memory REST Endpoints (Bloque 57)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.agents.orchestrator import vibe_orchestrator
from backend.agent.memory_store import (
    AgentMemoryStore, ExecutionTrace, TraceOutcome, get_agent_memory,
)

logger = logging.getLogger("AURA.Agent.Memory.Routes")

router = APIRouter(prefix="/api/agent/memory", tags=["agent-memory"])


def _get_store() -> AgentMemoryStore:
    return get_agent_memory()


class RecordTraceRequest(BaseModel):
    objective: str = Field(..., min_length=1, max_length=2000)
    outcome: str = Field("partial")
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    error: str = ""
    correction: str = ""
    task_id: str = ""


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    max_results: int = Field(5, ge=1, le=20)


@router.get("/status")
async def memory_status() -> Dict[str, Any]:
    store = _get_store()
    base = store.get_status()
    base["orchestrator_tasks"] = vibe_orchestrator.status()["tasks_total"]
    return base


@router.get("/traces")
async def list_traces(
    outcome: Optional[str] = None,
    task_id: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    store = _get_store()
    traces = store.list_traces(outcome=outcome, task_id=task_id, limit=limit)
    return {"count": len(traces), "traces": traces}


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str) -> Dict[str, Any]:
    store = _get_store()
    trace = store.get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="trace_not_found")
    return trace.to_dict()


@router.post("/traces")
async def record_trace(payload: RecordTraceRequest) -> Dict[str, Any]:
    store = _get_store()
    try:
        outcome = TraceOutcome(payload.outcome)
    except ValueError:
        raise HTTPException(status_code=422, detail="invalid outcome")
    trace = ExecutionTrace(
        trace_id=f"trace-manual-{int(__import__('time').time() * 1000)}",
        task_id=payload.task_id or f"manual-{int(__import__('time').time() * 1000)}",
        objective=payload.objective,
        outcome=outcome,
        steps=payload.steps,
        error=payload.error,
        correction=payload.correction,
    )
    trace_id = store.record_trace(trace)
    return {"status": "ok", "trace_id": trace_id}


@router.post("/search")
async def search_experiences(payload: SearchRequest) -> Dict[str, Any]:
    store = _get_store()
    results = store.search_experiences(payload.query, max_results=payload.max_results)
    return {"status": "ok", "query": payload.query, "count": len(results), "results": results}


@router.post("/inject")
async def inject_experience(payload: SearchRequest) -> Dict[str, Any]:
    context = vibe_orchestrator.inject_experience_context(payload.query, max_results=payload.max_results)
    return {"status": "ok", "query": payload.query, "context": context}


@router.get("/experiences/success")
async def successful_experiences(limit: int = 20) -> Dict[str, Any]:
    store = _get_store()
    traces = store.list_traces(outcome="success", limit=limit)
    return {"count": len(traces), "traces": traces}


@router.get("/experiences/failed")
async def failed_experiences(limit: int = 20) -> Dict[str, Any]:
    store = _get_store()
    traces = store.list_traces(outcome="failed", limit=limit)
    return {"count": len(traces), "traces": traces}


@router.get("/experiences/corrected")
async def corrected_experiences(limit: int = 20) -> Dict[str, Any]:
    store = _get_store()
    traces = store.list_traces(outcome="corrected", limit=limit)
    return {"count": len(traces), "traces": traces}


@router.delete("/traces/{trace_id}")
async def delete_trace(trace_id: str) -> Dict[str, Any]:
    store = _get_store()
    trace = store.get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="trace_not_found")
    return {"status": "ok", "trace_id": trace_id, "deleted": True}