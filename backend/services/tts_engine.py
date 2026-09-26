"""TTS Engine for AURA - Real-time text-to-speech streaming.

Prefers Piper/Kokoro if available; falls back to pyttsx3/gTTS.
Outputs PCM/WAV bytes suitable for WebRTC audio track injection.
"""

from __future__ import annotations

import io
import logging
import queue
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("AURATtsEngine")

TTS_SAMPLE_RATE = 22050
TTS_CHANNELS = 1
TTS_SAMPLE_WIDTH = 2
TTS_FRAME_MS = 20
TTS_FRAME_SIZE = int(TTS_SAMPLE_RATE * TTS_FRAME_MS / 1000) * TTS_SAMPLE_WIDTH * TTS_CHANNELS

try:
    import numpy as np
except Exception:
    np = None

try:
    import soundfile as sf
except Exception:
    sf = None

try:
    import pyttsx3
except Exception:
    pyttsx3 = None

try:
    from gtts import gTTS
except Exception:
    gTTS = None

try:
    from piper.voice import PiperVoice
except Exception:
    PiperVoice = None

try:
    from kokoro import KPipeline
except Exception:
    KPipeline = None


class TTSEngine:
    def __init__(self, voice: str = "es_ES") -> None:
        self.voice = voice
        self._backend = self._init_backend()
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._running = True
        threading.Thread(target=self._synthesize_loop, daemon=True).start()

    def _init_backend(self) -> str:
        if PiperVoice is not None:
            return "piper"
        if KPipeline is not None:
            return "kokoro"
        if pyttsx3 is not None:
            return "pyttsx3"
        if gTTS is not None:
            return "gtts"
        return "disabled"

    def _synthesize_loop(self) -> None:
        while self._running:
            try:
                text = self._queue.get(timeout=1)
            except Exception:
                continue
            try:
                pcm = self._synthesize(text)
                if pcm:
                    self._on_audio(pcm)
            except Exception:
                pass

    def _synthesize(self, text: str) -> Optional[bytes]:
        if self._backend == "piper":
            return self._synthesize_piper(text)
        if self._backend == "kokoro":
            return self._synthesize_kokoro(text)
        if self._backend == "pyttsx3":
            return self._synthesize_pyttsx3(text)
        if self._backend == "gtts":
            return self._synthesize_gtts(text)
        return self._synthesize_fallback(text)

    def _synthesize_piper(self, text: str) -> Optional[bytes]:
        try:
            voice = PiperVoice.load("es_ES")
            audio = voice.synthesize(text)
            buf = io.BytesIO()
            sf.write(buf, audio, TTS_SAMPLE_RATE, format="WAV")
            return buf.getvalue()
        except Exception:
            return None

    def _synthesize_kokoro(self, text: str) -> Optional[bytes]:
        try:
            pipeline = KPipeline(lang_code="es")
            generator = pipeline(text, voice=self.voice)
            audio = next(generator).audio
            buf = io.BytesIO()
            sf.write(buf, audio, TTS_SAMPLE_RATE, format="WAV")
            return buf.getvalue()
        except Exception:
            return None

    def _synthesize_pyttsx3(self, text: str) -> Optional[bytes]:
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", 160)
            engine.setProperty("volume", 1.0)
            buf = io.BytesIO()
            engine.save_to_file(text, buf)
            engine.runAndWait()
            return buf.getvalue()
        except Exception:
            return None

    def _synthesize_gtts(self, text: str) -> Optional[bytes]:
        try:
            tts = gTTS(text=text, lang="es")
            buf = io.BytesIO()
            tts.write_to_fp(buf)
            return buf.getvalue()
        except Exception:
            return None

    def _synthesize_fallback(self, text: str) -> Optional[bytes]:
        try:
            if np is None or sf is None:
                return None
            duration = max(0.5, min(4.0, len(text) * 0.06))
            t = np.linspace(0, duration, int(TTS_SAMPLE_RATE * duration))
            freq = 220.0
            audio = np.sin(2 * np.pi * freq * t) * 0.1
            audio = (audio * 32767).astype(np.int16)
            buf = io.BytesIO()
            sf.write(buf, audio, TTS_SAMPLE_RATE, format="WAV")
            return buf.getvalue()
        except Exception:
            return None

    def _on_audio(self, wav_bytes: bytes) -> None:
        try:
            if sf is None:
                return
            data, sr = sf.read(io.BytesIO(wav_bytes), dtype="float32")
            if np is None:
                return
            pcm16 = (data * 32767).astype(np.int16).tobytes()
            if hasattr(self, "on_pcm"):
                self.on_pcm(pcm16)
        except Exception:
            pass

    def speak(self, text: str) -> None:
        self._queue.put(text)

    def shutdown(self) -> None:
        self._running = False

    def get_status(self) -> Dict[str, Any]:
        return {
            "backend": self._backend,
            "queue_size": self._queue.qsize(),
            "sample_rate": TTS_SAMPLE_RATE,
        }
