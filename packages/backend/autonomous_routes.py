"""API routes for the autonomous agent."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from backend.integrations.autonomous_agent import (
    autonomous_agent,
    SessionConfig,
)

router = APIRouter(prefix="/api/autonomous", tags=["autonomous"])


class StartSessionRequest(BaseModel):
    name: str = Field(..., description="Session name")
    duration_minutes: int = Field(default=60, ge=1, le=1440)
    keep_awake: bool = Field(default=True)
    freeze_distractions: bool = Field(default=True)
    health_threshold: float = Field(default=0.0)
    notify_on_complete: bool = Field(default=True)
    tmux_pane: Optional[str] = Field(None)


class EndSessionRequest(BaseModel):
    name: str = Field(..., description="Session name to end")


@router.get("/status")
def get_autonomous_status():
    """Get autonomous agent status."""
    return autonomous_agent.get_status()


@router.post("/session/start")
async def start_autonomous_session(req: StartSessionRequest):
    """Start an autonomous background session with sleep prevention."""
    config = SessionConfig(
        name=req.name,
        duration_minutes=req.duration_minutes,
        keep_awake=req.keep_awake,
        freeze_distractions=req.freeze_distractions,
        health_threshold=req.health_threshold,
        notify_on_complete=req.notify_on_complete,
        tmux_pane=req.tmux_pane,
    )
    success = await autonomous_agent.start_session(config)
    return {
        "status": "ok" if success else "partial",
        "session": req.name,
        "keep_awake": req.keep_awake,
        "duration_minutes": req.duration_minutes,
    }


@router.post("/session/end")
async def end_autonomous_session(req: EndSessionRequest):
    """End an autonomous background session."""
    await autonomous_agent.end_session(req.name)
    return {"status": "ok", "session": req.name}
