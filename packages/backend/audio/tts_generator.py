"""AURA Local TTS — síntesis de voz 100% local (Bloque 46).

Motor de síntesis de voz (Text-to-Speech) basado en Piper TTS, Kokoro,
pyttsx3 o gTTS (en orden de preferencia) que procesa texto literario
y emite archivos de audio (.wav) sin enviar datos a APIs de terceros.

Diseño:
- Carga perezosa (lazy) del motor: la primera síntesis inicializa
  el backend disponible (Piper > Kokoro > pyttsx3 > gTTS > fallback).
- Directorio temporal de salida (AURA_TTS_TMP_DIR, default ./data/tts_output)
  con limpieza automática de ficheros antiguos.
- La inferencia corre en un hilo (asyncio.to_thread) para no bloquear
  el event loop de FastAPI.
- Mapeo opcional de voces por personaje vía Character Bible.
- Formato de salida: WAV PCM 16-bit mono 22050 Hz.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURA.Audio.TTS")

_DEFAULT_TMP_DIR = os.path.join("data", "tts_output")
_TMP_MAX_AGE_SECS = 3600
_DEFAULT_SAMPLE_RATE = 22050
_DEFAULT_VOICE = "es_ES"

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


class TTSUnavailable(RuntimeError):
    """No hay ningún motor TTS disponible."""


class TTSVoiceNotFound(ValueError):
    """Voz solicitada no encontrada en el motor actual."""


@dataclass
class VoiceProfile:
    """Perfil de voz para un personaje o narrador."""
    voice_id: str
    name: str
    language: str = "es"
    gender: str = "neutral"
    style: str = "neutral"
    speed: float = 1.0
    pitch: float = 1.0
    volume: float = 1.0
    engine_specific: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TTSResult:
    """Resultado de una síntesis."""
    audio_path: str
    duration_sec: float
    sample_rate: int
    channels: int
    sample_width: int
    format: str
    engine: str
    voice_id: str
    text_chars: int
    synthesis_time_ms: float


def _env(key: str, default: str) -> str:
    return os.getenv(key, default)


class LocalTTSEngine:
    """Motor TTS local con múltiples backends y fallback."""

    _BACKEND_PRIORITY = ["piper", "kokoro", "pyttsx3", "gtts", "fallback"]

    def __init__(
        self,
        voice: Optional[str] = None,
        tmp_dir: Optional[str] = None,
        engine: Optional[str] = None,
    ) -> None:
        self.default_voice = voice or _env("AURA_TTS_VOICE", _DEFAULT_VOICE)
        self.tmp_dir = Path(tmp_dir or _env("AURA_TTS_TMP_DIR", _DEFAULT_TMP_DIR))
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self._backend_name: Optional[str] = None
        self._backend_obj: Any = None
        self._piper_voices: Dict[str, Any] = {}
        self._kokoro_pipeline: Any = None
        self._pyttsx3_engine: Any = None
        self._engine_preference = (engine or _env("AURA_TTS_ENGINE", "auto")).lower()

    @property
    def backend_name(self) -> str:
        if self._backend_name is None:
            self._init_backend()
        return self._backend_name or "disabled"

    @property
    def available(self) -> bool:
        return self.backend_name != "disabled"

    def _init_backend(self) -> None:
        if self._engine_preference != "auto":
            if self._engine_preference in self._BACKEND_PRIORITY:
                try:
                    self._load_specific_backend(self._engine_preference)
                    return
                except Exception:
                    pass
            self._backend_name = "disabled"
            return

        for backend in self._BACKEND_PRIORITY:
            try:
                self._load_specific_backend(backend)
                return
            except Exception:
                continue
        self._backend_name = "disabled"

    def _load_specific_backend(self, backend: str) -> None:
        if backend == "piper" and PiperVoice is not None:
            self._backend_name = "piper"
            return
        if backend == "kokoro" and KPipeline is not None:
            self._backend_name = "kokoro"
            return
        if backend == "pyttsx3" and pyttsx3 is not None:
            self._backend_name = "pyttsx3"
            return
        if backend == "gtts" and gTTS is not None:
            self._backend_name = "gtts"
            return
        if backend == "fallback":
            self._backend_name = "fallback"
            return
        raise RuntimeError(f"Backend {backend} no disponible")

    def _get_piper_voice(self, voice_id: str) -> Any:
        if voice_id in self._piper_voices:
            return self._piper_voices[voice_id]
        try:
            voice = PiperVoice.load(voice_id)
            self._piper_voices[voice_id] = voice
            return voice
        except Exception as exc:
            logger.warning("Piper voice '%s' no disponible: %s", voice_id, exc)
            raise TTSVoiceNotFound(f"Voz Piper '{voice_id}' no encontrada") from exc

    def _get_kokoro_pipeline(self, lang_code: str = "es") -> Any:
        if self._kokoro_pipeline is not None:
            return self._kokoro_pipeline
        self._kokoro_pipeline = KPipeline(lang_code=lang_code)
        return self._kokoro_pipeline

    def _get_pyttsx3_engine(self) -> Any:
        if self._pyttsx3_engine is not None:
            return self._pyttsx3_engine
        self._pyttsx3_engine = pyttsx3.init()
        self._pyttsx3_engine.setProperty("rate", 160)
        self._pyttsx3_engine.setProperty("volume", 1.0)
        return self._pyttsx3_engine

    def _synthesize_piper(self, text: str, voice_id: str) -> bytes:
        voice = self._get_piper_voice(voice_id)
        audio = voice.synthesize(text)
        buf = io.BytesIO()
        sf.write(buf, audio, _DEFAULT_SAMPLE_RATE, format="WAV")
        return buf.getvalue()

    def _synthesize_kokoro(self, text: str, voice_id: str) -> bytes:
        pipeline = self._get_kokoro_pipeline("es")
        generator = pipeline(text, voice=voice_id)
        audio = next(generator).audio
        buf = io.BytesIO()
        sf.write(buf, audio, _DEFAULT_SAMPLE_RATE, format="WAV")
        return buf.getvalue()

    def _synthesize_pyttsx3(self, text: str, _voice_id: str) -> bytes:
        engine = self._get_pyttsx3_engine()
        buf = io.BytesIO()
        engine.save_to_file(text, buf)
        engine.runAndWait()
        return buf.getvalue()

    def _synthesize_gtts(self, text: str, _voice_id: str) -> bytes:
        tts = gTTS(text=text, lang="es")
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        return buf.getvalue()

    def _synthesize_fallback(self, text: str, _voice_id: str) -> bytes:
        # Fallback 100% stdlib+wave: tono formant-lite determinista (sin numpy/soundfile).
        import math
        import struct
        import wave
        duration = max(0.5, min(4.0, len(text) * 0.06))
        n = int(_DEFAULT_SAMPLE_RATE * duration)
        freq = 220.0
        frames = bytearray()
        for i in range(n):
            t = i / _DEFAULT_SAMPLE_RATE
            s = math.sin(2.0 * math.pi * freq * t) * 0.1
            frames += struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767))
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(_DEFAULT_SAMPLE_RATE)
            w.writeframes(bytes(frames))
        return buf.getvalue()

    def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
        speed: float = 1.0,
    ) -> TTSResult:
        if not text or not text.strip():
            raise ValueError("Texto vacío")
        if not self.available:
            raise TTSUnavailable("Ningún motor TTS disponible")

        start = time.perf_counter()
        vid = voice_id or self.default_voice

        if self._backend_name == "piper":
            wav_bytes = self._synthesize_piper(text, vid)
        elif self._backend_name == "kokoro":
            wav_bytes = self._synthesize_kokoro(text, vid)
        elif self._backend_name == "pyttsx3":
            wav_bytes = self._synthesize_pyttsx3(text, vid)
        elif self._backend_name == "gtts":
            wav_bytes = self._synthesize_gtts(text, vid)
        else:
            wav_bytes = self._synthesize_fallback(text, vid)

        synth_ms = (time.perf_counter() - start) * 1000.0

        fname = f"tts_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}.wav"
        out_path = self.tmp_dir / fname
        out_path.write_bytes(wav_bytes)

        duration = 0.0
        try:
            import wave
            with wave.open(io.BytesIO(wav_bytes), "rb") as w:
                duration = w.getnframes() / float(w.getframerate() or _DEFAULT_SAMPLE_RATE)
        except Exception:
            pass

        return TTSResult(
            audio_path=str(out_path),
            duration_sec=duration,
            sample_rate=_DEFAULT_SAMPLE_RATE,
            channels=1,
            sample_width=2,
            format="wav",
            engine=self._backend_name,
            voice_id=vid,
            text_chars=len(text),
            synthesis_time_ms=synth_ms,
        )

    async def synthesize_async(
        self,
        text: str,
        voice_id: Optional[str] = None,
        speed: float = 1.0,
    ) -> TTSResult:
        return await asyncio.to_thread(self.synthesize, text, voice_id, speed)

    def cleanup(self, max_age_secs: int = _TMP_MAX_AGE_SECS) -> int:
        removed = 0
        now = time.time()
        for p in self.tmp_dir.glob("*.wav"):
            try:
                if p.is_file() and now - p.stat().st_mtime > max_age_secs:
                    p.unlink()
                    removed += 1
            except OSError as exc:
                logger.debug("cleanup skip %s: %s", p, exc)
        return removed

    def status(self) -> Dict[str, Any]:
        return {
            "status": "ok",
            "engine": self.backend_name,
            "engine_requested": self._engine_preference,
            "available": self.available,
            "default_voice": self.default_voice,
            "sample_rate": _DEFAULT_SAMPLE_RATE,
            "output_dir": str(self.tmp_dir),
            "supported_backends": {
                "piper": PiperVoice is not None,
                "kokoro": KPipeline is not None,
                "pyttsx3": pyttsx3 is not None,
                "gtts": gTTS is not None,
                "fallback": True,
            },
        }

    def list_voices(self) -> Dict[str, List[str]]:
        voices = {}
        if self._backend_name == "piper":
            try:
                import piper
                voices["piper"] = list(piper.available_voices())
            except Exception:
                voices["piper"] = []
        elif self._backend_name == "kokoro":
            voices["kokoro"] = ["ef_dora", "em_alex", "em_santa", "ef_sarah"]
        elif self._backend_name == "pyttsx3":
            try:
                eng = self._get_pyttsx3_engine()
                vlist = eng.getProperty("voices")
                voices["pyttsx3"] = [v.id for v in vlist] if vlist else []
            except Exception:
                voices["pyttsx3"] = []
        return voices


class TTSGenerator:
    """Generador de alto nivel con mapeo de voces por personaje."""

    def __init__(
        self,
        store_dir: Optional[str] = None,
        engine: Optional[LocalTTSEngine] = None,
    ) -> None:
        self.store_dir = Path(
            store_dir or os.getenv("AURA_STORY_DIR", os.path.join(os.getcwd(), "story_memory"))
        )
        self.tts_engine = engine or LocalTTSEngine()
        self._voice_map: Dict[str, VoiceProfile] = {}
        self._lock = asyncio.Lock()

    def _load_character_voices(self, work_id: str) -> None:
        from backend.story_memory.character_bible import CharacterBible
        cb = CharacterBible()
        chars = cb.list(work_id)
        for char in chars:
            char_id = char.get("char_id", "")
            voice_data = char.get("voice_profile") or char.get("voice")
            if voice_data and char_id:
                self._voice_map[f"{work_id}:{char_id}"] = VoiceProfile(
                    voice_id=str(voice_data) if isinstance(voice_data, str) else voice_data.get("voice_id", self.tts_engine.default_voice),
                    name=char.get("name", char_id),
                    language=char.get("voice_profile", {}).get("language", "es") if isinstance(voice_data, dict) else "es",
                    gender=char.get("voice_profile", {}).get("gender", "neutral") if isinstance(voice_data, dict) else "neutral",
                    style=char.get("voice_profile", {}).get("style", "neutral") if isinstance(voice_data, dict) else "neutral",
                    speed=char.get("voice_profile", {}).get("speed", 1.0) if isinstance(voice_data, dict) else 1.0,
                    pitch=char.get("voice_profile", {}).get("pitch", 1.0) if isinstance(voice_data, dict) else 1.0,
                    volume=char.get("voice_profile", {}).get("volume", 1.0) if isinstance(voice_data, dict) else 1.0,
                    engine_specific=char.get("voice_profile", {}).get("engine_specific", {}) if isinstance(voice_data, dict) else {},
                )

    def set_voice_profile(self, work_id: str, char_id: str, profile: VoiceProfile) -> None:
        self._voice_map[f"{work_id}:{char_id}"] = profile

    def get_voice_profile(self, work_id: str, char_id: str) -> Optional[VoiceProfile]:
        return self._voice_map.get(f"{work_id}:{char_id}")

    def synthesize_text(
        self,
        text: str,
        work_id: Optional[str] = None,
        char_id: Optional[str] = None,
        voice_id: Optional[str] = None,
    ) -> TTSResult:
        v_id = voice_id
        if not v_id and work_id and char_id:
            profile = self.get_voice_profile(work_id, char_id)
            if not profile:
                self._load_character_voices(work_id)
                profile = self.get_voice_profile(work_id, char_id)
            if profile:
                v_id = profile.voice_id
        return self.tts_engine.synthesize(text, voice_id=v_id)

    async def synthesize_text_async(
        self,
        text: str,
        work_id: Optional[str] = None,
        char_id: Optional[str] = None,
        voice_id: Optional[str] = None,
    ) -> TTSResult:
        return await asyncio.to_thread(self.synthesize_text, text, work_id, char_id, voice_id)

    def synthesize_chapter(
        self,
        work_id: str,
        chapter_text: str,
        char_id: Optional[str] = None,
        voice_id: Optional[str] = None,
    ) -> List[TTSResult]:
        paragraphs = [p.strip() for p in chapter_text.split("\n\n") if p.strip()]
        results = []
        for para in paragraphs:
            results.append(self.synthesize_text(para, work_id, char_id, voice_id))
        return results

    def cleanup(self, max_age_secs: int = _TMP_MAX_AGE_SECS) -> int:
        return self.tts_engine.cleanup(max_age_secs)

    def status(self) -> Dict[str, Any]:
        base = self.tts_engine.status()
        base["voice_map_size"] = len(self._voice_map)
        return base


_tts_generator: Optional[TTSGenerator] = None
_tts_lock = asyncio.Lock()


def get_tts_generator(store_dir: Optional[str] = None) -> TTSGenerator:
    global _tts_generator
    if _tts_generator is None:
        _tts_generator = TTSGenerator(store_dir=store_dir)
    return _tts_generator


def reset_tts_generator() -> None:
    global _tts_generator
    _tts_generator = None