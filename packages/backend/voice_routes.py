"""Voice routes for AURA speech-to-text, text-to-speech and voice commands."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.voice_manager import VoiceManager, VoiceRequest, VoiceProvider

router = APIRouter(prefix="/api/voice", tags=["voice"])
voice_manager = VoiceManager()


@router.post("/stt")
async def voice_stt(payload: Dict[str, Any]) -> Dict[str, Any]:
    request = VoiceRequest(
        provider=VoiceProvider.STT,
        text=payload.get("text"),
        audio_format=payload.get("audio_format"),
        language=payload.get("language", "es"),
        metadata=payload.get("metadata"),
    )
    return voice_manager.transcribe(request)


@router.post("/tts")
async def voice_tts(payload: Dict[str, Any]) -> Dict[str, Any]:
    request = VoiceRequest(
        provider=VoiceProvider.TTS,
        text=payload.get("text"),
        audio_format=payload.get("audio_format"),
        language=payload.get("language", "es"),
        voice=payload.get("voice"),
        metadata=payload.get("metadata"),
    )
    return voice_manager.synthesize(request)


@router.post("/command")
async def voice_command(payload: Dict[str, Any]) -> Dict[str, Any]:
    request = VoiceRequest(
        provider=VoiceProvider.COMMAND,
        text=payload.get("text"),
        language=payload.get("language", "es"),
        metadata=payload.get("metadata"),
    )
    return voice_manager.execute_command(request)


@router.get("/history")
async def voice_history(limit: int = 50) -> Dict[str, Any]:
    sessions = voice_manager.history_sessions(limit=limit)
    return {"count": len(sessions), "sessions": sessions}
