"""AURA Local Wake-Word & Hands-Free Voice Dialogue Engine (Bloque 54)."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import queue
import struct
import threading
import time
import wave
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Awaitable

logger = logging.getLogger("AURA.Audio.WakeWord")


class DialogueState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"


class WakeWordEvent(str, Enum):
    WAKE_DETECTED = "wake_detected"
    SPEECH_START = "speech_start"
    SPEECH_END = "speech_end"
    TRANSCRIPT_READY = "transcript_ready"
    LLM_CHUNK = "llm_chunk"
    TTS_START = "tts_start"
    TTS_AUDIO = "tts_audio"
    TTS_DONE = "tts_done"
    STATE_CHANGE = "state_change"
    ERROR = "error"


@dataclass
class WakeWordConfig:
    wake_words: List[str] = field(default_factory=lambda: ["hey aura", "hola aura", "aura"])
    sample_rate: int = 16000
    chunk_ms: int = 30
    silence_timeout_ms: int = 1500
    max_speech_sec: float = 15.0
    confirmation_timeout_ms: int = 3000
    vosk_model_path: Optional[str] = None
    enable_whisper_fallback: bool = True
    sensitivity: float = 0.5


@dataclass
class DialogueSession:
    session_id: str = ""
    state: DialogueState = DialogueState.IDLE
    transcript: str = ""
    response_text: str = ""
    audio_chunks: List[bytes] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class RingBuffer:
    """Buffer circular de audio para deteccion continua de wake-word."""

    def __init__(self, max_seconds: float = 5.0, sample_rate: int = 16000) -> None:
        self.max_samples = int(max_seconds * sample_rate)
        self.sample_rate = sample_rate
        self._buffer: List[bytes] = []
        self._total_samples = 0
        self._lock = threading.Lock()

    def add(self, data: bytes) -> None:
        with self._lock:
            self._buffer.append(data)
            self._total_samples += len(data) // 2
            while self._total_samples > self.max_samples and self._buffer:
                removed = self._buffer.pop(0)
                self._total_samples -= len(removed) // 2

    def get_wav(self) -> bytes:
        with self._lock:
            raw = b"".join(self._buffer)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.sample_rate)
            w.writeframes(raw)
        return buf.getvalue()

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()
            self._total_samples = 0


class VoskWakeDetector:
    """Detector de wake-word usando Vosk (STT ligero, sin nube)."""

    def __init__(self, config: WakeWordConfig) -> None:
        self.config = config
        self._model = None
        self._rec = None
        self._available = False
        try:
            import vosk
            model_path = config.vosk_model_path or os.getenv("AURA_VOSK_MODEL", "")
            if model_path and os.path.isdir(model_path):
                self._model = vosk.Model(model_path)
                self._available = True
                logger.info("Vosk model loaded from %s", model_path)
            else:
                logger.warning("Vosk model path not set; wake-word detection disabled")
        except Exception as exc:
            logger.warning("Vosk unavailable: %s", exc)

    @property
    def available(self) -> bool:
        return self._available

    def detect(self, wav_bytes: bytes) -> Optional[str]:
        if not self._available or self._model is None:
            return None
        try:
            import vosk
            rec = vosk.KaldiRecognizer(self._model, self.config.sample_rate)
            rec.AcceptWaveform(wav_bytes)
            result = json.loads(rec.Result() or "{}")
            text = (result.get("text") or "").strip().lower()
            for ww in self.config.wake_words:
                if ww in text:
                    return ww
            return None
        except Exception as exc:
            logger.debug("Vosk detect error: %s", exc)
            return None


class AudioCapture:
    """Captura de microfono local con sounddevice (baja latencia)."""

    def __init__(self, sample_rate: int = 16000, chunk_ms: int = 30) -> None:
        self.sample_rate = sample_rate
        self.chunk_size = int(sample_rate * chunk_ms / 1000)
        self._stream = None
        self._available = False
        try:
            import sounddevice as sd
            self._sd = sd
            self._available = True
        except Exception as exc:
            logger.warning("sounddevice unavailable: %s", exc)
            self._sd = None

    @property
    def available(self) -> bool:
        return self._available

    def list_devices(self) -> List[Dict[str, Any]]:
        if not self._available:
            return []
        try:
            devices = self._sd.query_devices()
            return [
                {"index": i, "name": d.get("name", ""), "channels": d.get("max_input_channels", 0)}
                for i, d in enumerate(devices)
                if d.get("max_input_channels", 0) > 0
            ]
        except Exception:
            return []

    def start_stream(self, callback: Callable[[bytes], None], device: Optional[int] = None) -> bool:
        if not self._available:
            return False
        try:
            import numpy as np

            def _ind_callback(indata, frames, time_info, status):  # noqa: ARG001
                callback(bytes(indata.tobytes()))

            self._stream = self._sd.InputStream(
                samplerate=self.sample_rate,
                blocksize=self.chunk_size,
                device=device,
                channels=1,
                dtype="int16",
                callback=_ind_callback,
            )
            self._stream.start()
            return True
        except Exception as exc:
            logger.warning("Audio stream start failed: %s", exc)
            return False

    def stop_stream(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def read_wav(self, duration_sec: float, device: Optional[int] = None) -> Optional[bytes]:
        """Graba `duration_seg` segundos y devuelve WAV PCM."""
        if not self._available:
            return None
        try:
            import numpy as np
            data = self._sd.rec(
                int(duration_sec * self.sample_rate),
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                device=device,
            )
            self._sd.wait()
            buf = io.BytesIO()
            with wave.open(buf, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(self.sample_rate)
                w.writeframes(bytes(data.tobytes()))
            return buf.getvalue()
        except Exception as exc:
            logger.warning("read_wav failed: %s", exc)
            return None


class DialogueEngine:
    """Maquina de estados: IDLE -> LISTENING -> PROCESSING -> SPEAKING."""

    def __init__(self, config: Optional[WakeWordConfig] = None) -> None:
        self.config = config or WakeWordConfig()
        self.detector = VoskWakeDetector(self.config)
        self.capture = AudioCapture(self.config.sample_rate, self.config.chunk_ms)
        self.ring = RingBuffer(5.0, self.config.sample_rate)
        self.sessions: Dict[str, DialogueSession] = {}
        self._active_session: Optional[DialogueSession] = None
        self._running = False
        self._listen_task: Optional[asyncio.Task] = None
        self._ws_clients: List[Any] = []
        self._lock = threading.Lock()
        self._transcriber = None
        self._tts = None
        self._llm = None

    @property
    def state(self) -> DialogueState:
        if self._active_session:
            return self._active_session.state
        return DialogueState.IDLE

    def _new_session(self) -> DialogueSession:
        s = DialogueSession(session_id=uuid.uuid4().hex[:12])
        with self._lock:
            self.sessions[s.session_id] = s
            self._active_session = s
        return s

    def _set_state(self, session: DialogueSession, st: DialogueState) -> None:
        session.state = st
        session.updated_at = time.time()
        self._broadcast({
            "event": WakeWordEvent.STATE_CHANGE.value,
            "session_id": session.session_id,
            "state": st.value,
            "timestamp": time.time(),
        })

    def _broadcast(self, payload: Dict[str, Any]) -> None:
        for ws in self._ws_clients:
            try:
                asyncio.ensure_future(ws.send_json(payload))
            except Exception:
                pass

    def _audio_callback(self, data: bytes) -> None:
        if self._active_session is None:
            self.ring.add(data)
            wav = self.ring.get_wav()
            ww = self.detector.detect(wav)
            if ww:
                self._on_wake(ww)
            return
        s = self._active_session
        if s.state == DialogueState.LISTENING:
            s.audio_chunks.append(data)
            self.ring.add(data)

    def _on_wake(self, word: str) -> None:
        s = self._new_session()
        s.metadata["wake_word"] = word
        self._set_state(s, DialogueState.LISTENING)
        self._broadcast({
            "event": WakeWordEvent.WAKE_DETECTED.value,
            "session_id": s.session_id,
            "wake_word": word,
            "timestamp": time.time(),
        })
        self.ring.clear()

    def _get_transcriber(self):
        if self._transcriber is None:
            try:
                from backend.audio.transcriber import get_transcriber
                self._transcriber = get_transcriber()
            except Exception as exc:
                logger.warning("transcriber import failed: %s", exc)
        return self._transcriber

    def _get_tts(self):
        if self._tts is None:
            try:
                from backend.audio.tts_generator import get_tts_generator
                self._tts = get_tts_generator()
            except Exception as exc:
                logger.warning("tts import failed: %s", exc)
        return self._tts

    def _get_llm(self):
        if self._llm is None:
            try:
                from backend.brain_orchestrator import brain
                self._llm = brain
            except Exception as exc:
                logger.warning("llm import failed: %s", exc)
        return self._llm

    async def start_continuous(self, device: Optional[int] = None) -> bool:
        if self._running:
            return True
        if not self.capture.available:
            logger.warning("AudioCapture not available; wake-word disabled")
            return False
        self._running = True
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.capture.start_stream(self._audio_callback, device),
        )
        return True

    def stop_continuous(self) -> None:
        self._running = False
        self.capture.stop_stream()

    async def process_session(self, session_id: str) -> None:
        with self._lock:
            s = self.sessions.get(session_id)
        if not s:
            return
        self._set_state(s, DialogueState.PROCESSING)
        try:
            raw = b"".join(s.audio_chunks)
            buf = io.BytesIO()
            with wave.open(buf, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(self.config.sample_rate)
                w.writeframes(raw)
            wav_bytes = buf.getvalue()
            tr = self._get_transcriber()
            text = ""
            if tr and tr.available:
                result = await tr.transcribe_bytes("session.wav", wav_bytes)
                text = (result.get("text") or "").strip()
            s.transcript = text
            self._broadcast({
                "event": WakeWordEvent.TRANSCRIPT_READY.value,
                "session_id": session_id,
                "text": text,
                "timestamp": time.time(),
            })
            if not text:
                self._set_state(s, DialogueState.IDLE)
                self._active_session = None
                return
            llm = self._get_llm()
            response = ""
            if llm:
                try:
                    response = await llm.process(text) if hasattr(llm, "process") else str(llm)
                except Exception as exc:
                    logger.warning("LLM error: %s", exc)
            s.response_text = response
            self._broadcast({
                "event": WakeWordEvent.LLM_CHUNK.value,
                "session_id": session_id,
                "text": response,
                "timestamp": time.time(),
            })
            tts = self._get_tts()
            if tts and tts.tts_engine.available:
                self._broadcast({
                    "event": WakeWordEvent.TTS_START.value,
                    "session_id": session_id,
                    "timestamp": time.time(),
                })
                try:
                    result = await tts.synthesize_text_async(response)
                    self._broadcast({
                        "event": WakeWordEvent.TTS_AUDIO.value,
                        "session_id": session_id,
                        "audio_url": f"/api/audio/tts/file/{Path(result.audio_path).name}",
                        "duration_sec": result.duration_sec,
                        "timestamp": time.time(),
                    })
                except Exception as exc:
                    logger.warning("TTS error: %s", exc)
            self._broadcast({
                "event": WakeWordEvent.TTS_DONE.value,
                "session_id": session_id,
                "timestamp": time.time(),
            })
            self._set_state(s, DialogueState.SPEAKING)
        except Exception as exc:
            logger.warning("process_session error: %s", exc)
            self._set_state(s, DialogueState.ERROR)
            self._broadcast({
                "event": WakeWordEvent.ERROR.value,
                "session_id": session_id,
                "error": str(exc),
                "timestamp": time.time(),
            })
        finally:
            await asyncio.sleep(2.0)
            with self._lock:
                if self._active_session is s:
                    self._active_session = None
            self._set_state(s, DialogueState.IDLE)

    def register_ws(self, ws: Any) -> None:
        self._ws_clients.append(ws)

    def unregister_ws(self, ws: Any) -> None:
        if ws in self._ws_clients:
            self._ws_clients.remove(ws)

    def status(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "state": self.state.value,
            "wake_word_detector": {
                "available": self.detector.available,
                "wake_words": self.config.wake_words,
            },
            "audio_capture": {
                "available": self.capture.available,
                "sample_rate": self.config.sample_rate,
                "devices": self.capture.list_devices(),
            },
            "active_session": self._active_session.session_id if self._active_session else None,
            "total_sessions": len(self.sessions),
        }


wake_word_engine = DialogueEngine()