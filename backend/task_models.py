"""Task contract for AURA/AME automation."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    LEARNING = "learning"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskOrigin(str, Enum):
    AURA = "aura"
    AME = "ame"


class TaskStep(BaseModel):
    step_id: str
    name: str
    status: TaskStatus = TaskStatus.PENDING
    tool: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class TaskModel(BaseModel):
    task_id: str
    action_id: Optional[str] = None
    session_id: Optional[str] = None
    origin: TaskOrigin = TaskOrigin.AURA
    name: str
    action_type: str
    goal: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    finished_at: Optional[str] = None
    steps: List[TaskStep] = Field(default_factory=list)
    pending_steps: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
