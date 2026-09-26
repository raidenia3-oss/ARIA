"""AURA Voice Interaction Engine (Bloque 74).

Unified offline voice interaction pipeline:
    microphone -> STT -> command processing -> TTS -> speaker

100% local: no cloud speech APIs.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger("AURA.VoiceInteraction")

_SAMPLE_RATE = int(os.getenv("AURA_VOICE_SAMPLE_RATE", "16000"))
_CHANNELS = int(os.getenv("AURA_VOICE_CHANNELS", "1"))
_CHUNK_DURATION_S = float(os.getenv("AURA_VOICE_CHUNK_S", "0.5"))
_SILENCE_THRESHOLD = float(os.getenv("AURA_VOICE_SILENCE_THRESHOLD", "0.01"))
_SILENCE_DURATION_S = float(os.getenv("AURA_VOICE_SILENCE_DURATION_S", "1.5"))
_MAX_RECORD_S = float(os.getenv("AURA_VOICE_MAX_RECORD_S", "30.0"))


class VoiceState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"


@dataclass
class VoiceCommand:
    """A transcribed voice command."""
    text: str
    confidence: float = 0.0
    language: str = "es"
    duration_sec: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "confidence": self.confidence,
            "language": self.language,
            "duration_sec": self.duration_sec,
            "timestamp": self.timestamp,
        }


@dataclass
class VoiceResponse:
    """A synthetic voice response."""
    text: str
    audio_path: Optional[str] = None
    duration_sec: float = 0.0
    engine: str = "none"
    voice_id: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "audio_url": f"/api/audio/voice/file/{Path(self.audio_path).name}" if self.audio_path else None,
            "duration_sec": self.duration_sec,
            "engine": self.engine,
            "voice_id": self.voice_id,
        }


class AudioRingBuffer:
    """Thread-safe ring buffer for audio streaming."""

    def __init__(self, capacity: int = 65536) -> None:
        self._buffer = bytearray()
        self._capacity = capacity
        self._lock = threading.Lock()

    def write(self, data: bytes) -> None:
        with self._lock:
            self._buffer.extend(data)
            if len(self._buffer) > self._capacity:
                self._buffer = self._buffer[-self._capacity:]

    def read_all(self) -> bytes:
        with self._lock:
            data = bytes(self._buffer)
            self._buffer.clear()
            return data

    def read_chunk(self, size: int) -> bytes:
        with self._lock:
            data = bytes(self._buffer[:size])
            self._buffer = self._buffer[size:]
            return data

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._buffer)

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()


class LocalVoiceEngine:
    """Offline voice interaction engine combining STT + TTS."""

    def __init__(self, sample_rate: int = _SAMPLE_RATE, channels: int = _CHANNELS, engine: str = "auto") -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self._engine_mode = engine
        self._state = VoiceState.IDLE
        self._state_lock = threading.Lock()
        self._transcriber: Optional[Any] = None
        self._tts: Optional[Any] = None

    @property
    def state(self) -> VoiceState:
        with self._state_lock:
            return self._state

    def _set_state(self, s: VoiceState) -> None:
        with self._state_lock:
            self._state = s

    @property
    def available(self) -> bool:
        return self.stt_available or self.tts_available

    @property
    def stt_available(self) -> bool:
        try:
            from backend.audio.transcriber import get_transcriber
            return get_transcriber().available
        except Exception:
            return False

    @property
    def tts_available(self) -> bool:
        try:
            from backend.audio.tts_generator import get_tts_generator
            return get_tts_generator().tts_engine.available
        except Exception:
            return False

    def _get_transcriber(self):
        if self._transcriber is None:
            from backend.audio.transcriber import get_transcriber
            self._transcriber = get_transcriber()
        return self._transcriber

    def _get_tts(self):
        if self._tts is None:
            from backend.audio.tts_generator import get_tts_generator
            self._tts = get_tts_generator()
        return self._tts

    def transcribe_audio_data(self, audio_bytes: bytes, filename: str = "voice.wav") -> VoiceCommand:
        self._set_state(VoiceState.PROCESSING)
        try:
            t = self._get_transcriber()
            if not t.available:
                return VoiceCommand(text="", confidence=0.0, language="unknown")
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(t.transcribe_bytes(filename, audio_bytes))
            finally:
                loop.close()
            return VoiceCommand(
                text=result.get("text", ""),
                confidence=0.9 if result.get("engine") == "stub" else 0.0,
                language=result.get("language", "es"),
                duration_sec=result.get("duration", 0.0),
            )
        except Exception as e:
            logger.error("Transcription error: %s", e)
            return VoiceCommand(text="", confidence=0.0, language="error")
        finally:
            self._set_state(VoiceState.IDLE)

    async def transcribe_audio_data_async(self, audio_bytes: bytes, filename: str = "voice.wav") -> VoiceCommand:
        self._set_state(VoiceState.PROCESSING)
        try:
            t = self._get_transcriber()
            if not t.available:
                return VoiceCommand(text="", confidence=0.0, language="unknown")
            result = await t.transcribe_bytes(filename, audio_bytes)
            return VoiceCommand(
                text=result.get("text", ""),
                confidence=0.9 if result.get("engine") == "stub" else 0.0,
                language=result.get("language", "es"),
                duration_sec=result.get("duration", 0.0),
            )
        except Exception as e:
            logger.error("Async transcription error: %s", e)
            return VoiceCommand(text="", confidence=0.0, language="error")
        finally:
            self._set_state(VoiceState.IDLE)

    def speak_text(self, text: str, voice_id: Optional[str] = None) -> VoiceResponse:
        self._set_state(VoiceState.SPEAKING)
        try:
            tts = self._get_tts()
            if not tts.tts_engine.available:
                return VoiceResponse(text=text, engine="none")
            r = tts.tts_engine.synthesize(text, voice_id=voice_id)
            return VoiceResponse(
                text=text, audio_path=r.audio_path,
                duration_sec=r.duration_sec, engine=r.engine, voice_id=r.voice_id,
            )
        except Exception as e:
            logger.error("TTS error: %s", e)
            return VoiceResponse(text=text, engine="error")
        finally:
            self._set_state(VoiceState.IDLE)

    async def speak_text_async(self, text: str, voice_id: Optional[str] = None) -> VoiceResponse:
        self._set_state(VoiceState.SPEAKING)
        try:
            tts = self._get_tts()
            if not tts.tts_engine.available:
                return VoiceResponse(text=text, engine="none")
            r = await tts.tts_engine.synthesize_async(text, voice_id=voice_id)
            return VoiceResponse(
                text=text, audio_path=r.audio_path,
                duration_sec=r.duration_sec, engine=r.engine, voice_id=r.voice_id,
            )
        except Exception as e:
            logger.error("Async TTS error: %s", e)
            return VoiceResponse(text=text, engine="error")
        finally:
            self._set_state(VoiceState.IDLE)

    async def voice_roundtrip(
        self, audio_bytes: bytes, filename: str = "voice.wav",
        response_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        cmd = await self.transcribe_audio_data_async(audio_bytes, filename)
        result = {"command": cmd.to_dict()}
        if response_text or cmd.text:
            resp = await self.speak_text_async(response_text or f"Entendido: {cmd.text}")
            result["response"] = resp.to_dict()
        return result

    def record_microphone(self, duration_s: float = 5.0) -> Optional[bytes]:
        try:
            import sounddevice as sd
            self._set_state(VoiceState.LISTENING)
            samples = int(duration_s * self.sample_rate)
            audio = sd.rec(samples, samplerate=self.sample_rate, channels=self.channels, dtype="int16")
            sd.wait()
            return audio.tobytes()
        except Exception as e:
            logger.error("Mic recording failed: %s", e)
            return None
        finally:
            self._set_state(VoiceState.IDLE)

    def record_microphone_until_silence(self, max_duration_s: float = _MAX_RECORD_S) -> Optional[bytes]:
        try:
            import sounddevice as sd
            self._set_state(VoiceState.LISTENING)
            chunk_samples = int(_CHUNK_DURATION_S * self.sample_rate)
            all_chunks: list = []
            silence_chunks = 0
            max_silence = int(_SILENCE_DURATION_S / _CHUNK_DURATION_S)
            max_chunks = int(max_duration_s / _CHUNK_DURATION_S)
            stream = sd.InputStream(
                samplerate=self.sample_rate, channels=self.channels,
                dtype="int16", blocksize=chunk_samples,
            )
            with stream:
                for _ in range(max_chunks):
                    chunk, _ = stream.read(chunk_samples)
                    all_chunks.append(chunk)
                    rms = float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2))) / 32768.0
                    if rms < _SILENCE_THRESHOLD:
                        silence_chunks += 1
                        if silence_chunks >= max_silence and len(all_chunks) > 2:
                            break
                    else:
                        silence_chunks = 0
            return np.concatenate(all_chunks, axis=0).tobytes() if all_chunks else None
        except Exception as e:
            logger.error("Mic silence-detect recording failed: %s", e)
            return None
        finally:
            self._set_state(VoiceState.IDLE)

    def status(self) -> Dict[str, Any]:
        return {
            "status": "ok",
            "state": self.state.value,
            "available": self.available,
            "stt_available": self.stt_available,
            "tts_available": self.tts_available,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "mode": self._engine_mode,
        }


_voice_engine = None
_voice_lock = threading.Lock()


def get_voice_engine(engine: str = "auto"):
    global _voice_engine
    if _voice_engine is None:
        with _voice_lock:
            if _voice_engine is None:
                _voice_engine = LocalVoiceEngine(engine=engine)
    return _voice_engine


def reset_voice_engine():
    global _voice_engine
    with _voice_lock:
        _voice_engine = None


__all__ = [
    "VoiceState", "VoiceCommand", "VoiceResponse", "AudioRingBuffer",
    "LocalVoiceEngine", "get_voice_engine", "reset_voice_engine",
]