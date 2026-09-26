"""BLOQUE 102 - REST + WebSocket para /api/ai/federated. 100% offline."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from backend.ai.federated import DEFAULT_CLIP_NORM, get_engine, reset_engine

router = APIRouter(prefix="/api/ai/federated", tags=["federated"])


class StartRoundRequest(BaseModel):
    min_nodes: int = Field(default=2, ge=2, le=64)
    clip_norm: float = Field(default=DEFAULT_CLIP_NORM, gt=0)


class SubmitUpdateRequest(BaseModel):
    node_id: str
    ciphertext_b64: str
    hmac_sha256: str
    weight: float = Field(default=1.0, ge=0)


@router.get("/status")
async def fed_status() -> Dict[str, Any]:
    return get_engine().status()


@router.post("/round/start")
async def fed_start(req: StartRoundRequest) -> Dict[str, Any]:
    return get_engine().start_round(min_nodes=req.min_nodes, clip_norm=req.clip_norm)


@router.post("/round/{round_id}/submit")
async def fed_submit(round_id: str, req: SubmitUpdateRequest) -> Dict[str, Any]:
    res = get_engine().submit_update(round_id, req.node_id, req.ciphertext_b64,
                                     req.hmac_sha256, req.weight)
    if not res.get("accepted"):
        raise HTTPException(400, res.get("error", "update_rejected"))
    return res


@router.post("/round/{round_id}/aggregate")
async def fed_aggregate(round_id: str) -> Dict[str, Any]:
    res = get_engine().aggregate(round_id)
    if not res.get("aggregated"):
        raise HTTPException(400, res.get("error", "aggregation_failed"))
    return res


@router.get("/round/{round_id}")
async def fed_round(round_id: str) -> Dict[str, Any]:
    r = get_engine().get_round(round_id)
    if r is None:
        raise HTTPException(404, "round_not_found")
    return r


@router.get("/rounds")
async def fed_rounds() -> Dict[str, Any]:
    rs = get_engine().list_rounds()
    return {"count": len(rs), "rounds": rs, "offline_only": True}


@router.post("/reset")
async def fed_reset() -> Dict[str, Any]:
    reset_engine()
    get_engine()
    return {"reset": True, "offline_only": True}


class _WSConn:
    def __init__(self) -> None:
        self.active: set = set()


_ws = _WSConn()


@router.websocket("/ws")
async def federated_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    _ws.active.add(websocket)
    try:
        while True:
            await websocket.send_json({"event": "federated_heartbeat",
                                       "status": get_engine().status(),
                                       "offline_only": True})
            await asyncio.sleep(2.0)
    except (WebSocketDisconnect, Exception):
        _ws.active.discard(websocket)
