"""BLOQUE 96 - REST + WebSocket para /api/resilience/healing."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.resilience.self_healing import (
    get_self_healing_engine,
    reset_self_healing_engine,
    router as self_healing_router,
)

router = APIRouter(prefix="/api/resilience/healing", tags=["resilience-healing"])


class ThresholdsRequest(BaseModel):
    thresholds: Dict[str, Any] = {}


class FaultInjectRequest(BaseModel):
    kind: str
    detail: str = ""
    severity: str = "warning"


class RemediateRequest(BaseModel):
    action: str
    detail: str = ""


@router.get("/status", tags=["resilience-healing"])
async def healing_status() -> Dict[str, Any]:
    return get_self_healing_engine().status()


@router.get("/faults", tags=["resilience-healing"])
async def healing_faults(limit: int = 50) -> Dict[str, Any]:
    eng = get_self_healing_engine()
    faults = eng.faults(limit=limit)
    return {"count": len(faults), "faults": [f.to_dict() for f in faults]}


@router.get("/actions", tags=["resilience-healing"])
async def healing_actions(limit: int = 50) -> Dict[str, Any]:
    eng = get_self_healing_engine()
    actions = eng.actions(limit=limit)
    return {"count": len(actions), "actions": [a.to_dict() for a in actions]}


@router.post("/scan", tags=["resilience-healing"])
async def healing_scan() -> Dict[str, Any]:
    return get_self_healing_engine().scan_once()


@router.post("/faults/inject", tags=["resilience-healing"])
async def healing_inject_fault(req: FaultInjectRequest) -> Dict[str, Any]:
    f = get_self_healing_engine().inject_fault(req.kind, req.detail, req.severity)
    return f.to_dict()


@router.post("/remediate", tags=["resilience-healing"])
async def healing_remediate(req: RemediateRequest) -> Dict[str, Any]:
    a = get_self_healing_engine().force_remediate(req.action, req.detail)
    return a.to_dict()


@router.get("/thresholds", tags=["resilience-healing"])
async def healing_thresholds() -> Dict[str, Any]:
    return {"thresholds": get_self_healing_engine().thresholds()}


@router.post("/thresholds", tags=["resilience-healing"])
async def healing_update_thresholds(req: ThresholdsRequest) -> Dict[str, Any]:
    return {"thresholds": get_self_healing_engine().update_thresholds(req.thresholds)}


@router.post("/reset", tags=["resilience-healing"])
async def healing_reset() -> Dict[str, Any]:
    get_self_healing_engine().reset()
    return {"reset": True}


class _WSConn:
    def __init__(self) -> None:
        self.active: set = set()
        self._loop = None

    def set_loop(self, loop) -> None:
        self._loop = loop

    def broadcast(self, payload: Dict[str, Any]) -> None:
        if not self.active:
            return
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        for ws in list(self.active):
            try:
                coro = ws.send_json(payload)
                if asyncio.iscoroutine(coro):
                    loop.call_soon_threadsafe(asyncio.ensure_future, coro)
            except Exception:
                self.active.discard(ws)


_ws = _WSConn()


@router.websocket("/ws")
async def healing_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    _ws.active.add(websocket)
    try:
        _ws.set_loop(asyncio.get_running_loop())
    except Exception:
        pass
    eng = get_self_healing_engine()
    eng.on_event(_ws.broadcast)
    try:
        while True:
            await websocket.send_json({"event": "heartbeat", "status": eng.status()})
            await asyncio.sleep(2.0)
    except (WebSocketDisconnect, Exception):
        _ws.active.discard(websocket)