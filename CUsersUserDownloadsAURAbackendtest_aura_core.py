

Script de prueba para validar el núcleo básico de AURA OS sin dependencias externas.
from typing import Dict, Any, List, Optional
from enum import Enum
from pydantic import BaseModel, Field
from loguru import logger

# --- Modelos ---

class EventType(str, Enum):
    """Tipos de eventos soportados."""
    
    START = "start"
    PROGRESS = "progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ERROR = "error"


class CoreEvent(BaseModel):
    """Evento central del sistema."""
    
    type: EventType = Field(..., description="Tipo de evento")
    data: Dict[str, Any] = Field(..., description="Datos asociados al evento")
    agent: Optional[str] = Field(None, description="Agente que emitió el evento")
    status: Optional[str] = Field(None, description="Estado del evento")
    timestamp: float = Field(default_factory=lambda: time.time(), description="Marca de tiempo del evento")


class DecisionStep(BaseModel):
    """Un paso individual en un plan de decisión."""
    
    step_id: str = Field(..., description="Identificador único del paso")
    description: str = Field(..., description="Descripción del paso")
    agent: Optional[str] = Field(None, description="Agente asignado para ejecutar el paso")
    tool: Optional[str] = Field(None, description="Herramienta o agente a utilizar")
    dependencies: List[str] = Field(default_factory=list, description="Pasos previos necesarios")


class Decision(BaseModel):
    
    """Una decisión que contiene un plan de pasos."""
    decision_id: str = Field(..., description="Identificador único de la decisión")
    session_id: str = Field(..., description="Identificador de la sesión")
    steps: List[DecisionStep] = Field(..., description="Lista de pasos en el plan")
    agents: List[str] = Field(default_factory=list, description="Agentes disponibles para ejecutar los pasos")


# --- EventBus ---

class EventBus:
    """Sistema de eventos para manejar la comunicación entre componentes."""
    
    def __init__(self):
        self._listeners: dict[str, List] = {}
    
    def subscribe(self, event_type: EventType, callback) -> None:
        """Suscribirse a un tipo de evento."""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)
    
    def emit(self, event: CoreEvent) -> None:
        """Emitir un evento al bus."""
        if event.type in self._listeners:
            for callback in self._listeners[event.type]:
                callback(event)
    

# --- DecisionEngine ---

class DecisionEngine:
    """
    Motor de decisiones que procesa planes de acción internamente.
    """
    
    def __init__(self, bus: EventBus):
        """Inicializa el DecisionEngine con un EventBus."""
        self._bus = bus
        self._bus.subscribe(EventType.START, self._handle_start_event)
    
    def process_decision(self, decision: Decision) -> None:
        """
        Procesa una decisión y emite eventos al EventBus.
        """
        logger.info(f"DecisionEngine: Procesando decisión {decision.decision_id}")
        
        # Emitir evento de inicio
        start_event = CoreEvent(
            type=EventType.START,
            data={
                "decision_id": decision.decision_id,
                "session_id": decision.session_id,
                "timestamp": time.time(),
                "agents": decision.agents,
                "event_id": f"start_{decision.decision_id}"
            },
            agent="decision_engine"
        )
        self._bus.emit(start_event)
    
    def _handle_start_event(self, event: CoreEvent) -> None:
        """Maneja eventos de inicio."""
        logger.debug(f"DecisionEngine: Evento de inicio recibido: {event.data}")
    
    def generate_decision(self, prompt: str, session_id: str) -> Decision:
        """
        Genera una decisión basada en un prompt."""
        # Ejemplo de generación de pasos
        steps = [
            DecisionStep(
                step_id="step_1",
                description="Ejecutar la acción principal",
                description="Analizar la solicitud del usuario",
                agent="analysis_agent",
                step_id="step_2",
            DecisionStep(
                tool="memory"
            ),
                agent="executor_agent",
                tool="execute"
            )
        
        ]
        decision = Decision(
            decision_id=f"decision_{session_id}_{int(time.time())}",
            session_id=session_id,
            steps=steps,
            agents=["analysis_agent", "executor_agent"]
        )
        
        return decision


# --- Orchestrator ---

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
        self._steps = {step.step_id: {
            "description": step.description,
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
                "timestamp": time.time(),
                "agents": decision.agents,
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


# --- Prueba ---

if __name__ == "__main__":
    # Importar time para la marca de tiempo
    import time
    
    # Inicializar EventBus
    bus = EventBus()
    decision_engine = DecisionEngine(bus)
    
    # Generar una decisión
    decision = decision_engine.generate_decision("Hola, ¿cómo estás?", "test_session")
    print("Decisión generada:", decision)
    
    # Procesar la decisión
    decision_engine.process_decision(decision)
    orchestrator = Orchestrator(bus)
    
    # Ejecutar el plan
    orchestrator.execute_plan(decision)
    status = orchestrator.get_status("test_session")
    print("Estado del orquestador:", status)
    orchestrator.mark_completed("step_1")
    
    # Obtener el estado actualizado
    status = orchestrator.get_status("test_session")
    print("Estado actualizado del orquestador:", status)
    
    logger.info("Prueba del núcleo básico de AURA OS completada con éxito.")
