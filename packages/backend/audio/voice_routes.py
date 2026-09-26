"""AURA Voice Interaction Routes - REST + WebSocket (Bloque 74).

Endpoints under /api/audio/voice:
- GET  /api/audio/voice/status
- POST /api/audio/voice/sessions
- GET  /api/audio/voice/sessions
- POST /api/audio/voice/sessions/{sid}/process
- POST /api/audio/voice/sessions/{sid}/audio
- POST /api/audio/voice/sessions/{sid}/close
- WS   /api/audio/voice/stream
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Header, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from backend.audio.voice import (
    VoiceInteractionEngine,
    get_voice_engine,
    reset_voice_engine,
)

logger = logging.getLogger("AURA.Audio.Voice.Routes")

router = APIRouter(prefix="/api/audio/voice", tags=["audio-voice"])


def _check_api_key(provided: Optional[str]) -> None:
    expected = os.getenv("AURA_API_KEY", "")
    if expected and provided != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


def _wm() -> VoiceInteractionEngine:
    return get_voice_engine()


class CreateSessionRequest(BaseModel):
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AudioChunkRequest(BaseModel):
    session_id: str
    audio_b64: str = Field(..., description="Audio PCM int16 mono 16kHz en base64")


class ProcessSessionRequest(BaseModel):
    session_id: str


@router.get("/status")
async def voice_status(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    return _wm().status().to_dict()


@router.post("/sessions")
async def create_session(
    payload: CreateSessionRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    s = _wm().create_session(payload.metadata)
    return s.to_dict()


@router.get("/sessions")
async def list_sessions(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    sessions = _wm().list_sessions()
    return {
        "count": len(sessions),
        "sessions": [s.to_dict() for s in sessions],
    }


@router.post("/sessions/{session_id}/audio")
async def receive_audio(
    session_id: str,
    payload: AudioChunkRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    import base64
    try:
        chunk = base64.b64decode(payload.audio_b64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid_base64: {exc}") from exc
    n = _wm().receive_audio_chunk(session_id, chunk)
    return {"ok": True, "session_id": session_id, "chunks": n}


@router.post("/sessions/{session_id}/process")
async def process_session(
    session_id: str,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    result = await _wm().process_session(session_id)
    if not result.get("ok") and result.get("reason") == "session_not_found":
        raise HTTPException(status_code=404, detail="session_not_found")
    return result


@router.post("/sessions/{session_id}/close")
async def close_session(
    session_id: str,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    ok = _wm().close_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="session_not_found")
    return {"ok": True, "session_id": session_id}


@router.websocket("/stream")
async def voice_stream_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    engine = _wm()
    engine.register_ws(websocket)
    try:
        await websocket.send_json({
            "event": "connected",
            "status": engine.status().to_dict(),
            "timestamp": asyncio.get_event_loop().time(),
        })
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                await websocket.send_json({"event": "ping", "timestamp": asyncio.get_event_loop().time()})
                continue
            except WebSocketDisconnect:
                break
            try:
                data = json.loads(msg) if isinstance(msg, str) else msg
            except Exception:
                data = {"raw": msg}
            cmd = data.get("action") or data.get("cmd") or ""
            if cmd == "create":
                s = engine.create_session(data.get("metadata"))
                await websocket.send_json({"event": "session_created", "session": s.to_dict()})
            elif cmd == "audio":
                sid = data.get("session_id")
                if sid:
                    engine.receive_audio_chunk(sid, bytes.fromhex(data.get("audio_hex", "")))
            elif cmd == "process":
                sid = data.get("session_id")
                if sid:
                    asyncio.ensure_future(engine.process_session(sid))
            elif cmd == "close":
                sid = data.get("session_id")
                if sid:
                    engine.close_session(sid)
            elif cmd == "ping":
                await websocket.send_json({"event": "pong", "timestamp": asyncio.get_event_loop().time()})
            else:
                await websocket.send_json({"event": "ack", "received": data})
    except WebSocketDisconnect:
        pass
    finally:
        engine.unregister_ws(websocket)


__all__ = ["router"]