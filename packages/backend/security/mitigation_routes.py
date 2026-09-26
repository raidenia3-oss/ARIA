"""BLOQUE 87 - Real-Time Threat Mitigation REST + WebSocket (/api/security/defense)."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.security.mitigation import get_defense_engine

router = APIRouter(prefix="/api/security/defense", tags=["security-defense"])


class FeedRequest(BaseModel):
    category: str = "process"
    signal: str = ""
    severity: str = "low"
    detail: Dict[str, Any] = {}


class ScanRequest(BaseModel):
    text: str = ""
    category: str = "process"


class RestoreRequest(BaseModel):
    record_id: str = ""


@router.get("/status")
async def defense_status() -> Dict[str, Any]:
    return get_defense_engine().status()


@router.post("/feed")
async def feed_event(req: FeedRequest) -> Dict[str, Any]:
    ev = get_defense_engine().detector.feed(req.category, req.signal,
                                             req.severity, req.detail)
    return ev.to_dict()


@router.post("/scan")
async def scan_text(req: ScanRequest) -> Dict[str, Any]:
    events = get_defense_engine().detector.scan_text(req.text, req.category)
    return {"count": len(events), "events": [e.to_dict() for e in events],
            "offline_only": True}


@router.post("/evaluate")
async def evaluate_threats() -> Dict[str, Any]:
    alerts = get_defense_engine().evaluate()
    return {"count": len(alerts), "alerts": [a.to_dict() for a in alerts],
            "offline_only": True}


@router.get("/alerts")
async def list_alerts(status: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
    items = get_defense_engine().alerts(status, limit=min(500, max(1, limit)))
    return {"count": len(items), "alerts": [a.to_dict() for a in items]}


@router.get("/quarantine")
async def list_quarantine(limit: int = 100) -> Dict[str, Any]:
    items = get_defense_engine().quarantine(limit=min(500, max(1, limit)))
    return {"count": len(items), "records": [q.to_dict() for q in items],
            "offline_only": True}


@router.post("/quarantine/{record_id}/restore")
async def restore_quarantine(record_id: str) -> Dict[str, Any]:
    out = get_defense_engine().restore(record_id)
    if not out.get("restored"):
        raise HTTPException(status_code=409, detail=out.get("reason", "restore failed"))
    return out


@router.post("/reset")
async def defense_reset() -> Dict[str, Any]:
    get_defense_engine().reset()
    return {"reset": True, "offline_only": True}


@router.websocket("/ws")
async def defense_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    queue: asyncio.Queue = asyncio.Queue()
    get_defense_engine().on_alert(queue.put_nowait)
    try:
        while True:
            try:
                evt = await asyncio.wait_for(queue.get(), timeout=1.0)
                await websocket.send_json(evt)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "heartbeat",
                                           **get_defense_engine().status()})
    except (WebSocketDisconnect, Exception):
        pass