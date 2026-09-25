"""Swarm coordination routes."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/swarm", tags=["swarm"])


@router.get("/status")
async def swarm_status():
    return {"status": "ok", "agents": 0}
