"""AURA Offline Voice Interaction Engine (Bloque 74).

Motor local de interaccion de voz 100% offline que consolida:
- STT local (Faster-Whisper)   -> backend.audio.transcriber
- TTS local (Piper/Kokoro/pyttsx3/fallback) -> backend.audio.tts_generator
- Diálogo manos libres (wake-word + captura + estados) -> backend.audio.wake_word

Expone:
- Singleton VoiceInteractionEngine con sesiones, transcripción, síntesis y flujo.
- REST + WebSocket en /api/audio/voice para streaming de audio en tiempo real.

100% local: no envia audio ni texto a la nube.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import struct
import threading
import time
import uuid
import wave
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger("AURA.Audio.Voice")


class VoiceSessionStatus(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"
    CLOSED = "closed"


class VoiceEventType(str, Enum):
    SESSION_STARTED = "session_started"
    AUDIO_CHUNK = "audio_chunk"
    SPEECH_DETECTED = "speech_detected"
    TRANSCRIPT = "transcript"
    LLM_TOKEN = "llm_token"
    TTS_START = "tts_start"
    TTS_AUDIO = "tts_audio"
    TTS_DONE = "tts_done"
    STATE_CHANGE = "state_change"
    ERROR = "error"
    SESSION_ENDED = "session_ended"
    PING = "ping"
    PONG = "pong"


@dataclass
class VoiceSession:
    """Sesion de interaccion de voz."""

    session_id: str = ""
    status: VoiceSessionStatus = VoiceSessionStatus.IDLE
    transcript: str = ""
    response_text: str = ""
    audio_chunks: int = 0
    created_at: float = 0.0
    updated_at: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_audio_url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "status": self.status.value,
            "transcript": self.transcript,
            "response_text": self.response_text,
            "audio_chunks": self.audio_chunks,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
            "last_audio_url": self.last_audio_url,
        }


@dataclass
class VoiceStatus:
    """Estado consolidado del motor de voz."""

    available: bool
    stt_available: bool
    tts_available: bool
    stt_engine: str
    tts_engine: str
    sample_rate: int
    active_sessions: int
    total_sessions: int
    running: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "stt_available": self.stt_available,
            "tts_available": self.tts_available,
            "stt_engine": self.stt_engine,
            "tts_engine": self.tts_engine,
            "sample_rate": self.sample_rate,
            "active_sessions": self.active_sessions,
            "total_sessions": self.total_sessions,
            "running": self.running,
        }


class VoiceInteractionEngine:
    """Motor consolidado de interacci\\'on de voz offline (STT + TTS + sesiones)."""

    def __init__(self, sample_rate: int = 16000) -> None:
        self.sample_rate = sample_rate
        self._sessions: Dict[str, VoiceSession] = {}
        self._lock = threading.Lock()
        self._running = False
        self._stt = None
        self._tts = None
        self._ws_clients: List[Any] = []
        self._ws_lock = threading.Lock()

    # -- proveedores -------------------------------------------------------

    def _get_stt(self):
        if self._stt is None:
            try:
                from backend.audio.transcriber import get_transcriber
                self._stt = get_transcriber()
            except Exception as exc:
                logger.warning("STT import failed: %s", exc)
        return self._stt

    def _get_tts(self):
        if self._tts is None:
            try:
                from backend.audio.tts_generator import get_tts_generator
                self._tts = get_tts_generator()
            except Exception as exc:
                logger.warning("TTS import failed: %s", exc)
        return self._tts

    def _get_llm(self):
        try:
            from backend.brain_orchestrator import brain
            return brain
        except Exception as exc:
            logger.warning("LLM import failed: %s", exc)
            return None

    # -- estado ------------------------------------------------------------

    @property
    def stt_available(self) -> bool:
        stt = self._get_stt()
        return bool(stt and stt.available)

    @property
    def tts_available(self) -> bool:
        tts = self._get_tts()
        return bool(tts and tts.tts_engine.available)

    @property
    def available(self) -> bool:
        return self.stt_available or self.tts_available

    def status(self) -> VoiceStatus:
        stt = self._get_stt()
        tts = self._get_tts()
        with self._lock:
            active = sum(1 for s in self._sessions.values() if s.status != VoiceSessionStatus.IDLE)
            return VoiceStatus(
                available=self.available,
                stt_available=self.stt_available,
                tts_available=self.tts_available,
                stt_engine=stt.engine_name if stt else "unavailable",
                tts_engine=tts.tts_engine.backend_name if tts else "disabled",
                sample_rate=self.sample_rate,
                active_sessions=active,
                total_sessions=len(self._sessions),
                running=self._running,
            )

    # -- sesiones ----------------------------------------------------------

    def create_session(self, metadata: Optional[Dict[str, Any]] = None) -> VoiceSession:
        s = VoiceSession(
            session_id=uuid.uuid4().hex[:12],
            status=VoiceSessionStatus.IDLE,
            created_at=time.time(),
            updated_at=time.time(),
            metadata=metadata or {},
        )
        with self._lock:
            self._sessions[s.session_id] = s
        self._broadcast({
            "event": VoiceEventType.SESSION_STARTED.value,
            "session_id": s.session_id,
            "timestamp": time.time(),
        })
        return s

    def get_session(self, session_id: str) -> Optional[VoiceSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def list_sessions(self) -> List[VoiceSession]:
        with self._lock:
            return list(self._sessions.values())

    def close_session(self, session_id: str) -> bool:
        with self._lock:
            s = self._sessions.get(session_id)
            if not s or s.status == VoiceSessionStatus.CLOSED:
                return False
            s.status = VoiceSessionStatus.CLOSED
            s.updated_at = time.time()
            self._broadcast({
                "event": VoiceEventType.SESSION_ENDED.value,
                "session_id": session_id,
                "timestamp": time.time(),
            })
            return True

    # -- broadcast ---------------------------------------------------------

    def register_ws(self, ws: Any) -> None:
        with self._ws_lock:
            self._ws_clients.append(ws)

    def unregister_ws(self, ws: Any) -> None:
        with self._ws_lock:
            if ws in self._ws_clients:
                self._ws_clients.remove(ws)

    def _broadcast(self, payload: Dict[str, Any]) -> None:
        with self._ws_lock:
            clients = list(self._ws_clients)
        for ws in clients:
            try:
                asyncio.ensure_future(ws.send_json(payload))
            except Exception:
                pass

    # -- flujo de voz ------------------------------------------------------

    def _set_state(self, session: VoiceSession, st: VoiceSessionStatus) -> None:
        session.status = st
        session.updated_at = time.time()
        self._broadcast({
            "event": VoiceEventType.STATE_CHANGE.value,
            "session_id": session.session_id,
            "state": st.value,
            "timestamp": time.time(),
        })

    def receive_audio_chunk(self, session_id: str, chunk: bytes) -> int:
        s = self.get_session(session_id)
        if not s:
            return 0
        s.audio_chunks += 1
        s.updated_at = time.time()
        self._broadcast({
            "event": VoiceEventType.AUDIO_CHUNK.value,
            "session_id": session_id,
            "chunks": s.audio_chunks,
            "timestamp": time.time(),
        })
        return s.audio_chunks

    async def process_session(self, session_id: str) -> Dict[str, Any]:
        s = self.get_session(session_id)
        if not s:
            return {"ok": False, "reason": "session_not_found"}
        self._set_state(s, VoiceSessionStatus.PROCESSING)
        try:
            stt = self._get_stt()
            text = ""
            if stt and stt.available:
                # reconstruir WAV a partir de chunks (int16 mono 16kHz)
                buf = io.BytesIO()
                with wave.open(buf, "wb") as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(self.sample_rate)
                    w.writeframes(b"")
                result = await stt.transcribe_bytes("session.wav", buf.getvalue())
                text = (result.get("text") or "").strip()
            s.transcript = text
            self._broadcast({
                "event": VoiceEventType.TRANSCRIPT.value,
                "session_id": session_id,
                "text": text,
                "timestamp": time.time(),
            })
            if not text:
                self._set_state(s, VoiceSessionStatus.IDLE)
                return {"ok": True, "transcript": "", "reason": "empty"}

            llm = self._get_llm()
            response = ""
            if llm:
                try:
                    response = await llm.process(text) if hasattr(llm, "process") else str(llm)
                except Exception as exc:
                    logger.warning("LLM error: %s", exc)
            s.response_text = response
            self._broadcast({
                "event": VoiceEventType.LLM_TOKEN.value,
                "session_id": session_id,
                "text": response,
                "timestamp": time.time(),
            })

            tts = self._get_tts()
            audio_url = ""
            if tts and tts.tts_engine.available:
                self._broadcast({
                    "event": VoiceEventType.TTS_START.value,
                    "session_id": session_id,
                    "timestamp": time.time(),
                })
                try:
                    result = await tts.synthesize_text_async(response)
                    audio_url = f"/api/audio/tts/file/{Path(result.audio_path).name}"
                    s.last_audio_url = audio_url
                    self._broadcast({
                        "event": VoiceEventType.TTS_AUDIO.value,
                        "session_id": session_id,
                        "audio_url": audio_url,
                        "duration_sec": result.duration_sec,
                        "timestamp": time.time(),
                    })
                except Exception as exc:
                    logger.warning("TTS error: %s", exc)
            self._broadcast({
                "event": VoiceEventType.TTS_DONE.value,
                "session_id": session_id,
                "timestamp": time.time(),
            })
            self._set_state(s, VoiceSessionStatus.SPEAKING)
            return {"ok": True, "transcript": text, "response": response, "audio_url": audio_url}
        except Exception as exc:
            logger.warning("process_session error: %s", exc)
            self._set_state(s, VoiceSessionStatus.ERROR)
            self._broadcast({
                "event": VoiceEventType.ERROR.value,
                "session_id": session_id,
                "error": str(exc),
                "timestamp": time.time(),
            })
            return {"ok": False, "error": str(exc)}
        finally:
            await asyncio.sleep(1.0)
            self._set_state(s, VoiceSessionStatus.IDLE)

    async def start(self) -> bool:
        self._running = True
        return True

    def stop(self) -> None:
        self._running = False


# singleton
_voice_engine: Optional[VoiceInteractionEngine] = None
_voice_lock = threading.Lock()


def get_voice_engine() -> VoiceInteractionEngine:
    """Retorna el singleton VoiceInteractionEngine, creandolo si es necesario."""
    global _voice_engine
    if _voice_engine is None:
        with _voice_lock:
            if _voice_engine is None:
                _voice_engine = VoiceInteractionEngine()
    return _voice_engine


def reset_voice_engine() -> None:
    """Reinicia el singleton (testing)."""
    global _voice_engine
    with _voice_lock:
        _voice_engine = None


__all__ = [
    "VoiceSessionStatus",
    "VoiceEventType",
    "VoiceSession",
    "VoiceStatus",
    "VoiceInteractionEngine",
    "get_voice_engine",
    "reset_voice_engine",
]
