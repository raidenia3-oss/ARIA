"""JARVIS interface for AURA - Module 24.

Orquestación del estado de la interfaz (anillo flotante / visores),
procesamiento de voz y sincronización de memoria persistente estilo vault.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class VoiceSession:
    session_id: str
    started_at: str
    active: bool = True
    transcript: str = ""
    turns: List[Dict[str, Any]] = field(default_factory=list)


class VoiceSessionManager:
    """Administra sesiones de voz activas y su historial de transcripción."""

    def __init__(self, max_sessions: int = 100) -> None:
        self.sessions: Dict[str, VoiceSession] = {}
        self.max_sessions = max_sessions

    def create_session(self) -> Dict[str, Any]:
        session_id = f"vs-{int(time.time() * 1000000)}"
        session = VoiceSession(session_id=session_id, started_at=datetime.utcnow().isoformat() + "Z")
        self.sessions[session_id] = session
        if len(self.sessions) > self.max_sessions:
            oldest = min(self.sessions.values(), key=lambda s: s.started_at)
            del self.sessions[oldest.session_id]
        return {"session_id": session_id, "started_at": session.started_at, "active": True}

    def end_session(self, session_id: str) -> Dict[str, Any]:
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "session_not_found", "session_id": session_id}
        session.active = False
        return {
            "session_id": session_id,
            "active": False,
            "ended_at": datetime.utcnow().isoformat() + "Z",
            "turn_count": len(session.turns),
        }

    def add_transcript(self, session_id: str, text: str, direction: str = "user") -> Dict[str, Any]:
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "session_not_found", "session_id": session_id}
        session.transcript += f"[{direction}] {text}\n"
        session.turns.append({
            "direction": direction,
            "text": text,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })
        return {"session_id": session_id, "turn_count": len(session.turns), "latest": text}

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        session = self.sessions.get(session_id)
        if not session:
            return None
        return {
            "session_id": session.session_id,
            "started_at": session.started_at,
            "active": session.active,
            "turn_count": len(session.turns),
            "transcript": session.transcript,
            "turns": session.turns,
        }


class VisualizerState:
    """Gestiona el estado del visualizador flotante (anillo JARVIS)."""

    MODES: List[str] = ["idle", "listening", "processing", "responding", "spatial"]

    def __init__(self) -> None:
        self.mode: str = "idle"
        self.position: Dict[str, float] = {"x": 0.0, "y": 0.0, "z": 0.0}
        self.scale: float = 1.0
        self.opacity: float = 1.0
        self.hue: int = 210
        self.active_widgets: List[str] = []
        self.last_updated: str = datetime.utcnow().isoformat() + "Z"

    def set_mode(self, mode: str) -> Dict[str, Any]:
        if mode not in self.MODES:
            return {"error": "invalid_mode", "available_modes": self.MODES}
        self.mode = mode
        self.last_updated = datetime.utcnow().isoformat() + "Z"
        return {"mode": self.mode, "last_updated": self.last_updated}

    def update(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        for key in ("mode", "position", "scale", "opacity", "hue", "active_widgets"):
            if key in payload:
                setattr(self, key, payload[key])
        self.last_updated = datetime.utcnow().isoformat() + "Z"
        return self.get_state()

    def get_state(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "position": self.position,
            "scale": self.scale,
            "opacity": self.opacity,
            "hue": self.hue,
            "active_widgets": self.active_widgets,
            "last_updated": self.last_updated,
        }


class MemoryVaultBridge:
    """Puente de memoria persistente estilo vault."""

    def __init__(self) -> None:
        self._vault: Dict[str, Any] = {}
        self._sync_log: List[Dict[str, Any]] = []

    def store(self, key: str, value: Any) -> str:
        self._vault[key] = value
        return key

    def retrieve(self, key: str) -> Optional[Any]:
        return self._vault.get(key)

    def delete(self, key: str) -> bool:
        if key in self._vault:
            del self._vault[key]
            return True
        return False

    def keys(self) -> List[str]:
        return list(self._vault.keys())

    def sync(self) -> Dict[str, Any]:
        entry: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "vault_size": len(self._vault),
            "keys": list(self._vault.keys()),
        }
        self._sync_log.append(entry)
        if len(self._sync_log) > 500:
            self._sync_log = self._sync_log[-500:]
        return {
            "status": "synced",
            "timestamp": entry["timestamp"],
            "keys_count": len(self._vault),
            "history": self._sync_log[-10:],
        }


class JarvisCore:
    """Núcleo JARVIS: orquesta visualizador, voz y memoria."""

    def __init__(self) -> None:
        self.voice_manager = VoiceSessionManager()
        self.visualizer = VisualizerState()
        self.memory = MemoryVaultBridge()
        self.event_log: List[Dict[str, Any]] = []
        self._max_log = 1000
        self._initialized = False

    def initialize(self) -> Dict[str, Any]:
        self._initialized = True
        return {
            "status": "initialized",
            "jarvis_version": "1.0.0",
            "modes": self.visualizer.MODES,
            "initialized_at": datetime.utcnow().isoformat() + "Z",
        }

    def get_state(self) -> Dict[str, Any]:
        active_sessions = sum(1 for s in self.voice_manager.sessions.values() if s.active)
        return {
            "status": "active" if self._initialized else "uninitialized",
            "jarvis_version": "1.0.0",
            "visualizer": self.visualizer.get_state(),
            "voice_sessions": {
                "total": len(self.voice_manager.sessions),
                "active": active_sessions,
            },
            "memory": {
                "entries": len(self.memory.keys()),
                "synced": self._sync_log[-1]["timestamp"] if self.memory._sync_log else None,
            },
            "event_count": len(self.event_log),
        }

    def update_state(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}

        if "mode" in payload:
            result["visualizer"] = self.visualizer.set_mode(payload["mode"])

        if "position" in payload:
            self.visualizer.update({"position": payload["position"]})

        voice = payload.get("voice_session")
        if voice:
            result["voice_session"] = self._handle_voice_session(voice)

        mem = payload.get("memory")
        if mem:
            result["memory"] = self._handle_memory(mem)

        extra = {k: v for k, v in payload.items() if k not in ("mode", "position", "voice_session", "memory")}
        if extra:
            self.visualizer.update(extra)

        self.visualizer.last_updated = datetime.utcnow().isoformat() + "Z"
        return result

    def _handle_voice_session(self, voice: Dict[str, Any]) -> Dict[str, Any]:
        action = voice.get("action", "create")
        if action == "create":
            return self.voice_manager.create_session()
        if action == "end":
            return self.voice_manager.end_session(voice.get("session_id", ""))
        if action == "transcript":
            return self.voice_manager.add_transcript(
                voice.get("session_id", ""),
                voice.get("text", ""),
                voice.get("direction", "user"),
            )
        return {"error": "unknown_voice_action", "action": action}

    def _handle_memory(self, mem: Dict[str, Any]) -> Dict[str, Any]:
        action = mem.get("action", "")
        if action == "store":
            key = self.memory.store(mem.get("key", ""), mem.get("value"))
            return {"stored": True, "key": key}
        if action == "retrieve":
            return {"key": mem.get("key", ""), "value": self.memory.retrieve(mem.get("key", ""))}
        if action == "delete":
            return {"deleted": self.memory.delete(mem.get("key", ""))}
        if action == "sync":
            return self.memory.sync()
        return {"error": "unknown_memory_action", "action": action}

    def process_voice(self, session_id: str, text: str) -> Dict[str, Any]:
        if session_id not in self.voice_manager.sessions:
            created = self.voice_manager.create_session()
            session_id = created["session_id"]
        self.voice_manager.add_transcript(session_id, text, "user")
        self.memory.store(f"session:{session_id}:last", text)
        entry: Dict[str, Any] = {
            "session_id": session_id,
            "text": text,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        self.event_log.append(entry)
        if len(self.event_log) > self._max_log:
            self.event_log = self.event_log[-self._max_log :]
        return {
            "session_id": session_id,
            "echo": text,
            "processed": True,
            "visualizer_mode": self.visualizer.mode,
        }
