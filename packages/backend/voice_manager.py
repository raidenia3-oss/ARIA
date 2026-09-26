"""Voice manager for AURA speech-to-text, text-to-speech and voice commands."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class VoiceProvider(str, Enum):
    STT = "stt"
    TTS = "tts"
    COMMAND = "command"


@dataclass
class VoiceRequest:
    provider: VoiceProvider
    text: Optional[str] = None
    audio_format: Optional[str] = None
    language: str = "es"
    voice: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class VoiceManager:
    """Gestor central de voz."""

    def __init__(self) -> None:
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.history: List[Dict[str, Any]] = []

    def transcribe(self, request: VoiceRequest) -> Dict[str, Any]:
        session_id = f"stt-{int(time.time() * 1000)}"
        result = {
            "session_id": session_id,
            "provider": VoiceProvider.STT.value,
            "status": "ok",
            "language": request.language,
            "text": request.text or "Texto transcrito simulado desde audio.",
            "confidence": 0.92,
            "created_at": time.time(),
        }
        self._store(session_id, result)
        return result

    def synthesize(self, request: VoiceRequest) -> Dict[str, Any]:
        session_id = f"tts-{int(time.time() * 1000)}"
        result = {
            "session_id": session_id,
            "provider": VoiceProvider.TTS.value,
            "status": "ok",
            "language": request.language,
            "voice": request.voice or "default",
            "text": request.text or "Respuesta de voz generada por AURA.",
            "audio_format": request.audio_format or "mp3",
            "created_at": time.time(),
        }
        self._store(session_id, result)
        return result

    def execute_command(self, request: VoiceRequest) -> Dict[str, Any]:
        session_id = f"cmd-{int(time.time() * 1000)}"
        command = (request.text or "").strip().lower()
        recognized = bool(command)
        result = {
            "session_id": session_id,
            "provider": VoiceProvider.COMMAND.value,
            "status": "ok",
            "command": command,
            "recognized": recognized,
            "action": "none",
            "created_at": time.time(),
        }
        if recognized:
            result["action"] = self._match_command(command)
        self._store(session_id, result)
        return result

    def history_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.history[-limit:]

    def _store(self, session_id: str, result: Dict[str, Any]) -> None:
        self.sessions[session_id] = result
        self.history.append(result)
        if len(self.history) > 200:
            self.history = self.history[-200:]

    def _match_command(self, command: str) -> str:
        if "estado" in command:
            return "monitoring_status"
        if "alerta" in command:
            return "list_alerts"
        if "buscar" in command:
            return "rag_query"
        if "documento" in command or "ingestar" in command:
            return "rag_ingest"
        if "resumen" in command:
            return "summary"
        return "unknown"
