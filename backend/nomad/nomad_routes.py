"""N.O.M.A.D. REST routes."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from backend.nomad.nomad_manager import NomadManager

router = APIRouter(prefix="/api/nomad", tags=["nomad"])
nomad_manager = NomadManager()


@router.get("/health")
async def nomad_health() -> Dict[str, Any]:
    data = await nomad_manager.health_check_all()
    degraded = [k for k, v in data.items() if v.get("status") != "healthy"]
    return {
        "status": "healthy" if not degraded else "degraded",
        "degraded_services": degraded,
        "services": data,
    }


@router.get("/status")
async def nomad_status() -> Dict[str, Any]:
    return await nomad_manager.get_status()


@router.get("/compose")
async def nomad_compose() -> Dict[str, Any]:
    return {"docker_compose": nomad_manager.compose_template()}


@router.post("/rag/ingest")
async def nomad_rag_ingest(document: Dict[str, Any]) -> Dict[str, Any]:
    if not document.get("text") and not document.get("content"):
        raise HTTPException(status_code=400, detail="document.text or document.content is required")
    return await nomad_manager.ingest_document(document)


@router.post("/rag/query")
async def nomad_rag_query(payload: Dict[str, Any]) -> Dict[str, Any]:
    query = str(payload.get("query", "")).strip()
    limit = int(payload.get("limit", 5))
    if not query:
        raise HTTPException(status_code=400, detail="query is required")
    return await nomad_manager.rag_query(query, limit=limit)
