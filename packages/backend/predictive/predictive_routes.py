"""BLOQUE 84 - Predictive Engine REST + WebSocket Handlers (/api/scheduler/predictive)."""
from __future__ import annotations
import asyncio
from typing import Any, Dict, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from backend.predictive.intent import get_predictive_engine
router = APIRouter(prefix="/api/scheduler/predictive", tags=["predictive"])

class ObserveRequest(BaseModel):
    sources: Dict[str, int] = {}
    fused_score: float = 0.0
    state: str = "nominal"

class ObserveFusionRequest(BaseModel):
    window_s: float = 30.0

@router.get("/status")
async def predictive_status() -> Dict[str, Any]:
    eng = get_predictive_engine()
    return {"online": True, "runner": "local", "hypotheses": len(eng.hypotheses()),
            "tasks": len(eng.tasks()), "offline_only": True}

@router.post("/observe")
async def observe_context(req: ObserveRequest) -> Dict[str, Any]:
    return get_predictive_engine().observe(req.sources, req.fused_score, req.state)

@router.post("/observe-fusion")
async def observe_fusion(req: ObserveFusionRequest) -> Dict[str, Any]:
    from backend.fusion.sensory import get_fusion_engine
    snap = get_fusion_engine().snapshot(window_s=req.window_s)
    return get_predictive_engine().observe(snap.sources, snap.fused_score, snap.state)

@router.get("/hypotheses")
async def list_hypotheses(limit: int = 50) -> Dict[str, Any]:
    hs = get_predictive_engine().hypotheses(limit=min(200, max(1, limit)))
    return {"count": len(hs), "hypotheses": [h.to_dict() for h in hs]}

@router.get("/tasks")
async def list_tasks(limit: int = 50) -> Dict[str, Any]:
    ts = get_predictive_engine().tasks(limit=min(200, max(1, limit)))
    return {"count": len(ts), "tasks": [t.to_dict() for t in ts]}

@router.get("/ledger")
async def anticipation_ledger(limit: int = 50) -> Dict[str, Any]:
    log = get_predictive_engine().ledger(limit=min(200, max(1, limit)))
    return {"count": len(log), "entries": log, "offline_only": True}

@router.post("/confirm/{hypothesis_id}")
async def confirm_hypothesis(hypothesis_id: str) -> Dict[str, Any]:
    return get_predictive_engine().confirm(hypothesis_id)

@router.post("/reset")
async def predictive_reset() -> Dict[str, Any]:
    get_predictive_engine().reset()
    return {"reset": True, "offline_only": True}

@router.websocket("/ws")
async def predictive_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            eng = get_predictive_engine()
            await websocket.send_json({"hypotheses": len(eng.hypotheses()),
                "tasks": len(eng.tasks()), "pending": len([h for h in eng.hypotheses() if h.confidence < 0.8]),
                "offline_only": True})
            await asyncio.sleep(1.0)
    except (WebSocketDisconnect, Exception):
        pass
