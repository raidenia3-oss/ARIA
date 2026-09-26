"""Spatial & JARVIS routes for AURA - Module 24.

Eventos REST y WebSocket para la interfaz espacial multimodal y el núcleo JARVIS.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Query, WebSocket
from fastapi.responses import JSONResponse

from backend.jarvis_interface import JarvisCore
from backend.spatial_gesture_engine import (
    GestureFrame,
    HandTrackingEngine,
    SpatialCanvas,
    SpatialCoordinate,
)

router = APIRouter(prefix="/api", tags=["spatial", "jarvis"])

gesture_engine = HandTrackingEngine()
spatial_canvas = SpatialCanvas()
jarvis = JarvisCore()
jarvis.initialize()


# --------------------------------------------------------------------------- #
#  Spatial Gestures (REST)                                                     #
# --------------------------------------------------------------------------- #
@router.post("/spatial/gestures")
async def process_gesture(
    payload: Dict[str, Any] = Body(
        ...,
        json_schema_extra={
            "example": {
                "gesture_type": "pinch",
                "hand": "right",
                "coordinates": [{"x": 0.5, "y": 0.3, "z": 0.1}],
                "confidence": 0.95,
                "duration_ms": 120,
            }
        },
    ),
) -> Dict[str, Any]:
    frame = GestureFrame(
        frame_id=payload.get("frame_id", f"gest-{int(time.time() * 1000000)}"),
        gesture_type=payload.get("gesture_type", "pinch"),
        hand=payload.get("hand", "right"),
        coordinates=[
            SpatialCoordinate(**c) for c in payload.get("coordinates", [{"x": 0.0, "y": 0.0, "z": 0.0}])
        ],
        confidence=float(payload.get("confidence", 1.0)),
        duration_ms=float(payload.get("duration_ms", 0.0)),
    )
    gesture_result = gesture_engine.process_frame(frame)
    canvas_result = spatial_canvas.process_gesture(frame)
    return {"gesture": gesture_result, "canvas": canvas_result}


@router.get("/spatial/gestures/history")
async def gesture_history(limit: int = Query(50, ge=1, le=500)) -> Dict[str, Any]:
    history = gesture_engine.history(limit=limit)
    return {"count": len(history), "gestures": history}


# --------------------------------------------------------------------------- #
#  Spatial Canvas (REST)                                                       #
# --------------------------------------------------------------------------- #
@router.get("/spatial/canvas")
async def get_canvas() -> Dict[str, Any]:
    return spatial_canvas.get_state()


@router.post("/spatial/canvas")
async def update_canvas(
    payload: Dict[str, Any] = Body(
        ...,
        json_schema_extra={
            "example": {"action": "add_widget", "widget_type": "hud", "position": {"x": 1, "y": 2, "z": 0}}
        },
    ),
) -> Dict[str, Any]:
    action = payload.get("action", "add_widget")

    if action == "add_widget":
        return spatial_canvas.add_widget(
            widget_type=payload.get("widget_type", "generic"),
            position=payload.get("position"),
        )

    if action == "remove_widget":
        return spatial_canvas.remove_widget(payload.get("widget_id", ""))

    if action == "move_widget":
        coord_data = payload.get("coordinate", {"x": 0.0, "y": 0.0, "z": 0.0})
        return spatial_canvas.move_widget(
            payload.get("widget_id", ""),
            SpatialCoordinate(**coord_data),
        )

    if action == "transform_model":
        return spatial_canvas.transform_model(
            payload.get("model_id", ""),
            payload.get("transform", {}),
        )

    return JSONResponse(status_code=400, content={"error": f"unknown_canvas_action: {action}"})


# --------------------------------------------------------------------------- #
#  JARVIS State (REST)                                                         #
# --------------------------------------------------------------------------- #
@router.get("/jarvis/state")
async def get_jarvis_state() -> Dict[str, Any]:
    return jarvis.get_state()


@router.post("/jarvis/state")
async def update_jarvis_state(
    payload: Dict[str, Any] = Body(
        ...,
        json_schema_extra={
            "example": {
                "mode": "listening",
                "position": {"x": 0, "y": 1, "z": -2},
                "voice_session": {"action": "create"},
                "memory": {"action": "store", "key": "user_pref", "value": "dark"},
            }
        },
    ),
) -> Dict[str, Any]:
    return jarvis.update_state(payload)


# --------------------------------------------------------------------------- #
#  JARVIS Voice Session (REST)                                                 #
# --------------------------------------------------------------------------- #
@router.post("/jarvis/voice-session")
async def manage_voice_session(
    payload: Dict[str, Any] = Body(
        ...,
        json_schema_extra={"example": {"action": "create"}},
    ),
) -> Dict[str, Any]:
    action = payload.get("action", "create")

    if action == "create":
        return jarvis.voice_manager.create_session()

    if action == "end":
        session_id = payload.get("session_id", "")
        result = jarvis.voice_manager.end_session(session_id)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result

    if action == "transcript":
        session_id = payload.get("session_id", "")
        result = jarvis.voice_manager.add_transcript(
            session_id,
            payload.get("text", ""),
            payload.get("direction", "user"),
        )
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result

    if action == "process":
        return jarvis.process_voice(payload.get("session_id", ""), payload.get("text", ""))

    return JSONResponse(status_code=400, content={"error": f"unknown_voice_action: {action}"})


@router.get("/jarvis/voice-session/{session_id}")
async def get_voice_session(session_id: str) -> Dict[str, Any]:
    session = jarvis.voice_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session_not_found")
    return session


# --------------------------------------------------------------------------- #
#  Spatial WebSocket (real-time gesture streaming)                             #
# --------------------------------------------------------------------------- #
@router.websocket("/spatial/ws")
async def spatial_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json({"type": "connected", "message": "AURA spatial WebSocket ready"})
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "error": "invalid_json"})
                continue

            msg_type = msg.get("type", "gesture")

            if msg_type == "gesture":
                frame = GestureFrame(
                    frame_id=msg.get("frame_id", f"gest-{int(time.time() * 1000000)}"),
                    gesture_type=msg.get("gesture_type", "pinch"),
                    hand=msg.get("hand", "right"),
                    coordinates=[
                        SpatialCoordinate(**c)
                        for c in msg.get("coordinates", [{"x": 0.0, "y": 0.0, "z": 0.0}])
                    ],
                    confidence=float(msg.get("confidence", 1.0)),
                    duration_ms=float(msg.get("duration_ms", 0.0)),
                )
                gesture_result = gesture_engine.process_frame(frame)
                canvas_result = spatial_canvas.process_gesture(frame)
                await websocket.send_json({
                    "type": "gesture_result",
                    "gesture": gesture_result,
                    "canvas": canvas_result,
                })

            elif msg_type == "jarvis_state":
                await websocket.send_json({"type": "jarvis_state", "state": jarvis.get_state()})

            elif msg_type == "canvas_state":
                await websocket.send_json({"type": "canvas_state", "state": spatial_canvas.get_state()})

            else:
                await websocket.send_json({"type": "error", "error": f"unknown_message_type: {msg_type}"})

    except Exception as exc:
        await websocket.send_json({"type": "disconnected", "error": str(exc)})
    finally:
        await websocket.close()
