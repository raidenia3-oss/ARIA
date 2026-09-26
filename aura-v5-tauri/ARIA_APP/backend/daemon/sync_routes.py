"""Daemon sync routes."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/daemon/sync", tags=["daemon-sync"])


@router.get("/status")
async def sync_status():
    return {"status": "ok", "daemons": "ready"}
