from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import time

class InputType(str, Enum):
    """Tipos de entrada soportados."""
    CHAT = "chat"
    VOICE = "voz"
    GESTURE = "gesto"
    COMMAND = "comando"

class InputMessage(BaseModel):
    """Representa un mensaje de entrada unificado."""
    input_id: str = Field(..., description="Identificador único de la entrada")
    session_id: str = Field(..., description="Identificador de la sesión")
    type: InputType = Field(..., description="Tipo de entrada")
    content: str = Field(..., description="Contenido del mensaje de entrada")
    source: Optional[str] = Field(None, description="Origen de la entrada (e.g., "user", "system")")
    timestamp: float = Field(default_factory=time.time, description="Marca de tiempo de la entrada")

