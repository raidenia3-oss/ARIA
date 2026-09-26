"""BLOQUE 92 - REST + WebSocket para /api/planner/goals."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.planner.hierarchical import get_planner, reset_planner
from backend.planner.models import GoalStatus, MilestoneStatus

router = APIRouter(prefix="/api/planner/goals", tags=["planner"])


class DecomposeRequest(BaseModel):
    title: str = "Goal"
    description: str = ""
    parent_id: Optional[str] = None
    milestones: List[Dict[str, Any]] = []
    priority: int = 0
    deadline: Optional[str] = None


class MilestoneUpdateRequest(BaseModel):
    progress: Optional[float] = None
    status: Optional[str] = None


@router.get("/status", tags=["planner"])
async def planner_status() -> Dict[str, Any]:
    return get_planner().status()


@router.post("/decompose", tags=["planner"])
async def planner_decompose(req: DecomposeRequest) -> Dict[str, Any]:
    g = get_planner().decompose(
        title=req.title, description=req.description, parent_id=req.parent_id,
        milestones=req.milestones, priority=req.priority, deadline=req.deadline)
    return g.to_dict()


@router.get("/list", tags=["planner"])
async def planner_list(root_only: bool = False) -> Dict[str, Any]:
    goals = get_planner().list_goals(root_only=root_only)
    return {"count": len(goals), "goals": [g.to_dict() for g in goals]}


@router.get("/{goal_id}", tags=["planner"])
async def planner_get(goal_id: str) -> Dict[str, Any]:
    g = get_planner().get_goal(goal_id)
    if g is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="goal not found")
    return g.to_dict()


@router.post("/{goal_id}/milestone/{milestone_id}", tags=["planner"])
async def planner_update_milestone(goal_id: str, milestone_id: str, req: MilestoneUpdateRequest) -> Dict[str, Any]:
    status = MilestoneStatus(req.status) if req.status else None
    m = get_planner().update_milestone(goal_id, milestone_id, progress=req.progress, status=status)
    if m is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="milestone not found")
    return m.to_dict()


@router.post("/{goal_id}/replan", tags=["planner"])
async def planner_replan(goal_id: str, reason: str = "context_change") -> Dict[str, Any]:
    return get_planner().replan(goal_id, reason)


@router.post("/reset", tags=["planner"])
async def planner_reset() -> Dict[str, Any]:
    reset_planner()
    get_planner()
    return {"reset": True}


class _WSConn:
    def __init__(self) -> None:
        self.active: set = set()


_ws = _WSConn()


@router.websocket("/ws")
async def planner_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    _ws.active.add(websocket)
    try:
        while True:
            p = get_planner()
            await websocket.send_json({"event": "heartbeat", "status": p.status(), "offline_only": True})
            await asyncio.sleep(2.0)
    except (WebSocketDisconnect, Exception):
        _ws.active.discard(websocket)
