# -*- coding: utf-8 -*-
"""
AURA OS - Chunk 2: Parallel Executor.

Ejecuta los pasos asignados por el Orchestrator, con retry,
progreso y emision de eventos al EventBus.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from backend.core.event_bus import CoreEvent, EventBus, EventType, get_event_bus

logger = __import__("logging").getLogger("AURA.ParallelExecutor")


class ParallelExecutor:
    """Ejecuta multiples pasos con retry, progreso y eventos."""

    def __init__(self, max_concurrent: int = 4, max_retries: int = 3,
                 retry_delay: float = 1.0, bus: Optional[EventBus] = None) -> None:
        self._max_concurrent = max(1, max_concurrent)
        self._max_retries = max(0, max_retries)
        self._retry_delay = retry_delay
        self._bus = bus or get_event_bus()

    # ------------------------------------------------------------------
    def _resolve_agent(self, agent_name: str, session_id: str = "") -> Any:
        """Resuelve un agente por nombre usando importacion lazy."""
        if agent_name == "rag_agent":
            from backend.agent.rag_agent import RAGAgent
            return RAGAgent(session_id=session_id)
        if agent_name == "writer_agent":
            from backend.agent.writer_agent import WriterAgent
            return WriterAgent(session_id=session_id)
        if agent_name == "executor_agent":
            from backend.agent.executor_agent import ExecutorAgent
            return ExecutorAgent(session_id=session_id)
        from backend.agent.swarm_base import BaseAgent
        return BaseAgent(name=agent_name, session_id=session_id)

    # ------------------------------------------------------------------
    def run_step(self, step: Dict[str, Any], session_id: str = "") -> Dict[str, Any]:
        """Ejecuta un paso individual (bloqueante, con retry)."""
        step_id = step["step_id"]
        agent_name = step["agent"]
        params = step.get("params", {})
        description = step.get("description", "")

        attempt = 0
        last_error = ""
        while attempt <= self._max_retries:
            try:
                self._bus.emit(CoreEvent(
                    type=EventType.AGENT_START,
                    data={"step_id": step_id, "agent": agent_name,
                          "attempt": attempt, "description": description,
                          "session_id": session_id},
                    agent=agent_name, status="starting",
                ))
                agent = self._resolve_agent(agent_name, session_id)
                result = agent.execute(description, **params)
                self._bus.emit(CoreEvent(
                    type=EventType.AGENT_END,
                    data={"step_id": step_id, "agent": agent_name,
                          "status": "completed", "session_id": session_id},
                    agent=agent_name, status="completed",
                ))
                return {"step_id": step_id, "status": "completed",
                        "result": result, "attempts": attempt + 1}
            except Exception as exc:
                attempt += 1
                last_error = str(exc)
                logger.warning("Step %s fallo (intento %d): %s", step_id, attempt, exc)
                self._bus.emit(CoreEvent(
                    type=EventType.ERROR,
                    data={"step_id": step_id, "agent": agent_name,
                          "error": last_error, "attempt": attempt,
                          "session_id": session_id},
                    agent=agent_name, status="retry",
                ))
                if attempt <= self._max_retries:
                    time.sleep(self._retry_delay)

        # Agotar reintentos
        self._bus.emit(CoreEvent(
            type=EventType.ERROR,
            data={"step_id": step_id, "agent": agent_name,
                  "error": last_error, "status": "failed",
                  "session_id": session_id},
            agent=agent_name, status="failed",
                ))
        return {"step_id": step_id, "status": "failed",
                "error": last_error, "attempts": attempt}

    # ------------------------------------------------------------------
    def run(self, assignment: Dict[str, Any], session_id: str = "",
            orchestrator=None) -> Dict[str, Any]:
        """Ejecuta todos los pasos de un assignment."""
        steps: List[Dict[str, Any]] = assignment.get("steps", [])
        total = len(steps)
        results: Dict[str, Dict[str, Any]] = {}

        if total == 0:
            return {"session_id": session_id, "results": [], "progress": 100.0,
                    "status": "completed"}

        completed = 0
        overall_start = time.time()
        self._emit_progress(session_id, completed, total, "running")

        # Ejecucion secuencial (deps se respetan)
        for step in steps:
            step_id = step["step_id"]
            if orchestrator:
                orchestrator.mark_started(step_id)
            result = self.run_step(step, session_id)
            results[step_id] = result
            if orchestrator:
                if result["status"] == "completed":
                    orchestrator.mark_completed(step_id, result)
                else:
                    orchestrator.mark_failed(step_id, result.get("error", ""))
            completed += 1
            self._emit_progress(session_id, completed, total, "running")

        # Determinar estado final
        status = "completed"
        if any(r.get("status") == "failed" for r in results.values()):
            status = "failed"
        self._emit_progress(session_id, completed, total, status)
        self._emit_complete(session_id, results, status, time.time() - overall_start)

        return {
            "session_id": session_id, "results": list(results.values()),
            "progress": 100.0, "status": status, "total_steps": total,
            "completed_steps": completed, "failed_steps": total - completed,
            "latency_ms": round((time.time() - overall_start) * 1000, 2),
        }

    # ------------------------------------------------------------------
    def _emit_progress(self, session_id: str, completed: int, total: int, status: str) -> None:
        progress = round((completed / max(1, total)) * 100, 1)
        self._bus.emit(CoreEvent(
            type=EventType.PROGRESS,
            data={"session_id": session_id, "completed": completed,
                  "total": total, "progress": progress, "status": status},
            agent="parallel_executor", status=status,
        ))
        logger.debug("Executor progreso: %d/%d (%s%%) %s", completed, total, progress, status)

    def _emit_complete(self, session_id: str, results: Dict[str, Any],
                       status: str, duration: float) -> None:
        self._bus.emit(CoreEvent(
            type=EventType.COMPLETE,
            data={"session_id": session_id, "status": status,
                  "results": {k: v["status"] for k, v in results.items()},
                  "duration_s": round(duration, 3)},
            agent="parallel_executor", status=status,
        ))
        logger.info("Executor completado: %s en %.3fs", status, duration)

    # ------------------------------------------------------------------
    def shutdown(self) -> None:
        """Libera recursos (placeholder para futuro ThreadPoolExecutor)."""
        logger.info("ParallelExecutor shutdown")


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------
_executor_inst: Optional["ParallelExecutor"] = None


def get_parallel_executor() -> ParallelExecutor:
    """Retorna el singleton del ParallelExecutor."""
    global _executor_inst
    if _executor_inst is None:
        _executor_inst = ParallelExecutor()
    return _executor_inst


def reset_parallel_executor() -> None:
    """Reinicia el singleton del ParallelExecutor."""
    global _executor_inst
    if _executor_inst is not None:
        _executor_inst.shutdown()
    _executor_inst = None
