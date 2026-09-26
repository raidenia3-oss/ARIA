

Motor de decisiones que procesa planes de acción internamente.
AURA OS — Chunk 1: Core Decision Engine.

Genera decisiones basadas en prompts y las emite al EventBus.

from typing import List, Dict, Any, Optional
from loguru import logger
from backend.models.decision import Decision, DecisionStep
from backend.models.event import CoreEvent, EventType
from backend.core.event_bus import EventBus

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
                "agents": decision.agents,
                "timestamp": time.time(),
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
                description="Analizar la solicitud del usuario",
                agent="analysis_agent",
                tool="memory"
            ),
            DecisionStep(
                step_id="step_2",
                description="Ejecutar la acción principal",
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

# Importar time para la marca de tiempo
import time
