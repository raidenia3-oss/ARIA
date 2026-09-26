from typing import List, Optional
from pydantic import BaseModel, Field

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
    agents: List[str] = Field(default_factory=list, description="Agentes disponibles para ejecución")

