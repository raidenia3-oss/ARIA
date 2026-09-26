"""BLOQUE 103 - REST + WebSocket de diagnostico (/api/testing/matrix)."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from backend.testing.engine import get_matrix
from backend.testing.models import ALL_CHAIN_STEPS
from backend.testing.stress import get_stress

router = APIRouter(prefix="/api/testing/matrix", tags=["testing-matrix"])


class MatrixRunRequest(BaseModel):
    steps: Optional[List[str]] = None
    timeout_s: float = Field(default=10.0, ge=0.05, le=60.0)


class StressRunRequest(BaseModel):
    agents: int = Field(default=8, ge=1, le=64)
    ops_per_agent: int = Field(default=10, ge=1, le=50)
    inject_faults: bool = False
    timeout_s: float = Field(default=10.0, ge=1.0, le=60.0)


@router.get("/status")
async def matrix_status() -> Dict[str, Any]:
    m = get_matrix().last()
    s = get_stress().last()
    return {"online": True, "runner": "local",
            "chain_steps": list(ALL_CHAIN_STEPS),
            "last_matrix": (m.to_dict() if m else None),
            "last_stress": (s.to_dict() if s else None),
            "offline_only": True}


@router.get("/contracts")
async def matrix_contracts() -> Dict[str, Any]:
    return {"block": 103, "prefix": router.prefix,
            "chain_steps": list(ALL_CHAIN_STEPS),
            "endpoints": [
                {"method": "GET", "path": "/api/testing/matrix/status"},
                {"method": "GET", "path": "/api/testing/matrix/contracts"},
                {"method": "POST", "path": "/api/testing/matrix/run"},
                {"method": "GET", "path": "/api/testing/matrix/report"},
                {"method": "GET", "path": "/api/testing/matrix/history"},
                {"method": "POST", "path": "/api/testing/matrix/stress"},
                {"method": "GET", "path": "/api/testing/matrix/stress/report"},
                {"method": "GET", "path": "/api/testing/matrix/stress/history"},
                {"method": "POST", "path": "/api/testing/matrix/reset"},
                {"method": "WS", "path": "/api/testing/matrix/ws"},
            ],
            "offline_only": True}


@router.post("/run")
async def matrix_run(req: MatrixRunRequest) -> Dict[str, Any]:
    if req.steps:
        unknown = [s for s in req.steps if s not in ALL_CHAIN_STEPS]
        if unknown:
            raise HTTPException(400, f"steps desconocidos: {unknown}")
    get_matrix().timeout_s = max(0.05, min(60.0, req.timeout_s))
    rep = await asyncio.to_thread(get_matrix().run_chain, req.steps)
    return rep.to_dict()


@router.get("/report")
async def matrix_report() -> Dict[str, Any]:
    m = get_matrix().last()
    if m is None:
        raise HTTPException(404, "no_matrix_report")
    return m.to_dict()


@router.get("/history")
async def matrix_history(limit: int = 10) -> Dict[str, Any]:
    items = get_matrix().history(limit=min(20, max(1, limit)))
    return {"count": len(items),
            "reports": [r.to_dict() for r in items],
            "offline_only": True}


@router.post("/stress")
async def stress_run(req: StressRunRequest) -> Dict[str, Any]:
    rep = await asyncio.to_thread(
        get_stress().run, req.agents, req.ops_per_agent,
        req.inject_faults, req.timeout_s)
    return rep.to_dict()


@router.get("/stress/report")
async def stress_report() -> Dict[str, Any]:
    s = get_stress().last()
    if s is None:
        raise HTTPException(404, "no_stress_report")
    return s.to_dict()


@router.get("/stress/history")
async def stress_history(limit: int = 10) -> Dict[str, Any]:
    items = get_stress().history(limit=min(20, max(1, limit)))
    return {"count": len(items),
            "reports": [r.to_dict() for r in items],
            "offline_only": True}


@router.post("/reset")
async def matrix_reset() -> Dict[str, Any]:
    get_matrix().reset()
    get_stress().reset()
    return {"reset": True, "offline_only": True}


@router.websocket("/ws")
async def matrix_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            m = get_matrix().last()
            s = get_stress().last()
            await websocket.send_json({
                "event": "testing_heartbeat",
                "matrix": (m.to_dict() if m else None),
                "stress": (s.to_dict() if s else None),
                "offline_only": True})
            await asyncio.sleep(2.0)
    except (WebSocketDisconnect, Exception):
        pass
