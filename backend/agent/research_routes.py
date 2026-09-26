"""AURA Autonomous Deep Research REST endpoints (Bloque 63).

Permite iniciar misiones de investigacion autonoma y consultar los mapas de
conocimiento aprendidos en memoria a largo plazo.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.agent.deep_research import (
    DeepResearchEngine,
    get_research_engine,
    reset_research_engine,
)

logger = logging.getLogger("AURA.Agent.Research.Routes")

router = APIRouter(prefix="/api/agent/research", tags=["agent-research"])


def _engine() -> DeepResearchEngine:
    return get_research_engine()


class StartResearchRequest(BaseModel):
    question: str = Field(..., min_length=4, max_length=2000)
    sources: Optional[List[str]] = Field(default=None, max_items=50)
    seed_texts: Optional[List[str]] = Field(default=None, max_items=50)
    max_refine_depth: Optional[int] = Field(default=None, ge=0, le=8)
    metadata: Optional[Dict[str, Any]] = None


class SearchKnowledgeRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    max_results: int = Field(default=5, ge=1, le=30)


@router.post("/missions")
async def start_mission(payload: StartResearchRequest) -> Dict[str, Any]:
    engine = _engine()
    try:
        mission = engine.start_mission(
            question=payload.question,
            sources=payload.sources or [],
            seed_texts=payload.seed_texts or [],
            metadata=payload.metadata,
            max_refine_depth=payload.max_refine_depth,
        )
        return mission.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/missions")
async def list_missions(status: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
    engine = _engine()
    missions = engine.list_missions(status=status, limit=limit)
    return {"count": len(missions), "missions": missions}


@router.get("/missions/{mission_id}")
async def get_mission(mission_id: str) -> Dict[str, Any]:
    engine = _engine()
    mission = engine.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="mission_not_found")
    return mission.to_dict()


@router.get("/missions/{mission_id}/knowledge")
async def get_mission_knowledge(mission_id: str) -> Dict[str, Any]:
    engine = _engine()
    mission = engine.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="mission_not_found")
    return {
        "mission_id": mission.mission_id,
        "question": mission.question,
        "knowledge_map": mission.knowledge_map,
        "findings_count": len(mission.findings),
        "memory_ids": mission.memory_ids,
    }


@router.post("/search")
async def search_knowledge(payload: SearchKnowledgeRequest) -> Dict[str, Any]:
    engine = _engine()
    return engine.search_knowledge(payload.query, max_results=payload.max_results)


@router.get("/history")
async def research_history(limit: int = 20) -> Dict[str, Any]:
    engine = _engine()
    history = engine.history(limit=limit)
    return {"count": len(history), "history": history}


@router.get("/status")
async def research_status() -> Dict[str, Any]:
    return _engine().get_status()


__all__ = ["router"]