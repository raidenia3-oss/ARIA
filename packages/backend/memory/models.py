"""
Modelos Pydantic para el sistema de memoria de AURA OS.
"""
from pydantic import BaseModel, Field
from typing import Dict, List, Optional


class MemoryEntry(BaseModel):
    """Representa una entrada en la memoria."""
    entry_id: str
    text: str
    timestamp: float = Field(default_factory=lambda: time.time())
    metadata: Dict[str, str] = {}


class IngestRequest(BaseModel):
    """Solicitud para ingresar texto en el sistema de memoria."""
    session_id: str
    input_text: str
    metadata: Dict[str, str] = {}


class ContextResponse(BaseModel):
    """Respuesta con contexto relevante."""
    contexts: List[MemoryEntry]
    query: Optional[str] = None
    layers: Dict[str, int] = Field(default_factory=dict)


class MemoryStats(BaseModel):
    """Estadísticas del sistema de memoria."""
    short_term_count: int
    medium_term_count: int
    long_term_count: int
    total_entries: int


import time