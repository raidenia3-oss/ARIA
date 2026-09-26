
AURA OS — Chunk 1: Core Orchestrator.

Orquestador de tareas que asigna pasos a agentes y maneja el progreso.


from typing import Dict, Any, List, Optional
from loguru import logger
from backend.models.decision import Decision, DecisionStep
from backend.models.event import CoreEvent, EventType
from backend.core.event_bus import EventBus

class Orchestrator:
    """
    Orquestador de tareas que asigna pasos a agentes y maneja el progreso.
    """
    
    def __init__(self, bus: EventBus):
        """Inicializa el Orchestrator con un EventBus."""
        self._bus = bus
        self._steps: Dict[str, Dict[str, Any]] = {}
        self._completed: List[str] = []
        self._failed: List[str] = []
        self._current_plan: Optional[Decision] = None
        self._bus.subscribe(EventType.START, self._handle_start_event)
    
    def execute_plan(self, decision: Decision) -> None:
        """Ejecuta un plan de decisión."""
        logger.info(f"Orchestrator: Ejecutando plan {decision.decision_id}")
        self._current_plan = decision
            "description": step.description,
        self._steps = {step.step_id: {
            "agent": step.agent,
            "status": "pending",
            "dependencies": step.dependencies
        } for step in decision.steps}
        
        # Emitir evento de inicio del plan
        start_event = CoreEvent(
            type=EventType.START,
            data={
                "decision_id": decision.decision_id,
                "session_id": decision.session_id,
                "agents": decision.agents,
                "timestamp": time.time(),
                "event_id": f"plan_start_{decision.decision_id}"
            },
            agent="orchestrator"
        )
        self._bus.emit(start_event)
    
    def _handle_start_event(self, event: CoreEvent) -> None:
        """Maneja eventos de inicio."""
        logger.debug(f"Orchestrator: Evento de inicio recibido: {event.data}")
    
    def mark_started(self, step_id: str) -> None:
        """Marca un paso como en ejecución."""
        if step_id in self._steps:
            self._steps[step_id]["status"] = "running"
            self._steps[step_id]["started_at"] = time.time()
            self._emit_progress(step_id, "running", 0)
    
    def mark_completed(self, step_id: str, result: Any = None) -> None:
        """Marca un paso como completado."""
        if step_id in self._steps:
            self._steps[step_id]["status"] = "completed"
            self._steps[step_id]["result"] = result
            self._steps[step_id]["finished_at"] = time.time()
            self._completed.append(step_id)
            self._emit_progress(step_id, "completed", 100)
    
    def mark_failed(self, step_id: str, error: str = "") -> None:
        """Marca un paso como fallido."""
        if step_id in self._steps:
            self._steps[step_id]["status"] = "failed"
            self._steps[step_id]["error"] = error
            self._steps[step_id]["finished_at"] = time.time()
            self._failed.append(step_id)
            self._emit_progress(step_id, "failed", 0)
    
    def _emit_progress(self, step_id: str, status: str, progress: float) -> None:
        """Emite evento de progreso al EventBus."""
        step = self._steps.get(step_id, {})
        self._bus.emit(CoreEvent(
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
        ))
    
    def get_status(self, session_id: str = "") -> Dict[str, Any]:
        """Obtiene el estado actual del orquestador."""
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
        """Determina el estado general del orquestador."""
        if self._failed:
            return "failed"
        if len(self._completed) == len(self._steps) and self._steps:
            return "completed"
        if not self._steps:
            return "idle"
        return "running"
    
    def reset(self) -> None:
        """Reinicia el estado del orquestador."""
        self._steps = {}
        self._completed = []
        self._failed = []
        self._current_plan = None
# Importar time para la marca de tiempo
import time
