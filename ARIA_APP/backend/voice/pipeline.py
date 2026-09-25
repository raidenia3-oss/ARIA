"""ARIA Voice Pipeline — STT, TTS, Wake Word."""

from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class STTPipeline:
    def __init__(self, language: str = "es") -> None:
        self.language = language
        self._whisper_model = None
        self._vosk_model = None

    def transcribe(self, audio_path: str, engine: str = "auto") -> Dict[str, Any]:
        if not os.path.exists(audio_path):
            return {"status": "error", "error": f"audio not found: {audio_path}"}
        if engine in ("auto", "whisper"):
            result = self._transcribe_whisper(audio_path)
            if result.get("status") == "ok":
                return result
        if engine in ("auto", "vosk"):
            result = self._transcribe_vosk(audio_path)
            if result.get("status") == "ok":
                return result
        return {"status": "error", "error": "all engines failed"}

    def _transcribe_whisper(self, audio_path: str) -> Dict[str, Any]:
        try:
            from faster_whisper import WhisperModel

            if self._whisper_model is None:
                self._whisper_model = WhisperModel("base", compute_type="int8")
            segments, info = self._whisper_model.transcribe(audio_path, language=self.language)
            text = " ".join(segment.text for segment in segments).strip()
            return {
                "status": "ok",
                "engine": "faster-whisper",
                "text": text,
                "language": info.language,
                "duration": info.duration,
            }
        except Exception as e:
            return {"status": "error", "engine": "faster-whisper", "error": str(e)}

    def _transcribe_vosk(self, audio_path: str) -> Dict[str, Any]:
        try:
            from vosk import KaldiRecognizer, Model, SetLogLevel  # type: ignore

            SetLogLevel(-1)
            if self._vosk_model is None:
                model_path = os.environ.get("VOSK_MODEL_PATH", "")
                if not model_path or not os.path.exists(model_path):
                    return {
                        "status": "error",
                        "engine": "vosk",
                        "error": "VOSK_MODEL_PATH not set or missing",
                    }
                self._vosk_model = Model(model_path)
            wf = open(audio_path, "rb")
            rec = KaldiRecognizer(self._vosk_model, 16000)
            rec.SetWords(True)
            result_text = ""
            while True:
                data = wf.read(4096)
                if len(data) == 0:
                    break
                if rec.AcceptWaveform(data):
                    part = json.loads(rec.Result())
                    result_text += part.get("text", "") + " "
            final = json.loads(rec.FinalResult())
            result_text += final.get("text", "")
            wf.close()
            return {"status": "ok", "engine": "vosk", "text": result_text.strip()}
        except Exception as e:
            return {"status": "error", "engine": "vosk", "error": str(e)}


