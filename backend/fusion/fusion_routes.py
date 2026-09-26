"""BLOQUE 83 - Context Fusion REST + WebSocket Handlers (/api/fusion). 100% offline."""
from __future__ import annotations
import asyncio
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from backend.fusion.sensory import VALID_SOURCES, VALID_SEVERITIES, get_fusion_engine
router = APIRouter(prefix="/api/fusion", tags=["fusion"])

class IngestRequest(BaseModel):
    source: str = "system"
    kind: str = "generic"
    payload: Dict[str, Any] = {}
    severity: str = "info"

class IngestBatch(BaseModel):
    events: List[IngestRequest] = []

@router.get("/status")
async def fusion_status() -> Dict[str, Any]:
    eng = get_fusion_engine()
    last = eng.last()
    return {"online": True, "runner": "local", "buffered_events": len(eng.bus),
            "sources": list(VALID_SOURCES), "severities": list(VALID_SEVERITIES),
            "last_state": (last.state if last else None), "offline_only": True}

@router.post("/ingest")
async def ingest_event(req: IngestRequest) -> Dict[str, Any]:
    try:
        ev = get_fusion_engine().ingest(req.source, req.kind, req.payload, req.severity)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return ev.to_dict()

@router.post("/ingest/batch")
async def ingest_batch(batch: IngestBatch) -> Dict[str, Any]:
    eng = get_fusion_engine()
    out = []
    for req in batch.events[:200]:
        try:
            out.append(eng.ingest(req.source, req.kind, req.payload, req.severity).to_dict())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
    return {"count": len(out), "events": out, "offline_only": True}

@router.get("/context")
async def fusion_context(window_s: float = 30.0) -> Dict[str, Any]:
    return get_fusion_engine().snapshot(window_s=window_s).to_dict()

@router.get("/history")
async def fusion_history(limit: int = 20) -> Dict[str, Any]:
    snaps = get_fusion_engine().history(limit=min(100, max(1, limit)))
    return {"count": len(snaps), "snapshots": [s.to_dict() for s in snaps]}

@router.post("/reset")
async def fusion_reset() -> Dict[str, Any]:
    cleared = get_fusion_engine().reset()
    cleared["offline_only"] = True
    return cleared

@router.websocket("/ws")
async def fusion_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            snap = get_fusion_engine().snapshot(window_s=30.0)
            await websocket.send_json({"state": snap.state, "fused_score": snap.fused_score,
                                       "event_count": snap.event_count, "anomalies": snap.anomalies,
                                       "offline_only": True})
            await asyncio.sleep(1.0)
    except (WebSocketDisconnect, Exception):
        pass
