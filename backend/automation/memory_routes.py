"""BLOQUE 76 - Process Memory Inspector REST API.

Endpoints under /api/automation/memory:
- GET    /status
- GET    /processes
- POST   /authorize
- POST   /revoke
- POST   /scan
- POST   /read
- POST   /write
- POST   /watchpoint
- GET    /watchpoints
- DELETE /watchpoint/{wid}
- POST   /watchpoints/start
- POST   /watchpoints/stop
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.automation.memory_injector import (
    get_memory_inspector,
    reset_memory_inspector,
)

logger = logging.getLogger("AURA.Memory.Routes")

router = APIRouter(prefix="/api/automation/memory", tags=["automation", "memory"])


class AuthorizeRequest(BaseModel):
    pid: Optional[int] = None
    name: Optional[str] = None


class ScanRequest(BaseModel):
    pid: int
    pattern: str
    max_results: int = 100


class ReadRequest(BaseModel):
    pid: int
    address: int
    size: int = 4
    dtype: str = "int32"


class WriteRequest(BaseModel):
    pid: int
    address: int
    value: Any
    dtype: str = "int32"


class WatchpointRequest(BaseModel):
    pid: int
    address: int
    size: int = 4


def _inspector():
    try:
        return get_memory_inspector()
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/status")
async def memory_status() -> Dict[str, Any]:
    ins = _inspector()
    return ins.status()


@router.get("/processes")
async def memory_processes() -> List[dict]:
    ins = _inspector()
    return ins.list_processes()


@router.post("/authorize")
async def memory_authorize(req: AuthorizeRequest) -> Dict[str, Any]:
    ins = _inspector()
    if req.pid is not None:
        ins.authorize_pid(int(req.pid))
    if req.name:
        ins.authorize_name(str(req.name))
    return {"ok": True, "authorized": ins.scope.to_dict()}


@router.post("/revoke")
async def memory_revoke(req: AuthorizeRequest) -> Dict[str, Any]:
    ins = _inspector()
    if req.pid is not None:
        ins.revoke_pid(int(req.pid))
    return {"ok": True, "authorized": ins.scope.to_dict()}


@router.post("/scan")
async def memory_scan(req: ScanRequest) -> List[dict]:
    ins = _inspector()
    try:
        return ins.scan_pattern(req.pid, req.pattern, req.max_results)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/read")
async def memory_read(req: ReadRequest) -> Dict[str, Any]:
    ins = _inspector()
    try:
        value = ins.read(req.pid, req.address, req.size, req.dtype)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"pid": req.pid, "address": req.address, "dtype": req.dtype, "value": value}


@router.post("/write")
async def memory_write(req: WriteRequest) -> Dict[str, Any]:
    ins = _inspector()
    try:
        written = ins.write(req.pid, req.address, req.value, req.dtype)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"pid": req.pid, "address": req.address, "dtype": req.dtype, "bytes_written": written}


@router.post("/watchpoint")
async def memory_watchpoint(req: WatchpointRequest) -> Dict[str, Any]:
    ins = _inspector()
    try:
        wid = ins.add_watchpoint(req.pid, req.address, req.size)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "watchpoint_id": wid}


@router.get("/watchpoints")
async def memory_watchpoints() -> List[dict]:
    ins = _inspector()
    return ins.list_watchpoints()


@router.delete("/watchpoint/{wid}")
async def memory_delete_watchpoint(wid: int) -> Dict[str, Any]:
    ins = _inspector()
    removed = ins.remove_watchpoint(int(wid))
    return {"ok": removed}


@router.post("/watchpoints/start")
async def memory_watchpoints_start() -> Dict[str, Any]:
    ins = _inspector()
    ins.start_watchpoints()
    return {"ok": True}


@router.post("/watchpoints/stop")
async def memory_watchpoints_stop() -> Dict[str, Any]:
    ins = _inspector()
    ins.stop_watchpoints()
    return {"ok": True}


__all__ = ["router"]