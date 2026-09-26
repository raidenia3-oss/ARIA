from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
import time

class AnalysisType(str, Enum):
    """Tipos de análisis de contexto."""
    QUESTION = "pregunta"
    COMMAND = "comando"
    INFO = "informacion"
    TASK = "tarea"
    OTHER = "otro"

class AnalysisDomain(str, Enum):
    """Dominios de análisis de contexto."""
    SYSTEM = "sistema"
    WEB = "web"
    FILES = "archivos"
    MEMORY = "memoria"
    NONE = "ninguno"

class ContextAnalysisResult(BaseModel):
    """Resultado del análisis de contexto."""
    analysis_id: str = Field(..., description="Identificador único del análisis")
    session_id: str = Field(..., description="Identificador de la sesión")
    urgency: float = Field(..., ge=0.0, le=1.0, description="Nivel de urgencia (0.0-1.0)")
    type: AnalysisType = Field(..., description="Tipo de análisis")
    domain: AnalysisDomain = Field(..., description="Dominio del análisis")
    context: Dict[str, Any] = Field(..., description="Contexto extraído")
    timestamp: float = Field(default_factory=time.time, description="Marca de tiempo del análisis")

