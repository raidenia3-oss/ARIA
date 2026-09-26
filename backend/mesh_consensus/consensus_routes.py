"""BLOQUE 89 - Consensus & negotiation REST + WebSocket (/api/mesh/consensus)."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.mesh_consensus import get_consensus_engine

router = APIRouter(prefix="/api/mesh/consensus", tags=["mesh-consensus"])


class RoundRequest(BaseModel):
    topic: str = ""
    proposal: str = ""
    voters: List[str] = []
    ttl_s: float = 30.0


class VoteRequest(BaseModel):
    voter: str = ""
    choice: str = "abstain"


class TaskRequest(BaseModel):
    title: str = ""
    payload: Dict[str, Any] = {}
    requester: str = "local"


class BidRequest(BaseModel):
    node_id: str = ""
    capacity: float = 0.5


@router.get("/status")
async def consensus_status() -> Dict[str, Any]:
    eng = get_consensus_engine()
    return {"online": True, "runner": "local",
            "rounds": len(eng.rounds(limit=200)),
            "tasks": len(eng.tasks(limit=200)), "offline_only": True}


@router.post("/rounds")
async def open_round(req: RoundRequest) -> Dict[str, Any]:
    try:
        rnd = get_consensus_engine().open_round(
            req.topic, req.proposal, req.voters, req.ttl_s)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return rnd.to_dict()


@router.post("/rounds/{round_id}/vote")
async def cast_vote(round_id: str, req: VoteRequest) -> Dict[str, Any]:
    out = get_consensus_engine().vote(round_id, req.voter, req.choice)
    if not out.get("voted"):
        raise HTTPException(status_code=409, detail=out.get("reason", "vote failed"))
    return out


@router.get("/rounds")
async def list_rounds(limit: int = 50) -> Dict[str, Any]:
    items = get_consensus_engine().rounds(limit=min(200, max(1, limit)))
    return {"count": len(items), "rounds": [r.to_dict() for r in items]}


@router.post("/tasks")
async def publish_task(req: TaskRequest) -> Dict[str, Any]:
    try:
        return get_consensus_engine().publish_task(
            req.title, req.payload, req.requester)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/tasks/{task_id}/bid")
async def place_bid(task_id: str, req: BidRequest) -> Dict[str, Any]:
    if not req.node_id:
        raise HTTPException(status_code=422, detail="node_id requerido")
    out = get_consensus_engine().bid(task_id, req.node_id, req.capacity)
    if not out.get("bid"):
        raise HTTPException(status_code=409, detail=out.get("reason", "bid failed"))
    return out


@router.get("/tasks")
async def list_tasks(limit: int = 50) -> Dict[str, Any]:
    items = get_consensus_engine().tasks(limit=min(200, max(1, limit)))
    return {"count": len(items), "tasks": items}


@router.websocket("/ws")
async def consensus_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    queue: asyncio.Queue = asyncio.Queue()
    get_consensus_engine().on_event(queue.put_nowait)
    try:
        while True:
            try:
                evt = await asyncio.wait_for(queue.get(), timeout=1.0)
                await websocket.send_json({"event": evt.get("type", "event"), **evt})
            except asyncio.TimeoutError:
                eng = get_consensus_engine()
                await websocket.send_json({
                    "event": "heartbeat", "rounds": len(eng.rounds(limit=200)),
                    "tasks": len(eng.tasks(limit=200)), "offline_only": True})
    except (WebSocketDisconnect, Exception):
        pass
