from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import time

class AgentStatus(str, Enum):
    """Estados posibles de un agente."""
    IDLE = "inactivo"
    RUNNING = "ejecutando"
    PAUSED = "pausado"
    ERROR = "error"
    COMPLETED = "completado"

class AgentMessage(BaseModel):
    """Mensaje de estado o comunicación de un agente."""
    agent_id: str = Field(..., description="Identificador único del agente")
    session_id: str = Field(..., description="Identificador de la sesión")
    status: AgentStatus = Field(..., description="Estado actual del agente")
    message: str = Field(..., description="Mensaje del agente")
    timestamp: float = Field(default_factory=time.time, description="Marca de tiempo del mensaje")

