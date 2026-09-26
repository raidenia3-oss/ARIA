"""Disaster recovery routes for AURA."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.disaster_recovery import DisasterRecoveryManager

router = APIRouter(prefix="/api/disaster-recovery", tags=["disaster-recovery"])
dr_manager = DisasterRecoveryManager()


@router.get("/backups")
async def list_backups() -> Dict[str, Any]:
    return dr_manager.list_backups()


@router.post("/backups")
async def create_backup(payload: Dict[str, Any]) -> Dict[str, Any]:
    source = str(payload.get("source", "system"))
    result = dr_manager.create_snapshot(source=source)
    return result


@router.post("/backups/{backup_id}/finalize")
async def finalize_backup(backup_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    size_bytes = int(payload.get("size_bytes", 0))
    encrypted = bool(payload.get("encrypted", False))
    result = dr_manager.finalize_snapshot(backup_id, size_bytes=size_bytes, encrypted=encrypted)
    if "error" in result:
        return JSONResponse(status_code=404, content=result)
    return result


@router.post("/backups/{backup_id}/verify")
async def verify_backup(backup_id: str) -> Dict[str, Any]:
    return dr_manager.verify_snapshot(backup_id)


@router.post("/restore")
async def restore_backup(payload: Dict[str, Any]) -> Dict[str, Any]:
    backup_id = str(payload.get("backup_id", ""))
    target = str(payload.get("target", "current"))
    if not backup_id:
        return JSONResponse(status_code=400, content={"detail": "backup_id is required"})
    result = dr_manager.restore(backup_id, target=target)
    if result.get("status") == "failed":
        return JSONResponse(status_code=400, content=result)
    return result
