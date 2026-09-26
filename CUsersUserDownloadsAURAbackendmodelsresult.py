from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
import time

class ResultStatus(str, Enum):
    """Estados posibles del resultado de una acción."""
    SUCCESS = "exito"
    FAILURE = "fallo"
    PARTIAL = "parcial"

class ActionResult(BaseModel):
    """Resultado de la ejecución de una acción o paso."""
    result_id: str = Field(..., description="Identificador único del resultado")
    session_id: str = Field(..., description="Identificador de la sesión")
    step_id: str = Field(..., description="Identificador del paso al que corresponde el resultado")
    status: ResultStatus = Field(..., description="Estado del resultado")
    output: Optional[Dict[str, Any]] = Field(None, description="Salida detallada de la acción")
    error: Optional[str] = Field(None, description="Mensaje de error si la acción falló")
    timestamp: float = Field(default_factory=time.time, description="Marca de tiempo del resultado")