class TTSPipeline:
    def __init__(self, default_voice: str = "es-ES-ElviraNeural") -> None:
        self.default_voice = default_voice
        self._tts_engines: Dict[str, Any] = {}

    def speak(self, text: str, voice: Optional[str] = None, engine: str = "auto") -> Dict[str, Any]:
        if not text:
            return {"status": "error", "error": "empty text"}
        voice = voice or self.default_voice
        if engine in ("auto", "edge"):
            result = self._speak_edge(text, voice)
            if result.get("status") == "ok":
                return result
        if engine in ("auto", "piper"):
            result = self._speak_piper(text, voice)
            if result.get("status") == "ok":
                return result
        if engine in ("auto", "pyttsx3"):
            result = self._speak_pyttsx3(text, voice)
            if result.get("status") == "ok":
                return result
        return {"status": "error", "error": "all engines failed"}

    def _speak_edge(self, text: str, voice: str) -> Dict[str, Any]:
        try:
            import asyncio

            import edge_tts

            out_path = tempfile.gettempdir() + f"/aura-tts-{int(time.time()*1000)}.mp3"

            async def generate():
                communicate = edge_tts.Communicate(text, voice)
                await communicate.save(out_path)

            asyncio.run(generate())
            return {"status": "ok", "engine": "edge-tts", "audio": out_path, "voice": voice}
        except Exception as e:
            return {"status": "error", "engine": "edge-tts", "error": str(e)}

    def _speak_piper(self, text: str, voice: str) -> Dict[str, Any]:
        try:
            import sounddevice as sd  # type: ignore
            from piper.voice import PiperVoice  # type: ignore

            model_path = os.environ.get("PIPER_MODEL_PATH", "")
            if not model_path or not os.path.exists(model_path):
                return {"status": "error", "engine": "piper", "error": "PIPER_MODEL_PATH not set"}
            if "piper" not in self._tts_engines:
                self._tts_engines["piper"] = PiperVoice.load(model_path)
            voice_engine = self._tts_engines["piper"]
            out_path = tempfile.gettempdir() + f"/aura-piper-{int(time.time()*1000)}.wav"
            with open(out_path, "wb") as f:
                voice_engine.synthesize(text, f)
            return {"status": "ok", "engine": "piper", "audio": out_path, "voice": voice}
        except Exception as e:
            return {"status": "error", "engine": "piper", "error": str(e)}

    def _speak_pyttsx3(self, text: str, voice: str) -> Dict[str, Any]:
        try:
            import pyttsx3

            if "pyttsx3" not in self._tts_engines:
                engine = pyttsx3.init()
                engine.setProperty("rate", 170)
                engine.setProperty("volume", 1.0)
                self._tts_engines["pyttsx3"] = engine
            engine = self._tts_engines["pyttsx3"]
            engine.say(text)
            engine.runAndWait()
            return {"status": "ok", "engine": "pyttsx3", "voice": voice}
        except Exception as e:
            return {"status": "error", "engine": "pyttsx3", "error": str(e)}


class WakeWordDetector:
    """Detección de wake-word.

    Dos modos, para que el STT y el wake-word queden cableados de verdad:
    - ``listen(audio_path)``: audio -> openWakeWord (modelo acústico).
    - ``detect_text(text)``: transcripción del STT -> coincidencia léxica.
      Es el camino que usan los clientes (HUD/Tk) cuando el STT ya devolvió texto.
    """

    WAKE_WORDS: List[str] = ["hey aura", "hola aura", "ok aura", "oye aura", "ARIA"]

    def __init__(self, wake_word: str = "hey aura") -> None:
        self.wake_word = wake_word
        self.wake_words = list(self.WAKE_WORDS)
        self._model = None

    @staticmethod
    def _normalize(text: str) -> str:
        """Minúsculas, sin acentos y con espacios colapsados (para comparar)."""
        lowered = (text or "").strip().lower()
        for src, dst in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ü", "u")):
            lowered = lowered.replace(src, dst)
        return re.sub(r"\s+", " ", lowered)

    def detect_text(self, text: str, wake_words: Optional[List[str]] = None) -> Dict[str, Any]:
        """Detecta el wake-word en una transcripción y devuelve el comando limpio."""
        normalized = self._normalize(text)
        words = wake_words or self.wake_words
        matched = ""
        position = -1
        for candidate in sorted(words, key=len, reverse=True):
            needle = self._normalize(candidate)
            if not needle:
                continue
            idx = normalized.find(needle)
            if idx >= 0 and (position < 0 or idx < position):
                matched = candidate
                position = idx
        if position < 0:
            return {
                "detected": False,
                "wake_word": self.wake_word,
                "text": (text or "").strip(),
                "command": "",
            }
        # Recorta desde el final del wake-word: "hey aura, estado" -> "estado"
        command = normalized[position + len(self._normalize(matched)) :]
        command = command.lstrip(" ,.:;¡!¿?-")
        return {
            "detected": True,
            "wake_word": matched,
            "text": (text or "").strip(),
            "command": command,
            "command_original": (text or "").strip(),
        }

    def listen(self, audio_path: str, threshold: float = 0.5) -> Dict[str, Any]:
        try:
            from openwakeword.model import Model  # type: ignore

            if self._model is None:
                self._model = Model(wakeword_models=[self.wake_word])
            import wave

            import numpy as np

            with wave.open(audio_path, "rb") as wf:
                frames = wf.readframes(wf.getnframes())
                audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            prediction = self._model.predict(audio)
            score = float(prediction.get(self.wake_word, [0])[0])
            return {
                "status": "ok",
                "wake_word": self.wake_word,
                "detected": score >= threshold,
                "score": score,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
