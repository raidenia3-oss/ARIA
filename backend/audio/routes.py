"""AURA Local Audio STT — endpoints REST (Bloque 37).

- GET  /api/audio/transcribe/status       — estado del motor local.
- POST /api/audio/transcribe              — multipart upload → texto local.
- POST /api/audio/transcribe/canon        — transcribe + pobla el canon literario
                                            (bridge de notas de voz de Discord/AME).

Autenticación: si AURA_API_KEY está definida se exige X-API-Key (local-first:
sin key configurada, el endpoint queda abierto en red local). No se exponen
tokens: la key nunca se devuelve en la respuesta.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Header

from backend.audio.transcriber import (
    UnsupportedAudioFormat,
    get_transcriber,
)

logger = logging.getLogger("AURA.Audio.Routes")

router = APIRouter(prefix="/api/audio", tags=["audio-stt"])


def _check_api_key(provided: Optional[str]) -> None:
    expected = os.getenv("AURA_API_KEY", "")
    if expected and provided != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


@router.get("/transcribe/status")
async def transcribe_status() -> Dict[str, Any]:
    """Estado del motor STT local (modelo, idioma, formatos, disponibilidad)."""
    return get_transcriber().status()


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Transcribe localmente un fichero de audio (.ogg/.wav/.mp3/...).

    La inferencia corre en un hilo (no bloquea el event loop) y el fichero
    temporal se borra tras procesarlo.
    """
    _check_api_key(x_api_key)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="audio vacío")
    transcriber = get_transcriber()
    if not transcriber.available:
        raise HTTPException(status_code=503, detail="motor STT local no disponible (falta faster-whisper)")
    try:
        result = await transcriber.transcribe_bytes(file.filename or "audio.ogg", data)
    except UnsupportedAudioFormat as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.warning("Transcripción fallida: %s", exc)
        raise HTTPException(status_code=500, detail="transcription_failed") from exc
    return {"status": "ok", "filename": file.filename, **result}


@router.post("/transcribe/canon")
async def transcribe_audio_to_canon(
    file: UploadFile = File(...),
    work_id: str = Form(...),
    source: str = Form("discord"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Bridge de notas de voz: transcribe y añade el texto como evento canónico.

    Usado por el bot de Discord (voice-to-canon) y por AME móvil. Publica
    además el evento al WebSocket Gateway para sincronizar el HUD en vivo.
    """
    _check_api_key(x_api_key)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="audio vacío")
    if not work_id.strip():
        raise HTTPException(status_code=422, detail="work_id es requerido")

    transcriber = get_transcriber()
    if not transcriber.available:
        raise HTTPException(status_code=503, detail="motor STT local no disponible (falta faster-whisper)")
    try:
        result = await transcriber.transcribe_bytes(file.filename or "voice.ogg", data)
    except UnsupportedAudioFormat as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.warning("Transcripción canon fallida: %s", exc)
        raise HTTPException(status_code=500, detail="transcription_failed") from exc

    text = (result.get("text") or "").strip()
    if not text:
        return {"status": "empty_transcript", "work_id": work_id, **result}

    # Poblar el canon literario + broadcast WS (Bloque 32/33 ya consolidados).
    event_id = ""
    try:
        from backend.story_memory.canon_tracker import CanonTracker

        ct = CanonTracker()
        added = ct.add_canon_event(work_id=work_id, description=text, source=source)
        event_id = str((added or {}).get("event_id", ""))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Canon add fallido para %s: %s", work_id, exc)

    try:
        import asyncio

        from backend.websocket_manager import ws_gateway

        asyncio.ensure_future(ws_gateway.broadcast(
            "canon_event",
            {"work_id": work_id, "description": text, "source": source, "event_id": event_id},
            work_id=work_id,
        ))
    except Exception as exc:  # noqa: BLE001
        logger.debug("WS broadcast skip: %s", exc)

    return {
        "status": "ok",
        "work_id": work_id,
        "source": source,
        "event_id": event_id,
        "canon_added": bool(event_id),
        **result,
    }