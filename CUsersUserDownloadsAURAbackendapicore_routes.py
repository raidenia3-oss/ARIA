
URA OS — Chunk 1: Core API Routes.

Rutas principales para interactuar con el sistema.


from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from typing import Dict, Any, List
from backend.models.decision import Decision, DecisionStep
from loguru import logger
from backend.models.event import CoreEvent, EventType
from backend.core.decision_engine import DecisionEngine
from backend.core.event_bus import EventBus
from backend.core.orchestrator import Orchestrator


router = APIRouter()
@router.post("/api/decision", response_model=Decision)
def create_decision(prompt: str, session_id: str = "default_session") -> Decision:
    """
    Genera una decisión basada en un prompt.
    """
    
    logger.info(f"API: Creando decisión para prompt: {prompt[:50]}...")
    # Obtener el DecisionEngine y el EventBus
    bus = EventBus()
    bus.start()
    decision_engine = DecisionEngine(bus)
    
    # Generar la decisión
    decision = decision_engine.generate_decision(prompt, session_id)
    
    # Procesar la decisión
    decision_engine.process_decision(decision)
    
    return decision

@router.post("/api/execute", response_model=Dict[str, Any])
def execute_plan(decision: Decision) -> Dict[str, Any]:
    """
    Ejecuta un plan de decisión.
    """
    logger.info(f"API: Ejecutando plan {decision.decision_id}")
    
    # Obtener el Orchestrator y el EventBus
    bus = EventBus()
    bus.start()
    orchestrator = Orchestrator(bus)
    
    # Ejecutar el plan
    orchestrator.execute_plan(decision)
    
    return {
        "status": "plan_started",
        "decision_id": decision.decision_id,
        "session_id": decision.session_id,
        "message": "Plan de ejecución iniciado."
    }

@router.get("/api/status", response_model=Dict[str, Any])
def get_status(session_id: str = "default_session") -> Dict[str, Any]:
    """
    Obtiene el estado actual del orquestador.
    """
    logger.info(f"API: Obteniendo estado para sesión {session_id}")
    
    # Obtener el Orchestrator y el EventBus
    bus = EventBus()
    bus.start()
    orchestrator = Orchestrator(bus)
    
    # Obtener el estado
    status = orchestrator.get_status(session_id)
    
    return status

@router.websocket("/ws/status")
async def websocket_status(websocket: WebSocket):
    """
    WebSocket para recibir actualizaciones en tiempo real del estado.
    """
    await websocket.accept()
    logger.info("WebSocket: Conexión establecida para actualizaciones de estado")
    
    bus = EventBus()
    bus.start()
    
    def handle_progress(event: CoreEvent) -> None:
        """Maneja eventos de progreso."""
        if event.type == EventType.PROGRESS:
            logger.debug(f"WebSocket: Evento de progreso recibido: {event.data}")
            try:
                await websocket.send_json(event.data)
            except Exception as e:
                logger.error(f"Error al enviar evento por WebSocket: {e}")
    
    bus.subscribe(EventType.PROGRESS, handle_progress)
    
    try:
        while True:
            data = await websocket.receive_text()
            logger.debug(f"WebSocket: Mensaje recibido: {data}")
    except WebSocketDisconnect:
        logger.info("WebSocket: Conexión cerrada")
        bus.stop()
