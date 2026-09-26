"""AURA Window Routes - REST API for Bloque 73 Desktop Window Manager.

Endpoints under /api/desktop/windows:
- GET  /api/desktop/windows/monitors
- GET  /api/desktop/windows/list
- POST /api/desktop/windows/move
- POST /api/desktop/windows/focus
- POST /api/desktop/windows/maximize
- POST /api/desktop/windows/restore
- POST /api/desktop/windows/close
- POST /api/desktop/windows/layouts
- GET  /api/desktop/windows/layouts
- POST /api/desktop/windows/layouts/apply
- POST /api/desktop/windows/layouts/capture
- DELETE /api/desktop/windows/layouts/{layout_id}
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.desktop.window_manager import (
    DesktopWindowManager,
    get_window_manager,
    reset_window_manager,
)

logger = logging.getLogger("AURA.Window.Routes")

router = APIRouter(prefix="/api/desktop/windows", tags=["desktop", "windows"])


class MoveRequest(BaseModel):
    handle: int
    x: int
    y: int
    width: int
    height: int


class LayoutCreateRequest(BaseModel):
    name: str
    description: str = ""
    slots: List[Dict[str, Any]] = []


class ApplyLayoutRequest(BaseModel):
    layout_id: str


class CaptureLayoutRequest(BaseModel):
    name: str
    description: str = ""


def _wm() -> DesktopWindowManager:
    return get_window_manager()


@router.get("/monitors")
async def list_monitors() -> Dict[str, Any]:
    """Return physical monitor descriptors."""
    wm = _wm()
    monitors = wm.get_monitors()
    return {
        "count": len(monitors),
        "monitors": [m.to_dict() for m in monitors],
        "virtual_screen": {
            "width": wm.enumerator._win32_available and __import__("ctypes").windll.user32.GetSystemMetrics(76) or 0,
            "height": wm.enumerator._win32_available and __import__("ctypes").windll.user32.GetSystemMetrics(77) or 0,
        },
    }


@router.get("/list")
async def list_windows(visible_only: bool = True) -> Dict[str, Any]:
    """Enumerate top-level OS windows."""
    wm = _wm()
    windows = wm.get_windows(visible_only=visible_only)
    return {
        "count": len(windows),
        "windows": [w.to_dict() for w in windows],
    }


@router.post("/move")
async def move_window(req: MoveRequest) -> Dict[str, Any]:
    """Move/resize a window by handle."""
    wm = _wm()
    ok = wm.move_window(req.handle, req.x, req.y, req.width, req.height)
    if not ok:
        raise HTTPException(status_code=400, detail="move_failed")
    return {"moved": True, "handle": req.handle}


@router.post("/focus")
async def focus_window(handle: int) -> Dict[str, Any]:
    """Bring a window to foreground."""
    wm = _wm()
    ok = wm.focus_window(handle)
    if not ok:
        raise HTTPException(status_code=400, detail="focus_failed")
    return {"focused": True, "handle": handle}


@router.post("/maximize")
async def maximize_window(handle: int) -> Dict[str, Any]:
    """Maximize a window."""
    wm = _wm()
    ok = wm.maximize_window(handle)
    if not ok:
        raise HTTPException(status_code=400, detail="maximize_failed")
    return {"maximized": True, "handle": handle}


@router.post("/restore")
async def restore_window(handle: int) -> Dict[str, Any]:
    """Restore a maximized/minimized window."""
    wm = _wm()
    ok = wm.restore_window(handle)
    if not ok:
        raise HTTPException(status_code=400, detail="restore_failed")
    return {"restored": True, "handle": handle}


@router.post("/close")
async def close_window(handle: int) -> Dict[str, Any]:
    """Send WM_CLOSE to a window."""
    wm = _wm()
    ok = wm.close_window(handle)
    if not ok:
        raise HTTPException(status_code=400, detail="close_failed")
    return {"closed": True, "handle": handle}


@router.post("/layouts")
async def create_layout(req: LayoutCreateRequest) -> Dict[str, Any]:
    """Persist a new spatial layout profile."""
    wm = _wm()
    layout = wm.create_layout(req.name, req.slots, req.description)
    return layout.to_dict()


@router.get("/layouts")
async def list_layouts() -> Dict[str, Any]:
    """List persisted layouts."""
    wm = _wm()
    layouts = wm.list_layouts()
    return {
        "count": len(layouts),
        "layouts": [l.to_dict() for l in layouts],
    }


@router.post("/layouts/apply")
async def apply_layout(req: ApplyLayoutRequest) -> Dict[str, Any]:
    """Apply a persisted layout to live windows."""
    wm = _wm()
    result = wm.apply_layout(req.layout_id)
    if not result.get("applied"):
        raise HTTPException(status_code=404, detail=result.get("reason", "apply_failed"))
    return result


@router.post("/layouts/capture")
async def capture_layout(req: CaptureLayoutRequest) -> Dict[str, Any]:
    """Capture current window positions into a new layout."""
    wm = _wm()
    layout = wm.capture_layout(req.name, req.description)
    return layout.to_dict()


@router.delete("/layouts/{layout_id}")
async def delete_layout(layout_id: str) -> Dict[str, Any]:
    """Delete a persisted layout."""
    wm = _wm()
    ok = wm.delete_layout(layout_id)
    if not ok:
        raise HTTPException(status_code=404, detail="layout_not_found")
    return {"deleted": True, "layout_id": layout_id}


__all__ = ["router"]