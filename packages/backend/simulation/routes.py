"""BLOQUE 99 - REST + WebSocket para /api/simulation/infinite. 100% offline."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from backend.simulation.engine import (
    get_engine,
    reset_engine,
    ScenarioConfig,
    MAX_AGENTS,
    MAX_STEPS,
)

router = APIRouter(prefix="/api/simulation/infinite", tags=["simulation"])


class ScenarioRequest(BaseModel):
    name: str = "stress"
    agents: int = Field(default=8, ge=1, le=MAX_AGENTS)
    steps: int = Field(default=100, ge=1, le=MAX_STEPS)
    seed: int = 42
    faults: List[Dict[str, Any]] = []
    replication_rate: float = Field(default=0.3, ge=0.0, le=1.0)
    gamma: float = Field(default=0.95, ge=0.0, le=0.999)


class OptimizeRequest(BaseModel):
    iterations: Optional[int] = Field(default=None, ge=1, le=200)


class StressRequest(BaseModel):
    agents: int = Field(default=16, ge=1, le=MAX_AGENTS)
    seed: int = 99


@router.get("/status", tags=["simulation"])
async def sim_status() -> Dict[str, Any]:
    return get_engine().status()


@router.post("/scenario", tags=["simulation"])
async def run_scenario(req: ScenarioRequest) -> Dict[str, Any]:
    cfg = ScenarioConfig(**req.model_dump())
    return get_engine().run_scenario(cfg).to_dict()


@router.post("/stress", tags=["simulation"])
async def run_stress(req: StressRequest) -> Dict[str, Any]:
    try:
        return get_engine().stress_suite(agents=req.agents, seed=req.seed)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/optimize", tags=["simulation"])
async def run_optimize(req: OptimizeRequest) -> Dict[str, Any]:
    return get_engine().optimization_report(req.iterations)


@router.get("/results", tags=["simulation"])
async def list_results() -> Dict[str, Any]:
    eng = get_engine()
    with eng._lock:
        return {"count": len(eng.results),
                "results": [r.to_dict() for r in eng.results]}


@router.post("/reset", tags=["simulation"])
async def sim_reset() -> Dict[str, Any]:
    reset_engine()
    get_engine()
    return {"reset": True}


class _WSConn:
    def __init__(self) -> None:
        self.active: set = set()


_ws = _WSConn()


@router.websocket("/ws")
async def simulation_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    _ws.active.add(websocket)
    try:
        while True:
            await websocket.send_json({"event": "heartbeat",
                                       "status": get_engine().status(),
                                       "offline_only": True})
            await asyncio.sleep(2.0)
    except (WebSocketDisconnect, Exception):
        _ws.active.discard(websocket)
