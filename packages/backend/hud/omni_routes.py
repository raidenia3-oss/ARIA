"""BLOQUE 97 - REST + WebSocket handlers for /api/hud/omni. 100% offline."""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.hud.omni_interaction import (
    OmniChannel,
    HUDMode,
    HUDPosition,
    OmniIntent,
    get_omni_engine,
    reset_omni_engine,
)

router = APIRouter(prefix="/api/hud/omni", tags=["hud", "omni"])


class IngestRequest(BaseModel):
    channel: str = "text"
    text: str = ""
    confidence: float = 0.0
    context: Optional[Dict[str, Any]] = None


class CommandRequest(BaseModel):
    channel: str = "text"
    text: str = ""
    command: str = ""
    confidence: float = 0.0
    context: Optional[Dict[str, Any]] = None


class HUDActionRequest(BaseModel):
    action: str
    params: Optional[Dict[str, Any]] = None


class AlertRequest(BaseModel):
    title: str
    message: str = ""
    severity: str = "info"


def _engine():
    return get_omni_engine()


@router.get("/status", tags=["hud-omni"])
async def omni_status() -> Dict[str, Any]:
    return _engine().status()


@router.get("/snapshot", tags=["hud-omni"])
async def omni_snapshot() -> Dict[str, Any]:
    return _engine().snapshot()


@router.post("/ingest", tags=["hud-omni"])
async def omni_ingest(req: IngestRequest) -> Dict[str, Any]:
    try:
        inp = _engine().ingest(req.channel, req.text, req.confidence, req.context)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"status": "ok", "input": inp.to_dict()}


@router.post("/command", tags=["hud-omni"])
async def omni_command(req: CommandRequest) -> Dict[str, Any]:
    text = req.text or req.command or ""
    try:
        inp = _engine().ingest(req.channel, text, req.confidence, req.context)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"status": "ok", "input": inp.to_dict()}


@router.post("/hud/action", tags=["hud-omni"])
async def omni_hud_action(req: HUDActionRequest) -> Dict[str, Any]:
    return _engine().hud_action(req.action, req.params)


@router.post("/hud/alert", tags=["hud-omni"])
async def omni_hud_alert(req: AlertRequest) -> Dict[str, Any]:
    alert = _engine().hud.push_alert(req.title, req.message, req.severity)
    return {"status": "ok", "alert": alert}


@router.post("/hud/clear_alerts", tags=["hud-omni"])
async def omni_hud_clear_alerts() -> Dict[str, Any]:
    n = _engine().hud.clear_alerts()
    return {"status": "ok", "cleared": n}


@router.get("/hud/quick_actions", tags=["hud-omni"])
async def omni_hud_quick_actions() -> Dict[str, Any]:
    hud = _engine().hud
    with hud._lock:
        actions = list(hud._quick_actions)
    return {"status": "ok", "actions": actions, "offline_only": True}


class QuickActionsRequest(BaseModel):
    actions: List[Dict[str, Any]] = []


@router.post("/hud/quick_actions", tags=["hud-omni"])
async def omni_hud_set_quick_actions(req: QuickActionsRequest) -> Dict[str, Any]:
    n = _engine().hud.set_quick_actions(req.actions)
    return {"status": "ok", "count": n}


@router.get("/commands", tags=["hud-omni"])
async def omni_commands(limit: int = 50) -> Dict[str, Any]:
    cmds = _engine().synthesizer.recent_commands(limit=min(200, max(1, limit)))
    return {"count": len(cmds), "commands": [c.to_dict() for c in cmds]}


@router.get("/inputs", tags=["hud-omni"])
async def omni_inputs(limit: int = 50) -> Dict[str, Any]:
    inputs = _engine().synthesizer.recent_inputs(limit=min(500, max(1, limit)))
    return {"count": len(inputs), "inputs": [i.to_dict() for i in inputs]}


@router.post("/reset", tags=["hud-omni"])
async def omni_reset() -> Dict[str, Any]:
    cleared = _engine().reset()
    return {"status": "ok", **cleared}


@router.get("/channels", tags=["hud-omni"])
async def omni_channels() -> Dict[str, Any]:
    return {
        "channels": [c.value for c in OmniChannel],
        "intents": [i.value for i in OmniIntent],
        "hud_modes": [m.value for m in HUDMode],
        "hud_positions": [p.value for p in HUDPosition],
        "offline_only": True,
    }


class _WSConn:
    def __init__(self) -> None:
        self.active: set = set()
        self._loop = None

    def set_loop(self, loop) -> None:
        self._loop = loop

    def broadcast(self, payload: Dict[str, Any]) -> None:
        if not self.active:
            return
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        for ws in list(self.active):
            try:
                coro = ws.send_json(payload)
                if asyncio.iscoroutine(coro):
                    loop.call_soon_threadsafe(asyncio.ensure_future, coro)
            except Exception:
                self.active.discard(ws)


_ws = _WSConn()


@router.websocket("/ws")
async def omni_ws(websocket: WebSocket) -> None:
    """Real-time omni-interaction channel.

    Pushes HUD state changes, synthesized commands, cognitive-state updates
    and alerts. Accepts JSON actions: { "action": "...", "params": {...} }.
    """
    await websocket.accept()
    eng = _engine()
    eng.register_websocket(websocket)
    _ws.active.add(websocket)
    try:
        _ws.set_loop(asyncio.get_running_loop())
    except Exception:
        pass
    eng.on_event(_ws.broadcast)
    try:
        await websocket.send_json({"type": "connected", "status": eng.status()})
        while True:
            msg = await websocket.receive_text()
            try:
                payload = json.loads(msg)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "invalid_json"})
                continue
            action = payload.get("action", "")
            params = payload.get("params") or {}
            if action == "status":
                await websocket.send_json({"type": "status", "status": eng.status()})
            elif action == "snapshot":
                await websocket.send_json({"type": "snapshot", **eng.snapshot()})
            elif action == "ingest":
                try:
                    inp = eng.ingest(params.get("channel", "text"),
                                     params.get("text", ""), float(params.get("confidence", 0.0)),
                                     params.get("context"))
                    await websocket.send_json({"type": "input", **inp.to_dict()})
                except ValueError as exc:
                    await websocket.send_json({"type": "error", "message": str(exc)})
            elif action == "hud_action":
                res = eng.hud_action(action=params.get("hud_action") or params.get("action", "toggle"),
                                     params=params.get("params"))
                await websocket.send_json({"type": "hud_result", **res})
            elif action == "alert":
                eng.hud.push_alert(params.get("title", ""), params.get("message", ""),
                                   params.get("severity", "info"))
                await websocket.send_json({"type": "ack", "action": "alert"})
            else:
                await websocket.send_json({"type": "error",
                                           "message": f"unknown_action: {action}"})
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        eng.unregister_websocket(websocket)
        _ws.active.discard(websocket)


__all__ = ["router"]