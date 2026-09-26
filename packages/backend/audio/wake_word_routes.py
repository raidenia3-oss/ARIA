"""AURA Local Wake-Word & Voice Dialogue — endpoints REST + WebSocket (Bloque 54).

- GET  /api/audio/wake-word/status     — estado del motor de wake-word.
- POST /api/audio/wake-word/start      — inicia captura continua.
- POST /api/audio/wake-word/stop       — detiene captura continua.
- GET  /api/audio/wake-word/sessions   — lista sesiones de dialogo.
- WS   /api/audio/voice/stream         — stream de eventos de voz en tiempo real.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Header, WebSocket, WebSocketDisconnect

from backend.audio.wake_word import DialogueEngine, wake_word_engine

logger = logging.getLogger("AURA.Audio.WakeWord.Routes")

router = APIRouter(prefix="/api/audio/wake-word", tags=["audio-wake-word"])


def _check_api_key(provided: Optional[str]) -> None:
    expected = os.getenv("AURA_API_KEY", "")
    if expected and provided != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


@router.get("/status")
async def wake_word_status(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    return wake_word_engine.status()


@router.post("/start")
async def wake_word_start(
    device: Optional[int] = None,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    ok = await wake_word_engine.start_continuous(device=device)
    return {"status": "ok" if ok else "error", "running": wake_word_engine._running}


@router.post("/stop")
async def wake_word_stop(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    wake_word_engine.stop_continuous()
    return {"status": "ok", "running": False}


@router.get("/sessions")
async def wake_word_sessions(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    return {
        "status": "ok",
        "sessions": [
            {
                "session_id": s.session_id,
                "state": s.state.value,
                "transcript": s.transcript,
                "response_text": s.response_text,
                "created_at": s.created_at,
                "updated_at": s.updated_at,
            }
            for s in wake_word_engine.sessions.values()
        ],
    }


@router.websocket("/voice/stream")
async def voice_stream_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    wake_word_engine.register_ws(websocket)
    try:
        await websocket.send_json({
            "event": "connected",
            "engine": wake_word_engine.status(),
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
            if cmd == "start":
                await wake_word_engine.start_continuous(device=data.get("device"))
            elif cmd == "stop":
                wake_word_engine.stop_continuous()
            elif cmd == "process":
                sid = data.get("session_id")
                if sid:
                    asyncio.ensure_future(wake_word_engine.process_session(sid))
            else:
                await websocket.send_json({"event": "ack", "received": data})
    except WebSocketDisconnect:
        pass
    finally:
        wake_word_engine.unregister_ws(websocket)