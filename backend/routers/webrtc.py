"""WebRTC router for AURA - Audio pipeline and TTS integration.

Bridges incoming/outgoing audio tracks with:
- audio_pipeline.py (VAD + Faster-Whisper STT)
- tts_engine.py (Piper/Kokoro/pyttsx3 TTS)

Exposes:
- POST /api/webrtc/audio/process - process incoming audio chunk
- POST /api/webrtc/tts/speak - enqueue TTS and return WAV/PCM
- WS  /ws/webrtc/audio/{session_id} - optional streaming channel
"""

from __future__ import annotations

import io
import json
import logging
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from backend.services.audio_pipeline import AudioPipeline, AUDIO_SAMPLE_RATE
from backend.services.tts_engine import TTSEngine, TTS_SAMPLE_RATE

router = APIRouter()
logger = logging.getLogger("AURAWebRTCAudio")

audio_pipeline = AudioPipeline()
tts_engine = TTSEngine()

_audio_sessions: Dict[str, Dict[str, Any]] = {}


@router.on_event("startup")
async def _on_startup() -> None:
    logger.info("WebRTC audio pipeline ready")


@router.post("/webrtc/audio/process")
async def process_audio(payload: Dict[str, Any]) -> Dict[str, Any]:
    session_id = str(payload.get("session_id", ""))
    if not session_id:
        return JSONResponse(status_code=400, content={"error": "session_id is required"})

    audio_b64 = payload.get("audio")
    if not audio_b64:
        return JSONResponse(status_code=400, content={"error": "audio is required"})

    try:
        audio_bytes = io.BytesIO(audio_b64).read() if isinstance(audio_b64, (bytes, bytearray)) else io.BytesIO(str(audio_b64).encode()).read()
    except Exception:
        audio_bytes = b""

    ts = int(time.time() * 1000)
    audio_pipeline.push_audio(audio_bytes, timestamp_ms=ts)

    return {
        "session_id": session_id,
        "status": "queued",
        "pipeline": audio_pipeline.get_status(),
    }


@router.post("/webrtc/tts/speak")
async def tts_speak(payload: Dict[str, Any]) -> Dict[str, Any]:
    text = str(payload.get("text", "")).strip()
    if not text:
        return JSONResponse(status_code=400, content={"error": "text is required"})

    session_id = str(payload.get("session_id", ""))
    voice = str(payload.get("voice", "es_ES"))

    tts_engine.voice = voice
    tts_engine.speak(text)

    return {
        "session_id": session_id,
        "status": "synthesizing",
        "backend": tts_engine.get_status()["backend"],
        "sample_rate": TTS_SAMPLE_RATE,
    }


@router.get("/webrtc/tts/status")
async def tts_status() -> Dict[str, Any]:
    return tts_engine.get_status()


@router.get("/webrtc/audio/status")
async def audio_status() -> Dict[str, Any]:
    return audio_pipeline.get_status()


@router.websocket("/ws/webrtc/audio/{session_id}")
async def webrtc_audio_ws(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    _audio_sessions.setdefault(session_id, {"ws": websocket, "tts_chunks": 0, "last_activity": time.time()})
    logger.info("WebRTC audio WS connected: %s", session_id)
    try:
        while True:
            msg = await websocket.receive_text()
            try:
                payload = json.loads(msg)
                if payload.get("type") == "audio":
                    audio_b64 = payload.get("data")
                    if audio_b64:
                        audio_bytes = io.BytesIO(audio_b64).read() if isinstance(audio_b64, (bytes, bytearray)) else io.BytesIO(str(audio_b64).encode()).read()
                        audio_pipeline.push_audio(audio_bytes, timestamp_ms=int(time.time() * 1000))
                elif payload.get("type") == "tts":
                    text = str(payload.get("text", "")).strip()
                    if text:
                        tts_engine.voice = str(payload.get("voice", "es_ES"))
                        tts_engine.speak(text)
            except Exception:
                pass
    except WebSocketDisconnect:
        logger.info("WebRTC audio WS disconnected: %s", session_id)
    finally:
        _audio_sessions.pop(session_id, None)
        try:
            await websocket.close()
        except Exception:
            pass
