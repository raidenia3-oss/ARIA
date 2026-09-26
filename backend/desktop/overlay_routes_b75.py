"""AURA Overlay REST + WebSocket Routes (Bloque 75).

Endpoints under /api/desktop/overlay:
- GET  /status
- POST /mode
- POST /toggle
- POST /position
- POST /opacity
- POST /context
- POST /notification
- POST /clear_notifications
- POST /dnd
- POST /pin
- WS   /ws
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.desktop.overlay import (
    OverlayMode, OverlayPosition, get_overlay_bridge,
    reset_overlay_bridge,
)

logger = logging.getLogger("AURA.Overlay.Routes")

router = APIRouter(prefix="/api/desktop/overlay", tags=["desktop", "overlay"])


class ModeRequest(BaseModel):
    mode: str = "compact"


class PositionRequest(BaseModel):
    position: str = "top_right"
    x: int = 0
    y: int = 0


class OpacityRequest(BaseModel):
    opacity: float = 0.85


class ContextRequest(BaseModel):
    context: str = ""


class NotificationRequest(BaseModel):
    title: str = ""
    message: str = ""
    kind: str = "info"


def _bridge():
    return get_overlay_bridge()


@router.get("/status")
async def overlay_status() -> Dict[str, Any]:
    return _bridge().status()


@router.post("/mode")
async def set_mode(req: ModeRequest) -> Dict[str, Any]:
    try:
        mode = OverlayMode(req.mode)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"invalid mode: {req.mode}")
    state = _bridge().set_mode(mode)
    return {"status": "ok", "state": state.to_dict()}


@router.post("/toggle")
async def toggle_overlay() -> Dict[str, Any]:
    state = _bridge().toggle_visibility()
    return {"status": "ok", "state": state.to_dict()}


@router.post("/position")
async def set_position(req: PositionRequest) -> Dict[str, Any]:
    try:
        pos = OverlayPosition(req.position)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"invalid position: {req.position}")
    state = _bridge().set_position(pos, req.x, req.y)
    return {"status": "ok", "state": state.to_dict()}


@router.post("/opacity")
async def set_opacity(req: OpacityRequest) -> Dict[str, Any]:
    state = _bridge().set_opacity(req.opacity)
    return {"status": "ok", "state": state.to_dict()}


@router.post("/context")
async def set_context(req: ContextRequest) -> Dict[str, Any]:
    state = _bridge().set_context(req.context)
    return {"status": "ok", "state": state.to_dict()}


@router.post("/notification")
async def add_notification(req: NotificationRequest) -> Dict[str, Any]:
    notif = _bridge().add_notification(req.title, req.message, req.kind)
    return {"status": "ok", "notification": notif}


@router.post("/clear_notifications")
async def clear_notifications() -> Dict[str, Any]:
    count = _bridge().clear_notifications()
    return {"status": "ok", "cleared": count}


@router.post("/dnd")
async def toggle_dnd() -> Dict[str, Any]:
    state = _bridge().toggle_dnd()
    return {"status": "ok", "state": state.to_dict()}


@router.post("/pin")
async def toggle_pin() -> Dict[str, Any]:
    state = _bridge().toggle_pin()
    return {"status": "ok", "state": state.to_dict()}


@router.websocket("/ws")
async def overlay_websocket(websocket: WebSocket):
    """WebSocket for real-time overlay updates."""
    await websocket.accept()
    bridge = get_overlay_bridge()
    bridge.subscribe_websocket(websocket)
    try:
        await websocket.send_json({"type": "connected", "state": bridge.state.to_dict()})
        while True:
            msg = await websocket.receive_text()
            try:
                payload = json.loads(msg)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "invalid_json"})
                continue

            action = payload.get('action', '')
            if action == "toggle":
                bridge.toggle_visibility()
                await websocket.send_json({"type": "state", "state": bridge.state.to_dict()})
            elif action == "mode":
                try:
                    bridge.set_mode(OverlayMode(payload.get("mode", "compact")))
                    await websocket.send_json({"type": "state", "state": bridge.state.to_dict()})
                except ValueError:
                    await websocket.send_json({"type": "error", "message": "invalid_mode"})
            elif action == "dnd":
                bridge.toggle_dnd()
                await websocket.send_json({"type": "state", "state": bridge.state.to_dict()})
            elif action == "pin":
                bridge.toggle_pin()
                await websocket.send_json({"type": "state", "state": bridge.state.to_dict()})
            elif action == "status":
                await websocket.send_json({"type": "status", "status": bridge.status()})
            else:
                await websocket.send_json({"type": "error", "message": f"unknown_action: {action}"})
    except WebSocketDisconnect:
        pass
    finally:
        bridge.unsubscribe_websocket(websocket)


__all__ = ["router"]
