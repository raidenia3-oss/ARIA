# -*- coding: utf-8 -*-
"""AURA OS — Chunk 1: Receiver Hub.

Punto único de entrada del núcleo. Unifica cualquier canal
(chat, voz, gesto, comando, archivo, sistema) en un `UnifiedInput`
y lo publica en el EventBus como evento `input`.

Flujo:
  canal → ReceiverHub.receive() → UnifiedInput → EventBus(INPUT)
"""
from __future__ import annotations

import logging
import time
import uuid
from collections import deque
from typing import Any, Deque, Dict, List, Optional

from backend.core.event_bus import CoreEvent, EventType, get_event_bus
from backend.core.models import InputType, UnifiedInput

logger = logging.getLogger("AURA.ReceiverHub")

DEDUP_WINDOW_S = 2.0
HISTORY_SIZE = 200


class ReceiverHub:
    """Recepción y normalización de inputs. Thread-safe a nivel de
    estructuras (deque + dict) y con deduplicación por ventana temporal."""

    def __init__(self, dedup_window: float = DEDUP_WINDOW_S, history_size: int = HISTORY_SIZE) -> None:
        self._bus = get_event_bus()
        self._dedup_window = max(0.0, dedup_window)
        self._history: Deque[UnifiedInput] = deque(maxlen=max(1, history_size))
        self._dedup: Dict[str, float] = {}
        self._counters: Dict[str, int] = {}
        self._sessions: Dict[str, int] = {}

    def receive(
        self,
        input_type: str,
        content: str,
        source: str = "user",
        session_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CoreEvent:
        """Normaliza la entrada y la publica en el EventBus.
        Devuelve el CoreEvent emitido (type=INPUT)."""
        try:
            itype = InputType(input_type)
        except ValueError:
            logger.debug("input_type '%s' desconocido; usando chat", input_type)
            itype = InputType.CHAT

        meta: Dict[str, Any] = dict(metadata or {})
        input_id = uuid.uuid4().hex[:12]
        meta["input_id"] = input_id

        inp = UnifiedInput(
            type=itype,
            content=content or "",
            source=source or "user",
            session_id=session_id or "",
            metadata=meta,
            input_id=input_id,
        )

        key = self._dedup_key(inp)
        if self._is_duplicate(key):
            meta["duplicate"] = True
            logger.debug("ReceiverHub: entrada duplicada ignorada (%s)", key[:40])
        else:
            meta["duplicate"] = False

        self._history.append(inp)
        self._counters[itype.value] = self._counters.get(itype.value, 0) + 1
        if session_id:
            self._sessions[session_id] = self._sessions.get(session_id, 0) + 1

        evt = CoreEvent(
            type=EventType.INPUT,
            data={
                "input_id": input_id,
                "type": itype.value,
                "content": inp.content,
                "source": inp.source,
                "session_id": inp.session_id,
                "metadata": meta,
                "duplicate": meta["duplicate"],
            },
            agent="receiver_hub",
            status="received",
        )
        self._bus.emit(evt)

        logger.info("input → receiver_hub [%s] %s", itype.value, (inp.content or "")[:80])
        return evt

    async def receive_async(
        self,
        input_type: str,
        content: str,
        source: str = "user",
        session_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CoreEvent:
        """Variante async: espera a los suscriptores asíncronos del bus."""
        evt = self.receive(input_type, content, source, session_id, metadata)
        await self._bus.emit_async(evt)
        return evt

    def receive_chat(self, message: str, session_id: str = "",
                     metadata: Optional[Dict[str, Any]] = None) -> CoreEvent:
        return self.receive("chat", message, "user", session_id, metadata)

    def receive_voice(self, text: str, session_id: str = "",
                      metadata: Optional[Dict[str, Any]] = None) -> CoreEvent:
        return self.receive("voice", text, "voice_pipeline", session_id, metadata)

    def receive_gesture(self, gesture: str, session_id: str = "",
                        metadata: Optional[Dict[str, Any]] = None) -> CoreEvent:
        return self.receive("gesture", gesture, "gesture_control", session_id, metadata)

    def receive_command(self, command: str, session_id: str = "",
                        metadata: Optional[Dict[str, Any]] = None) -> CoreEvent:
        return self.receive("command", command, "command_parser", session_id, metadata)

    def receive_file(self, path: str, session_id: str = "",
                     metadata: Optional[Dict[str, Any]] = None) -> CoreEvent:
        return self.receive("file", path, "file_watcher", session_id, metadata)

    def receive_system(self, message: str, session_id: str = "",
                       metadata: Optional[Dict[str, Any]] = None) -> CoreEvent:
        return self.receive("system", message, "system_monitor", session_id, metadata)

    def _dedup_key(self, inp: UnifiedInput) -> str:
        return f"{inp.type.value}|{inp.source}|{inp.content.strip().lower()[:160]}"

    def _is_duplicate(self, key: str) -> bool:
        now = time.time()
        if self._dedup_window <= 0:
            return False
        expired = [k for k, ts in self._dedup.items() if now - ts > self._dedup_window]
        for k in expired:
            self._dedup.pop(k, None)
        last = self._dedup.get(key)
        self._dedup[key] = now
        return last is not None and (now - last) <= self._dedup_window

    def stats(self) -> Dict[str, Any]:
        return {
            "total": sum(self._counters.values()),
            "by_type": dict(self._counters),
            "sessions": len(self._sessions),
            "history_size": len(self._history),
            "dedup_window_s": self._dedup_window,
        }

    def recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        items = list(self._history)[-max(1, limit):]
        return [
            {
                "input_id": i.metadata.get("input_id", ""),
                "type": i.type.value,
                "content": i.content[:200],
                "source": i.source,
                "session_id": i.session_id,
                "timestamp": i.timestamp,
            }
            for i in items
        ]

    def reset(self) -> None:
        self._history.clear()
        self._dedup.clear()
        self._counters.clear()
        self._sessions.clear()


_hub: Optional[ReceiverHub] = None


def get_receiver_hub() -> ReceiverHub:
    global _hub
    if _hub is None:
        _hub = ReceiverHub()
    return _hub


def reset_receiver_hub() -> None:
    global _hub
    if _hub is not None:
        _hub.reset()
    _hub = None