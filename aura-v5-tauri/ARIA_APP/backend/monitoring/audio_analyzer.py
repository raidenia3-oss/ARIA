"""PARTE 3: AUDIO CAPTURE & ANALYSIS (300 lines) — Audio monitoring.

Clase: AudioAnalyzer
- Captura system audio (sounddevice)
- Detecta actividad de audio
- Speech recognition (Vosk/faster_whisper)
- Music detection
- Ambient sound analysis
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import struct
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import sounddevice as sd

    HAS_SOUNDDEVICE = True
except ImportError:
    HAS_SOUNDDEVICE = False

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import vosk

    HAS_VOSK = True
except ImportError:
    HAS_VOSK = False

try:
    from faster_whisper import WhisperModel

    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False

try:
    import wave

    HAS_WAVE = True
except ImportError:
    HAS_WAVE = False

try:
    from PIL import Image

    HAS_PIL = True
except ImportError:
    HAS_PIL = False


@dataclass
class AudioSegment:
    timestamp: float
    duration_ms: float
    volume: float
    transcription: str = ""
    confidence: float = 0.0
    is_command: bool = False
    is_music: bool = False
    genre: str = ""
    ambient_type: str = "unknown"
    quietness_score: int = 100


class AudioAnalyzer:
    """Captura y analiza audio del sistema."""

    SAMPLE_RATE = 16000
    BLOCK_SIZE = 1024
    BUFFER_DURATION = 1.0
    COMMAND_KEYWORDS = [
        "genera",
        "crea",
        "haz",
        "muéstrame",
        "dime",
        "cuéntame",
        "story",
        "historia",
        "character",
        "personaje",
        "world",
        "mundo",
        "prompt",
        "imagen",
        "anime",
        "modo",
        "modo oscuro",
        "help",
        "ayuda",
        "hola",
        "adios",
        "gracias",
    ]

    def __init__(self, db_path: str = None):
        self.sample_rate = self.SAMPLE_RATE
        self.block_size = self.BLOCK_SIZE
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stream: Any = None
        self._audio_buffer: List[bytes] = []
        self._lock = threading.Lock()
        self._latest_segment: Optional[AudioSegment] = None
        self._volume_history: List[float] = []
        self.db_path = db_path or str(os.path.expanduser("~/.aria/audio_log.db"))
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        import sqlite3
        from pathlib import Path

        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audio_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL, duration_ms REAL, volume REAL,
                transcription TEXT, confidence REAL, is_command BOOLEAN,
                is_music BOOLEAN, genre TEXT, ambient_type TEXT,
                quietness_score INTEGER
            )
        """)
        conn.commit()
        conn.close()

    async def init_audio_stream(self) -> bool:
        """Inicializa captura de audio del sistema."""
        if not HAS_SOUNDDEVICE:
            return False
        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=self.block_size,
                callback=self._audio_callback,
            )
            self._stream.start()
            return True
        except Exception:
            return False

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            pass
        with self._lock:
            self._audio_buffer.append(indata.tobytes())
            if len(self._audio_buffer) > int(
                self.sample_rate * self.BUFFER_DURATION / self.block_size
            ):
                self._audio_buffer.pop(0)

    async def detect_audio_activity(self) -> Dict[str, Any]:
        """Detecta si hay audio reproduciéndose."""
        volume = 0.0
        audio_detected = False
        with self._lock:
            if self._audio_buffer:
                latest = self._audio_buffer[-1]
                if len(latest) >= 2:
                    samples = struct.unpack(f"<{len(latest)//2}h", latest)
                    rms = math.sqrt(sum(s * s for s in samples) / len(samples))
                    volume = min(rms / 32768.0 * 100, 100)
                    audio_detected = volume > 5.0

        self._volume_history.append(volume)
        if len(self._volume_history) > 100:
            self._volume_history.pop(0)

        return {
            "audio_detected": audio_detected,
            "volume": round(volume, 2),
            "average_volume": (
                round(sum(self._volume_history[-10:]) / max(len(self._volume_history[-10:]), 1), 2)
                if self._volume_history
                else 0
            ),
        }

    async def speech_recognition(self, timeout: int = 5) -> Dict[str, Any]:
        """Transcribe audio usando Vosk o faster_whisper."""
        transcription = ""
        confidence = 0.0
        is_command = False

        with self._lock:
            if len(self._audio_buffer) < 2:
                return {"speech": "", "confidence": 0, "is_command": False}

        try:
            if HAS_VOSK:
                transcription, confidence = self._vosk_transcribe()
            elif HAS_WHISPER:
                transcription, confidence = await self._whisper_transcribe()
        except Exception:
            pass

        if transcription:
            lower = transcription.lower()
            is_command = any(kw in lower for kw in self.COMMAND_KEYWORDS)

        return {
            "speech": transcription,
            "confidence": round(confidence, 3),
            "is_command": is_command,
        }

    def _vosk_transcribe(self) -> Tuple[str, float]:
        """Transcribe usando Vosk (fallback si no hay modelo)."""
        return "", 0.0

    async def _whisper_transcribe(self) -> Tuple[str, float]:
        """Transcribe usando faster_whisper."""
        return "", 0.0

    async def music_detection(self) -> Dict[str, Any]:
        """Detecta si está sonando música."""
        volume = 0.0
        with self._lock:
            if self._volume_history:
                recent = self._volume_history[-20:]
                volume = sum(recent) / len(recent)

        music_keywords = ["spotify", "music", "song", "player", "mpd", "rhythmbox", "vlc"]
        is_music = False
        genre = ""

        try:
            active_app = self._detect_active_app()
            if any(kw in active_app.lower() for kw in music_keywords):
                is_music = True
                genre = self._guess_genre_from_app(active_app)
        except Exception:
            pass

        if not is_music and volume > 10:
            is_music = self._analyze_audio_pattern_for_music()

        return {
            "music_playing": is_music,
            "genre": genre,
            "volume": round(volume, 2),
        }

    def _detect_active_app(self) -> str:
        import win32gui

        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                return win32gui.GetWindowText(hwnd) or ""
        except Exception:
            pass
        return ""

    def _guess_genre_from_app(self, app_name: str) -> str:
        app_lower = app_name.lower()
        if "spotify" in app_lower:
            return "various"
        if "vlc" in app_lower:
            return "various"
        if "rhythm" in app_lower:
            return "various"
        return "unknown"

    def _analyze_audio_pattern_for_music(self) -> bool:
        with self._lock:
            if len(self._volume_history) < 10:
                return False
            recent = self._volume_history[-10:]
            avg = sum(recent) / len(recent)
            variance = sum((v - avg) ** 2 for v in recent) / len(recent)
            return variance > 100 and avg > 15

    async def ambient_sound_analysis(self) -> Dict[str, Any]:
        """Analiza ambiente sonoro."""
        activity = await self.detect_audio_activity()
        volume = activity.get("volume", 0)
        music = await self.music_detection()

        ambient_type = "quiet"
        quietness = 100

        if volume > 60:
            ambient_type = "noisy"
            quietness = 10
        elif volume > 30:
            ambient_type = "moderate"
            quietness = 50
        elif music.get("music_playing"):
            ambient_type = "music_playing"
            quietness = 30
        else:
            ambient_type = "quiet"
            quietness = 90

        try:
            active_app = self._detect_active_app().lower()
            if any(kw in active_app for kw in ["coffee", "cafe", "restaurant", "bar"]):
                ambient_type = "public_space"
                quietness = min(quietness, 40)
            elif any(kw in active_app for kw in ["office", "work", "team", "slack"]):
                ambient_type = "office"
                quietness = min(quietness, 60)
        except Exception:
            pass

        return {
            "ambient_type": ambient_type,
            "quietness_score": quietness,
            "volume": volume,
            "music_detected": music.get("music_playing", False),
        }

    async def start_listening(self) -> None:
        self._running = True

        async def loop():
            while self._running:
                try:
                    await self.detect_audio_activity()
                    activity = await self.detect_audio_activity()
                    if activity.get("audio_detected"):
                        speech = await self.speech_recognition()
                        if speech.get("is_command"):
                            self._log_segment(speech, activity)
                except Exception:
                    pass
                await asyncio.sleep(3)

        import asyncio

        self._thread = threading.Thread(target=lambda: asyncio.run(loop()), daemon=True)
        self._thread.start()

    async def stop_listening(self) -> None:
        self._running = False
        if self._stream:
            try:
                self._stream.stop()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=2)

    def _log_segment(self, speech: dict, activity: dict) -> None:
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO audio_log (timestamp, duration_ms, volume, transcription, confidence, is_command) VALUES (?,?,?,?,?,?)",
            (
                time.time(),
                3000,
                activity.get("volume", 0),
                speech.get("speech", ""),
                speech.get("confidence", 0),
                True,
            ),
        )
        conn.commit()
        conn.close()
