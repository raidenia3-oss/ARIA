"""BLOQUE 70 - Modelos de datos para el motor de autoevolucion y parcheo."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_ts() -> float:
    return time.time()


class PatchStatus(str, Enum):
    PROPOSED = "proposed"
    SANDBOX_PASSED = "sandbox_passed"
    SANDBOX_FAILED = "sandbox_failed"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"
    REJECTED = "rejected"


class PatchType(str, Enum):
    BUGFIX = "bugfix"
    PERFORMANCE = "performance"
    SECURITY = "security"
    FEATURE = "feature"
    REFACTOR = "refactor"


@dataclass
class VersionSnapshot:
    """Instantanea de version de un archivo antes de una mutacion."""

    file_path: str
    content_hash: str
    backup_path: str
    timestamp: float = field(default_factory=_now_ts)
    patch_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "content_hash": self.content_hash,
            "backup_path": self.backup_path,
            "timestamp": self.timestamp,
            "patch_id": self.patch_id,
        }


@dataclass
class PatchProposal:
    """Una propuesta de parche generada por el sintetizador."""

    patch_id: str
    target_file: str
    old_snippet: str
    new_snippet: str
    patch_type: PatchType
    description: str
    rationale: str = ""
    confidence: float = 0.0
    status: PatchStatus = PatchStatus.PROPOSED
    created_at: str = field(default_factory=_utcnow_iso)
    applied_at: Optional[str] = None
    rolled_back_at: Optional[str] = None
    sandbox_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "patch_id": self.patch_id,
            "target_file": self.target_file,
            "old_snippet": self.old_snippet,
            "new_snippet": self.new_snippet,
            "patch_type": self.patch_type.value,
            "description": self.description,
            "rationale": self.rationale,
            "confidence": self.confidence,
            "status": self.status.value,
            "created_at": self.created_at,
            "applied_at": self.applied_at,
            "rolled_back_at": self.rolled_back_at,
            "sandbox_result": self.sandbox_result,
            "error": self.error,
            "metadata": self.metadata,
        }


__all__ = ["PatchStatus", "PatchType", "VersionSnapshot", "PatchProposal"]