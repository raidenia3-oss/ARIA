"""Self-learning routes for AURA."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query

from backend.self_learning_manager import SelfLearningManager

router = APIRouter(prefix="/api/selflearn", tags=["self_learning"])

self_learning: SelfLearningManager | None = None


def init_self_learning(manager: SelfLearningManager) -> None:
    global self_learning
    self_learning = manager


@router.get("/config/current")
async def get_current_config() -> Dict[str, Any]:
    if self_learning is None:
        raise HTTPException(status_code=500, detail="Self-learning not initialized")
    return self_learning.get_current_config()


@router.get("/optimization/history")
async def get_optimization_history(limit: int = Query(10)) -> Dict[str, Any]:
    if self_learning is None:
        raise HTTPException(status_code=500, detail="Self-learning not initialized")
    history = await self_learning.get_optimization_history(limit)
    return {"recent_optimizations": history, "total_count": len(history)}


@router.get("/learning/events")
async def get_learning_events(limit: int = Query(10)) -> Dict[str, Any]:
    if self_learning is None:
        raise HTTPException(status_code=500, detail="Self-learning not initialized")
    events = await self_learning.get_learning_events(limit)
    return {"learning_events": events, "total_count": len(events)}


@router.get("/status")
async def self_learning_status() -> Dict[str, Any]:
    if self_learning is None:
        raise HTTPException(status_code=500, detail="Self-learning not initialized")
    return {
        "status": "autonomous",
        "learning_active": True,
        "optimization_active": True,
        "current_config": self_learning.get_current_config(),
        "message": "Sistema totalmente autónomo - Sin intervención necesaria",
    }
