"""BLOQUE 92 - Modelos de datos del motor de planificación jerárquica local."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_ts() -> float:
    return time.time()


class GoalStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class MilestoneStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"


@dataclass
class Milestone:
    milestone_id: str
    title: str
    description: str = ""
    status: MilestoneStatus = MilestoneStatus.PENDING
    progress: float = 0.0
    depends_on: List[str] = field(default_factory=list)
    goal_id: str = ""
    completed_at: Optional[str] = None
    created_at: str = field(default_factory=_utcnow_iso)
    updated_at: str = field(default_factory=_utcnow_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "milestone_id": self.milestone_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "progress": self.progress,
            "depends_on": list(self.depends_on),
            "goal_id": self.goal_id,
            "completed_at": self.completed_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }


@dataclass
class GoalNode:
    goal_id: str
    title: str
    description: str = ""
    parent_id: Optional[str] = None
    status: GoalStatus = GoalStatus.PENDING
    priority: int = 0
    milestones: List[Milestone] = field(default_factory=list)
    children: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    deadline: Optional[str] = None
    created_at: str = field(default_factory=_utcnow_iso)
    updated_at: str = field(default_factory=_utcnow_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "title": self.title,
            "description": self.description,
            "parent_id": self.parent_id,
            "status": self.status.value,
            "priority": self.priority,
            "milestones": [m.to_dict() for m in self.milestones],
            "children": list(self.children),
            "dependencies": list(self.dependencies),
            "deadline": self.deadline,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }


@dataclass
class PlanEvent:
    event_id: str
    goal_id: str
    kind: str
    message: str
    timestamp: float = field(default_factory=_now_ts)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "goal_id": self.goal_id,
            "kind": self.kind,
            "message": self.message,
            "timestamp": self.timestamp,
            "metadata": dict(self.metadata),
        }


__all__ = [
    "GoalStatus",
    "MilestoneStatus",
    "Milestone",
    "GoalNode",
    "PlanEvent",
]
