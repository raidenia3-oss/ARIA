#!/usr/bin/env python3
"""
voice_engine.py - Motor de Voz Local (STT/TTS)
Integra Whisper (STT) y Kokoro TTS para ejecución 100% local.
"""

import os
import asyncio
import logging
import tempfile
import subprocess
from datetime import datetime
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class VoiceEngine:
    """Motor de voz local con Whisper (STT) y Kokoro (TTS)."""

    def __init__(self):
        self.whisper_bin = os.getenv("WHISPER_BIN", "whisper")
        self.kokoro_bin = os.getenv("KOKORO_BIN", "kokoro")
        self.default_voice = os.getenv("KOKORO_VOICE", "af_heart")
        self.enabled = os.getenv("VOICE_ENABLED", "true").lower() == "true"
        self._last_stt: Optional[str] = None
        self._last_tts_path: Optional[str] = None

    async def transcribe(self, audio_path: str, language: str = "es") -> str:
        """
        STT: Transcribir audio a texto usando Whisper local.
        """
        if not self.enabled:
            return ""
        try:
            proc = await asyncio.create_subprocess_exec(
                self.whisper_bin,
                audio_path,
                "--model",
                "base",
                "--language",
                language,
                "--output_format",
                "txt",
                "--output_dir",
                tempfile.gettempdir(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            if proc.returncode != 0:
                logger.error(f"[Voice] Whisper error: {stderr.decode()[:200]}")
                return ""
            text = stdout.decode().strip()
            self._last_stt = text
            logger.info(f"[Voice] STT OK: {text[:100]}")
            return text
        except Exception as e:
            logger.error(f"[Voice] Error STT: {e}")
            return ""

    async def synthesize(self, text: str, voice: Optional[str] = None) -> str:
        """
        TTS: Sintetizar voz con Kokoro TTS. Devuelve ruta del WAV generado.
        """
        if not self.enabled:
            return ""
        voice = voice or self.default_voice
        try:
            out_path = os.path.join(
                tempfile.gettempdir(), f"aura_tts_{int(datetime.now().timestamp())}.wav"
            )
            proc = await asyncio.create_subprocess_exec(
                self.kokoro_bin,
                "--text",
                text,
                "--voice",
                voice,
                "--output",
                out_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            if proc.returncode != 0:
                logger.error(f"[Voice] Kokoro error: {stderr.decode()[:200]}")
                return ""
            self._last_tts_path = out_path
            logger.info(f"[Voice] TTS OK: {out_path}")
            return out_path
        except Exception as e:
            logger.error(f"[Voice] Error TTS: {e}")
            return ""

    async def speak(self, text: str, voice: Optional[str] = None) -> bool:
        """
        TTS + reproducción directa por altavoz (Windows: PowerShell MediaPlayer).
        """
        path = await self.synthesize(text, voice)
        if not path:
            return False
        try:
            if os.name == "nt":
                subprocess.Popen(
                    [
                        "powershell",
                        "-Command",
                        f"(New-Object Media.SoundPlayer '{path}').PlaySync()",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                subprocess.Popen(["aplay" if os.name == "posix" else "afplay", path])
            return True
        except Exception as e:
            logger.error(f"[Voice] Error reproduciendo: {e}")
            return False

    def get_last_stt(self) -> Optional[str]:
        return self._last_stt

    def get_last_tts_path(self) -> Optional[str]:
        return self._last_tts_path


# Instancia global
_voice = VoiceEngine()


def get_voice_engine() -> VoiceEngine:
    return _voice
