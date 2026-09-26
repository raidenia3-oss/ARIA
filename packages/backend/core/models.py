# -*- coding: utf-8 -*-
"""AURA OS — Chunk 1: Core Models (Pydantic v2).

modelos compartidos por todo el núcleo:
   - Input (entrada unificada)
   - Event (evento del EventBus)
   - Decision (decisión de Jan / motor local)
   - Result (resultado final)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------- entrada unificada ----------
class InputType(str, Enum):
    CHAT = "chat"
    VOICE = "voice"
    GESTURE = "gesture"
    COMMAND = "command"
    FILE = "file"
    SYSTEM = "system"


class UnifiedInput(BaseModel):
    type: InputType = InputType.CHAT
    content: str = ""
    source: str = "user"
    session_id: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    input_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])

    def to_event_data(self) -> Dict[str, Any]:
        return {
            "input_id": self.input_id,
            "type": self.type.value,
            "content": self.content,
            "source": self.source,
            "session_id": self.session_id,
            "metadata": self.metadata,
        }


# ---------- eventos del bus ----------
class EventType(str, Enum):
    INPUT = "input"
    THOUGHT = "thought"
    DECISION = "decision"
    ACTION = "action"
    AGENT_START = "agent_start"
    AGENT_END = "agent_end"
    RESULT = "result"
    PROGRESS = "progress"
    ERROR = "error"
    COMPLETE = "complete"


class CoreEvent(BaseModel):
    type: EventType = EventType.INPUT
    data: Dict[str, Any] = Field(default_factory=dict)
    agent: str = "system"
    status: str = "running"
    timestamp: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "data": self.data,
            "agent": self.agent,
            "status": self.status,
            "timestamp": self.timestamp,
            "event_id": self.event_id,
        }


# ---------- decisión (Jan / motor local) ----------
class DecisionType(str, Enum):
    PLAN = "plan"
    TASK = "task"
    RESPONSE = "response"
    REFUSAL = "refusal"
    FALLBACK = "fallback"


class DecisionStep(BaseModel):
    step: int = 0
    description: str = ""
    agent: Optional[str] = None
    tool: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)


class Decision(BaseModel):
    type: DecisionType = DecisionType.TASK
    plan: List[DecisionStep] = Field(default_factory=list)
    rationale: str = ""
    agents: List[str] = Field(default_factory=list)
    priority: float = Field(default=0.5, ge=0.0, le=1.0)


# ---------- resultado final ----------
class ActionResult(BaseModel):
    success: bool = False
    message: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)


class ProcessingResult(BaseModel):
    session_id: str = ""
    input_id: str = ""
    events: List[Dict[str, Any]] = Field(default_factory=list)
    decision: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    status: str = "completed"
    latency_ms: float = 0.0


# ---------- estado del núcleo ----------
class CoreStatus(BaseModel):
    status: str = "ok"
    version: str = "2.0.0"
    chunk: int = 1
    modules: Dict[str, str] = Field(default_factory=dict)
    jan_available: bool = False


class EventStatus(str, Enum):
    """Estado de un paso de ejecución."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"