# -*- coding: utf-8 -*-
"""AURA EventBus - BLOQUE 105.

Pub/sub event bus con tipado estricto.
Soporta el wildcard "__all__" que recibe TODOS los eventos.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger("AURA.EventBus")


class EventType(str, Enum):
    INPUT = "input"
    AGENT_START = "agent_start"
    AGENT_END = "agent_end"
    DECISION = "decision"
    ACTION = "action"
    RESULT = "result"
    ERROR = "error"
    COMPLETE = "complete"
    THOUGHT = "thought"
    PROGRESS = "progress"


@dataclass
class CoreEvent:
    type: str
    data: Dict[str, Any] = field(default_factory=dict)
    agent: str = "system"
    status: str = "running"
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "data": self.data,
            "agent": self.agent,
            "status": self.status,
            "timestamp": self.timestamp,
            "event_id": self.event_id,
        }


class EventBus:
    """Pub/sub central. Thread-safe, async-first."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable[[CoreEvent], None]]] = {}
        self._async_subscribers: Dict[str,
            List[Callable[[CoreEvent], Awaitable[None]]]] = {}
        self._history: List[CoreEvent] = []
        self._max_history: int = 500
        self._lock = asyncio.Lock()

    def subscribe(self, event_type: str,
                  cb: Callable[[CoreEvent], None]) -> None:
        """Suscribirse a un tipo de evento."""
        self._subscribers.setdefault(event_type, []).append(cb)

    def subscribe_async(self, event_type: str,
                        cb: Callable[[CoreEvent], Awaitable[None]]) -> None:
        """Suscribirse async."""
        self._async_subscribers.setdefault(event_type, []).append(cb)

    def unsubscribe(self, event_type: str, cb: Callable) -> None:
        for store in (self._subscribers, self._async_subscribers):
            for key in (event_type, "__all__"):
                if key in store and cb in store[key]:
                    store[key].remove(cb)

    def emit(self, event: CoreEvent) -> None:
        """Emitir a todos los suscriptores sincronicos + async."""
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        sync_cbs = (self._subscribers.get("__all__", []) +
                     self._subscribers.get(event.type, []))
        for cb in sync_cbs:
            try:
                cb(event)
            except Exception as exc:
                logger.warning("Sync subscriber %s failed: %s", cb, exc)

        async_cbs = (self._async_subscribers.get("__all__", []) +
                     self._async_subscribers.get(event.type, []))
        for cb in async_cbs:
            try:
                asyncio.ensure_future(cb(event))
            except RuntimeError:
                logger.debug("No loop for async subscriber %s", cb)
            except Exception as exc:
                logger.warning("Async subscriber %s failed: %s", cb, exc)

    async def emit_async(self, event: CoreEvent) -> None:
        """Emitir y esperar a todos los suscriptores async."""
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        tasks = []
        sync_cbs = (self._subscribers.get("__all__", []) +
                     self._subscribers.get(event.type, []))
        for cb in sync_cbs:
            try:
                cb(event)
            except Exception:
                pass
        async_cbs = (self._async_subscribers.get("__all__", []) +
                     self._async_subscribers.get(event.type, []))
        for cb in async_cbs:
            try:
                tasks.append(cb(event))
            except Exception:
                pass
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def emit_simple(self, type_: str, data: Dict[str, Any],
                    agent: str = "system", status: str = "running") -> CoreEvent:
        evt = CoreEvent(type=type_, data=data, agent=agent, status=status)
        self.emit(evt)
        return evt

    def recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._history[-limit:]]

    def clear(self) -> None:
        self._history.clear()

    def start(self) -> None:
        """No-op (compat). EventBus es push-driven, no necesita hilo propio."""
        pass


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------
_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus


def reset_event_bus() -> None:
    global _bus
    if _bus is not None:
        _bus.clear()
    _bus = None