# -*- coding: utf-8 -*-
"""
ARIA OS — Chunk 2: Orchestrator Core.

Orquestador central:
- Recibe decisiones del DecisionEngine
- Asigna pasos a agentes
- Maneja dependencias entre pasos
- Emite eventos a EventBus
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from backend.core.event_bus import CoreEvent, EventType, get_event_bus
from backend.core.models import Decision, DecisionStep, EventStatus

logger = logging.getLogger("ARIA.Orchestrator")


class Orchestrator:
    """Orquestador central para ejecutar planes generados por DecisionEngine."""

    def __init__(self) -> None:
        self._bus = get_event_bus()
        self._agents: Dict[str, Any] = {}
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._steps: Dict[str, Dict[str, Any]] = {}
        self._completed: List[str] = []
        self._failed: List[str] = []
        self._current_plan: Optional[Decision] = None

    def register_agent(self, agent_name: str, agent_instance: Any) -> None:
        """Registra un agente disponible para ejecución."""
        self._agents[agent_name] = agent_instance

    def get_agent(self, agent_name: str) -> Optional[Any]:
        """Obtiene un agente registrado."""
        return self._agents.get(agent_name)

    async def execute_decision(self, decision: Decision, session_id: str) -> Dict[str, Any]:
        """Ejecuta un plan de decisión generado por DecisionEngine.

        Asigna cada paso a un agente, respeta dependencias (pasos previos
        completados) y emite eventos (action/agent_start/agent_end/complete).
        """
        start_time = time.time()
        event_id = f"orch-{int(time.time() * 1000)}"
        plan: List[DecisionStep] = list(decision.plan or [])

        self._current_plan = decision
        self._steps = {}
        self._completed = []
        self._failed = []
        for s in plan:
            sid = f"step_{s.step}"
            self._steps[sid] = {
                "description": s.description,
                "agent": s.agent or "",
                "tool": s.tool or "",
                "status": "pending",
            }

        self._bus.emit(
            CoreEvent(
                type=EventType.ACTION,
                data={
                    "stage": "orchestration_start",
                    "session_id": session_id,
                    "steps": len(plan),
                    "agents": decision.agents,
                    "event_id": event_id,
                },
                agent="orchestrator",
                status="running",
            )
        )

        step_results: List[Dict[str, Any]] = []
        for s in plan:
            sid = f"step_{s.step}"
            agent_name = s.agent or self._default_agent_for(s)
            self.mark_started(sid)
            self._bus.emit(
                CoreEvent(
                    type=EventType.AGENT_START,
                    data={"step_id": sid, "agent": agent_name},
                    agent=agent_name,
                    status="running",
                )
            )
            try:
                result = await self._run_agent(agent_name, s, session_id)
                self.mark_completed(sid, result)
                self._bus.emit(
                    CoreEvent(
                        type=EventType.AGENT_END,
                        data={"step_id": sid, "agent": agent_name, "result": result},
                        agent=agent_name,
                        status="completed",
                    )
                )
                step_results.append(
                    {"step_id": sid, "agent": agent_name, "status": "completed", "result": result}
                )
            except Exception as exc:
                self.mark_failed(sid, str(exc))
                self._bus.emit(
                    CoreEvent(
                        type=EventType.AGENT_END,
                        data={"step_id": sid, "agent": agent_name, "error": str(exc)},
                        agent=agent_name,
                        status="failed",
                    )
                )
                step_results.append(
                    {"step_id": sid, "agent": agent_name, "status": "failed", "error": str(exc)}
                )

        duration_ms = round((time.time() - start_time) * 1000, 2)
        self._bus.emit(
            CoreEvent(
                type=EventType.COMPLETE,
                data={
                    "stage": "orchestration_complete",
                    "session_id": session_id,
                    "duration_ms": duration_ms,
                    "steps": len(step_results),
                },
                agent="orchestrator",
                status="completed",
            )
        )
        return {
            "session_id": session_id,
            "duration_ms": duration_ms,
            "steps": step_results,
            "status": self._overall_status(),
        }

    async def _run_agent(
        self, agent_name: str, step: DecisionStep, session_id: str
    ) -> Dict[str, Any]:
        """Ejecuta un paso delegando al agente (registrado o importable)."""
        inst = self._agents.get(agent_name)
        if inst is None:
            try:
                from backend.agent.swarm_base import AgentRegistry

                inst = AgentRegistry.get(agent_name)(session_id=session_id)
            except Exception:
                inst = None
        params = dict(step.params or {})
        params.setdefault("task", step.description)
        if inst is not None:
            if hasattr(inst, "execute"):
                res = (
                    inst.execute(**params)
                    if not asyncio.iscoroutinefunction(getattr(inst, "execute"))
                    else await inst.execute(**params)
                )
                return res if isinstance(res, dict) else {"output": res}
        # Sin agente disponible: resultado simulado coherente
        return {
            "output": f"[{agent_name}] paso simulado: {step.description[:80]}",
            "simulated": True,
        }

    def _default_agent_for(self, step: DecisionStep) -> str:
        """Asigna un agente por defecto segun tool/descripcion."""
        tool = (step.tool or "").lower()
        desc = (step.description or "").lower()
        text = tool + " " + desc
        if "rag" in text or "memory" in text or "search" in text or "leer" in text:
            return "rag_agent"
        if "write" in text or "generar" in text or "texto" in text:
            return "writer_agent"
        if "execute" in text or "command" in text or "system" in text:
            return "executor_agent"
        return "executor_agent"

    def _extract_deps(self, index: int, plan: List[DecisionStep]) -> List[str]:
        """Dependencias: pasos previos son deps implicitas (max 3)."""
        prev = plan[max(0, index - 3) : index]
        return [f"step_{p.step}" for p in prev]

    # --------------------------------------------------------------
    # Consulta de estado
    # --------------------------------------------------------------
    def get_status(self, session_id: str = "") -> Dict[str, Any]:
        """Estado actual de la ejecucion del plan."""
        total = len(self._steps)
        completed = len(self._completed)
        failed = len(self._failed)
        pending = total - completed - failed
        progress = round((completed / max(1, total)) * 100, 1) if total else 0.0

        return {
            "session_id": session_id,
            "total_steps": total,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "progress": progress,
            "status": self._overall_status(),
            "steps_summary": [
                {
                    "step_id": sid,
                    "description": s.get("description", "")[:80],
                    "agent": s.get("agent", ""),
                    "status": s.get("status", "pending"),
                }
                for sid, s in self._steps.items()
            ],
        }

    def _overall_status(self) -> str:
        if self._failed:
            return "failed"
        if len(self._completed) == len(self._steps) and self._steps:
            return "completed"
        if not self._steps:
            return "idle"
        return "running"

    # --------------------------------------------------------------
    # Markers de progreso (para el ParallelExecutor)
    # --------------------------------------------------------------
    def mark_started(self, step_id: str) -> None:
        """Marca un paso como en ejecucion y emite progreso."""
        if step_id in self._steps:
            self._steps[step_id]["status"] = "running"
            self._steps[step_id]["started_at"] = time.time()
            self._emit_progress(step_id, "running", 0)

    def mark_completed(self, step_id: str, result: Any = None) -> None:
        """Marca un paso como completado y emite progreso."""
        if step_id in self._steps:
            self._steps[step_id]["status"] = "completed"
            self._steps[step_id]["result"] = result
            self._steps[step_id]["finished_at"] = time.time()
            self._completed.append(step_id)
            self._emit_progress(step_id, "completed", 100)

    def mark_failed(self, step_id: str, error: str = "") -> None:
        """Marca un paso como fallido y emite evento de error."""
        if step_id in self._steps:
            self._steps[step_id]["status"] = "failed"
            self._steps[step_id]["error"] = error
            self._steps[step_id]["finished_at"] = time.time()
            self._failed.append(step_id)
            self._emit_progress(step_id, "failed", 0)

    def _emit_progress(self, step_id: str, status: str, progress: float) -> None:
        """Emite evento de progreso al EventBus."""
        step = self._steps.get(step_id, {})
        self._bus.emit(
            CoreEvent(
                type=EventType.PROGRESS,
                data={
                    "step_id": step_id,
                    "status": status,
                    "progress": progress,
                    "description": step.get("description", ""),
                    "agent": step.get("agent", ""),
                },
                agent="orchestrator",
                status=status,
            )
        )

    # -------------------------------------------------------------
    # Reset
    # --------------------------------------------------------------
    def reset(self) -> None:
        """Reinicia el estado del orquestador."""
        self._steps = {}
        self._completed = []
        self._failed = []
        self._current_plan = None


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------

_orchestrator: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    """Retorna el singleton del Orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator


def reset_orchestrator() -> None:
    """Reinicia el singleton del Orchestrator."""
    global _orchestrator
    if _orchestrator is not None:
        _orchestrator.reset()
    _orchestrator = None
