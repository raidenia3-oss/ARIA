# -*- coding: utf-8 -*-
"""
AURA OS - Chunk 2: Base Agent (swarm base class).

Define BaseAgent, la clase base para todos los agentes del swarm,
y AgentRegistry, el registro central de agentes.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.core.event_bus import CoreEvent, EventBus, EventType, get_event_bus

logger = logging.getLogger("AURA.Agent")


class BaseAgent:
    """
    Clase base para todos los agentes.

    Flujo típico:
      agent = SomeAgent(session_id="abc")
      result = agent.execute(" descripcion de la tarea ", key="valor")
    Cada agente emite eventos THOUGHT/PROGRESS al EventBus.
    """

    def __init__(self, name: str = "base_agent", session_id: str = "",
                 bus: Optional[EventBus] = None) -> None:
        self.name = name
        self.session_id = session_id
        self._bus = bus or get_event_bus()
        self._status: str = "idle"
        self._progress: float = 0.0
        self._last_result: Dict[str, Any] = {}
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None

    # ------------------------------------------------------------------
    # API principal
    # ------------------------------------------------------------------
    def execute(self, task: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Ejecuta una tarea: emitir AGENT_START, correr lógica, emitir AGENT_END.

        Subclases implementan _do_execute().
        """
        import time
        self._start_time = time.time()
        self._status = "running"
        self._last_result = {}
        self.report_progress(0.0, "iniciando agente")

        self._bus.emit(CoreEvent(
            type=EventType.AGENT_START,
            data={"agent": self.name, "task": task, **kwargs},
            agent=self.name,
            status="starting",
        ))

        try:
            result = self._do_execute(task, **kwargs)
            self._status = "completed"
            self._last_result = result
            self.report_progress(100.0, "completado")
        except Exception as exc:
            self._status = "failed"
            self._last_result = {"error": str(exc), "task": task}
            self._bus.emit(CoreEvent(
                type=EventType.ERROR,
                data={"agent": self.name, "error": str(exc), "task": task,
                      "session_id": self.session_id},
                agent=self.name, status="failed",
            ))
            raise

        self._end_time = time.time()
        self._bus.emit(CoreEvent(
            type=EventType.AGENT_END,
            data={
                "agent": self.name, "task": task,
                "status": self._status,
                "duration_ms": round((self._end_time - (self._start_time or 0)) * 1000, 2),
                "result_keys": list(result.keys()) if isinstance(result, dict) else [],
                **kwargs,
            },
            agent=self.name, status=self._status,
        ))
        return result

    def _do_execute(self, task: str, **kwargs: Any) -> Dict[str, Any]:
        """Lógia de ejecucion. Subclasses deben overridear."""
        return {
            "agent": self.name,
            "task": task,
            "result": f"Tarea procesada por {self.name}",
            "kwargs": kwargs,
        }

    # ------------------------------------------------------------------
    # Progreso y pensamiento
    # ------------------------------------------------------------------
    def report_progress(self, progress: float, message: str = "") -> None:
        """Emite evento de progreso al EventBus."""
        self._progress = max(0.0, min(100.0, float(progress)))
        self._bus.emit(CoreEvent(
            type=EventType.PROGRESS,
            data={"agent": self.name, "progress": self._progress,
                  "message": message, "session_id": self.session_id},
            agent=self.name, status="running",
        ))

    def emit_thought(self, stage: str, detail: Dict[str, Any]) -> None:
        """Emite un evento de tipo pensamiento (THOUGHT)."""
        self._bus.emit(CoreEvent(
            type=EventType.THOUGHT,
            data={"agent": self.name, "stage": stage, "session_id": self.session_id, **detail},
            agent=self.name, status="thinking",
        ))

    # ------------------------------------------------------------------
    # Estado
    # ------------------------------------------------------------------
    def get_status(self) -> Dict[str, Any]:
        """Retorna el estado actual del agente."""
        return {
            "name": self.name,
            "status": self._status,
            "progress": self._progress,
            "session_id": self.session_id,
            "last_result": self._last_result,
        }


class AgentRegistry:
    """Registro central de agentes disponibles."""

    _registry: Dict[str, type] = {}

    @classmethod
    def register(cls, name: str, agent_cls: type) -> None:
        cls._registry[name] = agent_cls
        logger.info("Agente registrado: %s -> %s", name, agent_cls.__name__)

    @classmethod
    def get(cls, name: str) -> type:
        return cls._registry.get(name, BaseAgent)

    @classmethod
    def list_agents(cls) -> List[str]:
        return list(cls._registry.keys())

    @classmethod
    def create(cls, name: str, session_id: str = "", **kwargs) -> BaseAgent:
        agent_cls = cls.get(name)
        return agent_cls(name=name, session_id=session_id, **kwargs)

