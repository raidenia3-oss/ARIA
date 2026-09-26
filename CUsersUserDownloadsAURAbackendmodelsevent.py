from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
import time

class EventType(str, Enum):
    """Tipos de eventos soportados."""
    START = "start"
    PROGRESS = "progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ERROR = "error"
    INPUT = "input"
    DECISION = "decision"
    ACTION = "action"
    AGENT_STATUS = "agent_status"
    RESULT = "result"

class CoreEvent(BaseModel):
    """Evento central del sistema."""
    type: EventType = Field(..., description="Tipo de evento")
    data: Dict[str, Any] = Field(..., description="Datos asociados al evento")
    agent: Optional[str] = Field(None, description="Agente que emitió el evento")
    status: Optional[str] = Field(None, description="Estado del evento")
    timestamp: float = Field(default_factory=time.time, description="Marca de tiempo del evento")

