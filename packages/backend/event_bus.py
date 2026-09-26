"""Event-driven architecture for AURA - Module 23.

Provides an asynchronous event bus for publishing and subscribing to
internal system events.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional


@dataclass
class EventPayload:
    """Contenedor de datos para un evento interno."""

    event_type: str
    data: Dict[str, Any]
    event_id: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class EventSubscriber:
    """Suscriptor a eventos de un tipo específico."""

    def __init__(
        self,
        name: str,
        handler: Callable[[EventPayload], Awaitable[Any]],
        event_types: Optional[List[str]] = None,
    ) -> None:
        self.name = name
        self.handler = handler
        self.event_types: List[str] = event_types or ["*"]

    def matches(self, event_type: str) -> bool:
        return "*" in self.event_types or event_type in self.event_types

    async def handle(self, event: EventPayload) -> Any:
        return await self.handler(event)


class EventDispatcher:
    """Despide eventos a los suscriptores registrados de forma concurrente."""

    def __init__(self) -> None:
        self.subscribers: List[EventSubscriber] = []

    def add_subscriber(self, subscriber: EventSubscriber) -> None:
        self.subscribers.append(subscriber)

    def remove_subscriber(self, name: str) -> bool:
        original = len(self.subscribers)
        self.subscribers = [s for s in self.subscribers if s.name != name]
        return len(self.subscribers) < original

    async def dispatch(self, event: EventPayload) -> List[Dict[str, Any]]:
        tasks = [
            asyncio.create_task(sub.handle(event))
            for sub in self.subscribers
            if sub.matches(event.event_type)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        names = [s.name for s in self.subscribers if s.matches(event.event_type)]
        return [
            {"subscriber": names[i], "result": _safe_result(results[i])}
            for i in range(len(names))
        ]


def _safe_result(result: Any) -> Any:
    if isinstance(result, Exception):
        return {"error": str(result), "type": type(result).__name__}
    return result


class EventBus:
    """Bus de eventos asíncrono para publicar y suscribir eventos internos."""

    def __init__(self, max_history: int = 500) -> None:
        self.dispatcher = EventDispatcher()
        self.history: List[Dict[str, Any]] = []
        self.max_history = max_history

    def subscribe(self, subscriber: EventSubscriber) -> None:
        self.dispatcher.add_subscriber(subscriber)

    def unsubscribe(self, name: str) -> bool:
        return self.dispatcher.remove_subscriber(name)

    @property
    def subscribers(self) -> List[EventSubscriber]:
        return self.dispatcher.subscribers

    async def publish(
        self,
        event_type: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        event = EventPayload(
            event_type=event_type,
            data=data or {},
            event_id=f"evt-{int(time.time() * 1000000)}",
        )
        results = await self.dispatcher.dispatch(event)
        record: Dict[str, Any] = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "data": event.data,
            "timestamp": event.timestamp,
            "dispatch_results": results,
        }
        self.history.append(record)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history :]
        return record

    def recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.history[-limit:]
