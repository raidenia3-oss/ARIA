"""BLOQUE 93 - Modelos de datos del motor de especializaci\u00f3n de roles de enjambre y mercado de habilidades."""

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


def _uid(prefix: str = "r") -> str:
    return prefix + "_" + uuid.uuid4().hex[:12]


class RoleType(str, Enum):
    ANALYST = "analyst"
    AUDITOR = "auditor"
    RESEARCHER = "researcher"
    VISUAL_EXEC = "visual_exec"
    CODE_REVIEWER = "code_reviewer"
    SECURITY_SCANNER = "security_scanner"
    DATA_ENGINEER = "data_engineer"
    GENERALIST = "generalist"


class SkillCategory(str, Enum):
    CODE = "code"
    SECURITY = "security"
    RAG = "rag"
    VISION = "vision"
    DATA = "data"
    NETWORK = "network"
    AUDIO = "audio"


@dataclass
class CapabilityProfile:
    node_id: str
    roles: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    hardware: Dict[str, Any] = field(default_factory=dict)
    software: List[str] = field(default_factory=list)
    load: float = 0.0
    reputation: float = 1.0
    last_seen: float = field(default_factory=_now_ts)
    offline_only: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "roles": list(self.roles),
            "skills": list(self.skills),
            "hardware": dict(self.hardware),
            "software": list(self.software),
            "load": self.load,
            "reputation": self.reputation,
            "last_seen": self.last_seen,
            "offline_only": self.offline_only,
        }


@dataclass
class SkillModule:
    skill_id: str
    name: str
    category: str
    description: str = ""
    version: str = "1.0.0"
    owner: str = ""
    signature: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    requires: List[str] = field(default_factory=list)
    rating: float = 0.0
    downloads: int = 0
    created_at: str = field(default_factory=_utcnow_iso)
    offline_only: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "version": self.version,
            "owner": self.owner,
            "signature": self.signature,
            "payload": dict(self.payload),
            "requires": list(self.requires),
            "rating": self.rating,
            "downloads": self.downloads,
            "created_at": self.created_at,
            "offline_only": self.offline_only,
        }


@dataclass
class RoleAssignment:
    assignment_id: str
    task_id: str
    node_id: str
    role: str
    status: str = "active"
    created_at: float = field(default_factory=_now_ts)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assignment_id": self.assignment_id,
            "task_id": self.task_id,
            "node_id": self.node_id,
            "role": self.role,
            "status": self.status,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }


__all__ = [
    "RoleType",
    "SkillCategory",
    "CapabilityProfile",
    "SkillModule",
    "RoleAssignment",
]
