"""BLOQUE 85 - Recovery Management REST + WebSocket Handlers (/api/recovery)."""
from __future__ import annotations
import asyncio
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from backend.recovery.snapshot import get_recovery_engine
router = APIRouter(prefix="/api/recovery", tags=["recovery"])

class SnapshotRequest(BaseModel):
    sources: Dict[str, str] = {}
    kind: str = "full"
    label: str = ""

class RestoreRequest(BaseModel):
    dest_dir: str = ""
    overwrite: bool = False

@router.get("/status")
async def recovery_status() -> Dict[str, Any]:
    eng = get_recovery_engine()
    snaps = eng.list_snapshots()
    return {"online": True, "runner": "local", "snapshots": len(snaps),
            "recoveries": len(eng.recoveries()), "offline_only": True}

@router.post("/snapshot")
async def create_snapshot(req: SnapshotRequest) -> Dict[str, Any]:
    if not req.sources:
        raise HTTPException(status_code=422, detail="sources vacias")
    try:
        meta = get_recovery_engine().create_snapshot(req.sources, req.kind, req.label)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return meta.to_dict()

@router.get("/snapshots")
async def list_snapshots() -> Dict[str, Any]:
    snaps = get_recovery_engine().list_snapshots()
    return {"count": len(snaps), "snapshots": [s.to_dict() for s in snaps]}

@router.get("/snapshots/{snapshot_id}")
async def snapshot_detail(snapshot_id: str) -> Dict[str, Any]:
    meta = get_recovery_engine().get(snapshot_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="snapshot not found")
    return meta.to_dict()

@router.post("/snapshots/{snapshot_id}/verify")
async def verify_snapshot(snapshot_id: str) -> Dict[str, Any]:
    return get_recovery_engine().verify(snapshot_id)

@router.delete("/snapshots/{snapshot_id}")
async def delete_snapshot(snapshot_id: str) -> Dict[str, Any]:
    ok = get_recovery_engine().delete(snapshot_id)
    if not ok:
        raise HTTPException(status_code=404, detail="snapshot not found")
    return {"deleted": True, "snapshot_id": snapshot_id}

@router.post("/snapshots/{snapshot_id}/restore")
async def restore_snapshot(snapshot_id: str, req: RestoreRequest) -> Dict[str, Any]:
    if not req.dest_dir:
        raise HTTPException(status_code=422, detail="dest_dir requerido")
    out = get_recovery_engine().restore(snapshot_id, req.dest_dir, req.overwrite)
    if not out.get("restored"):
        raise HTTPException(status_code=409, detail=out.get("reason", "restore failed"))
    return out

@router.get("/recoveries")
async def list_recoveries(limit: int = 50) -> Dict[str, Any]:
    recs = get_recovery_engine().recoveries(limit=min(200, max(1, limit)))
    return {"count": len(recs), "recoveries": recs, "offline_only": True}


class RollbackRequest(BaseModel):
    dest_dir: str = ""
    overwrite: bool = False


@router.post("/rollback")
async def rollback_last_stable(req: RollbackRequest) -> Dict[str, Any]:
    """Automated disaster recovery: restaura el ultimo snapshot verificado."""
    if not req.dest_dir:
        raise HTTPException(status_code=422, detail="dest_dir requerido")
    out = get_recovery_engine().rollback_last_stable(req.dest_dir, req.overwrite)
    if not out.get("rolled_back"):
        raise HTTPException(status_code=409, detail=out.get("reason", "rollback failed"))
    return out

@router.websocket("/ws")
async def recovery_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    queue: asyncio.Queue = asyncio.Queue()
    def _cb(evt: Dict[str, Any]) -> None:
        try:
            queue.put_nowait(evt)
        except Exception:
            pass
    get_recovery_engine().on_recovery(_cb)
    try:
        while True:
            try:
                evt = await asyncio.wait_for(queue.get(), timeout=1.0)
                await websocket.send_json({"event": "restored", **evt})
            except asyncio.TimeoutError:
                eng = get_recovery_engine()
                await websocket.send_json({"event": "heartbeat",
                    "snapshots": len(eng.list_snapshots()), "offline_only": True})
    except (WebSocketDisconnect, Exception):
        pass
