"""AURA Local TTS — endpoints REST (Bloque 46).

- GET  /api/audio/tts/status          — estado del motor local TTS.
- GET  /api/audio/tts/voices          — lista voces disponibles.
- POST /api/audio/tts/synthesize      — texto → audio (WAV).
- POST /api/audio/tts/synthesize/chapter — capítulo → lista de audios.
- GET  /api/audio/tts/file/{filename} — descarga archivo generado.

Autenticación: si AURA_API_KEY está definida se exige X-API-Key
(local-first: sin key configurada, el endpoint queda abierto en red local).
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Header, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.audio.tts_generator import (
    LocalTTSEngine,
    TTSGenerator,
    TTSUnavailable,
    TTSVoiceNotFound,
    VoiceProfile,
    get_tts_generator,
    reset_tts_generator,
)

logger = logging.getLogger("AURA.Audio.TTS.Routes")

router = APIRouter(prefix="/api/audio/tts", tags=["audio-tts"])


def _check_api_key(provided: Optional[str]) -> None:
    expected = os.getenv("AURA_API_KEY", "")
    if expected and provided != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=50000, description="Texto a sintetizar")
    work_id: Optional[str] = Field(None, description="ID de la obra (para mapeo de voces)")
    char_id: Optional[str] = Field(None, description="ID del personaje (para voz específica)")
    voice_id: Optional[str] = Field(None, description="Voz explícita (override)")
    speed: float = Field(1.0, ge=0.5, le=2.0, description="Velocidad de habla")


class SynthesizeChapterRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=200000, description="Texto completo del capítulo")
    work_id: str = Field(..., description="ID de la obra")
    char_id: Optional[str] = Field(None, description="Personaje narrador")
    voice_id: Optional[str] = Field(None, description="Voz explícita (override)")
    speed: float = Field(1.0, ge=0.5, le=2.0, description="Velocidad de habla")


class VoiceProfileRequest(BaseModel):
    voice_id: str = Field(..., description="ID de voz del motor (ej: es_ES)")
    name: str = Field(..., description="Nombre descriptivo")
    language: str = Field("es", description="Código de idioma")
    gender: str = Field("neutral", description="Género: male, female, neutral")
    style: str = Field("neutral", description="Estilo: neutral, dramatic, calm, etc.")
    speed: float = Field(1.0, ge=0.5, le=2.0)
    pitch: float = Field(1.0, ge=0.5, le=2.0)
    volume: float = Field(1.0, ge=0.1, le=2.0)
    engine_specific: Dict[str, Any] = Field(default_factory=dict)


@router.get("/status")
async def tts_status(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> Dict[str, Any]:
    """Estado del motor TTS local (backend, voces, disponibilidad)."""
    _check_api_key(x_api_key)
    gen = get_tts_generator()
    return gen.status()


@router.get("/voices")
async def tts_voices(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> Dict[str, Any]:
    """Lista voces disponibles según el backend activo."""
    _check_api_key(x_api_key)
    gen = get_tts_generator()
    return {"status": "ok", "backend": gen.tts_engine.backend_name, "voices": gen.tts_engine.list_voices()}


@router.post("/synthesize")
async def tts_synthesize(
    payload: SynthesizeRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Sintetiza texto a audio WAV localmente."""
    _check_api_key(x_api_key)
    gen = get_tts_generator()
    if not gen.tts_engine.available:
        raise HTTPException(status_code=503, detail="motor TTS local no disponible")
    try:
        result = await gen.synthesize_text_async(
            payload.text,
            work_id=payload.work_id,
            char_id=payload.char_id,
            voice_id=payload.voice_id,
        )
    except TTSVoiceNotFound as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TTSUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("Síntesis fallida: %s", exc)
        raise HTTPException(status_code=500, detail="synthesis_failed") from exc

    return {
        "status": "ok",
        "audio_url": f"/api/audio/tts/file/{Path(result.audio_path).name}",
        "duration_sec": result.duration_sec,
        "sample_rate": result.sample_rate,
        "channels": result.channels,
        "format": result.format,
        "engine": result.engine,
        "voice_id": result.voice_id,
        "text_chars": result.text_chars,
        "synthesis_time_ms": result.synthesis_time_ms,
    }


@router.post("/synthesize/chapter")
async def tts_synthesize_chapter(
    payload: SynthesizeChapterRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Sintetiza un capítulo completo (párrafos → múltiples audios)."""
    _check_api_key(x_api_key)
    gen = get_tts_generator()
    if not gen.tts_engine.available:
        raise HTTPException(status_code=503, detail="motor TTS local no disponible")
    try:
        results = await asyncio.to_thread(
            gen.synthesize_chapter,
            payload.work_id,
            payload.text,
            payload.char_id,
            payload.voice_id,
        )
    except TTSVoiceNotFound as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TTSUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("Síntesis de capítulo fallida: %s", exc)
        raise HTTPException(status_code=500, detail="synthesis_failed") from exc

    return {
        "status": "ok",
        "count": len(results),
        "total_duration_sec": sum(r.duration_sec for r in results),
        "engine": results[0].engine if results else "unknown",
        "segments": [
            {
                "audio_url": f"/api/audio/tts/file/{Path(r.audio_path).name}",
                "duration_sec": r.duration_sec,
                "text_chars": r.text_chars,
                "synthesis_time_ms": r.synthesis_time_ms,
            }
            for r in results
        ],
    }


@router.get("/file/{filename}")
async def tts_get_file(
    filename: str,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> FileResponse:
    """Descarga un archivo de audio WAV generado."""
    _check_api_key(x_api_key)
    gen = get_tts_generator()
    safe_name = Path(filename).name
    file_path = gen.tts_engine.tmp_dir / safe_name
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="archivo no encontrado")
    return FileResponse(
        path=file_path,
        media_type="audio/wav",
        filename=safe_name,
    )


@router.post("/voice-map")
async def tts_set_voice_map(
    work_id: str,
    char_id: str,
    profile: VoiceProfileRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Define/actualiza perfil de voz para un personaje."""
    _check_api_key(x_api_key)
    gen = get_tts_generator()
    vp = VoiceProfile(
        voice_id=profile.voice_id,
        name=profile.name,
        language=profile.language,
        gender=profile.gender,
        style=profile.style,
        speed=profile.speed,
        pitch=profile.pitch,
        volume=profile.volume,
        engine_specific=profile.engine_specific,
    )
    gen.set_voice_profile(work_id, char_id, vp)
    return {"status": "ok", "work_id": work_id, "char_id": char_id, "voice_id": vp.voice_id}


@router.get("/voice-map/{work_id}/{char_id}")
async def tts_get_voice_map(
    work_id: str,
    char_id: str,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Obtiene perfil de voz de un personaje."""
    _check_api_key(x_api_key)
    gen = get_tts_generator()
    vp = gen.get_voice_profile(work_id, char_id)
    if not vp:
        raise HTTPException(status_code=404, detail="perfil de voz no encontrado")
    return {
        "status": "ok",
        "work_id": work_id,
        "char_id": char_id,
        "voice_id": vp.voice_id,
        "name": vp.name,
        "language": vp.language,
        "gender": vp.gender,
        "style": vp.style,
        "speed": vp.speed,
        "pitch": vp.pitch,
        "volume": vp.volume,
        "engine_specific": vp.engine_specific,
    }