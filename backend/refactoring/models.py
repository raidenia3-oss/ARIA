"""BLOQUE 91 - Data models for autonomous code refactoring & hot-patching."""

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


class RefactoringType(str, Enum):
    """Tipos de refactorización soportados."""
    RENAME = "rename"
    EXTRACT_METHOD = "extract_method"
    SIMPLIFY = "simplify"
    REMOVE_DEAD_CODE = "remove_dead_code"
    FIX_SMELL = "fix_smell"


class PatchStatus(str, Enum):
    PROPOSED = "proposed"
    SANDBOX_PASSED = "sandbox_passed"
    SANDBOX_FAILED = "sandbox_failed"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"
    REJECTED = "rejected"


@dataclass
class RefactoringFinding:
    """Un hallazgo de code smell detectado por el auditor."""
    file_path: str
    line: int
    severity: str  # info | warning | error
    category: str  # complexity | dead_code | naming | style | security
    message: str
    snippet: str = ""
    suggested_patch: str = ""
    confidence: float = 0.0
    created_at: str = field(default_factory=lambda: _utcnow_iso())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "line": self.line,
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "snippet": self.snippet,
            "suggested_patch": self.suggested_patch,
            "confidence": self.confidence,
            "created_at": self.created_at,
        }


@dataclass
class PatchProposal:
    """Propuesta de refactorización/hotpatching."""
    patch_id: str
    target_file: str
    old_snippet: str
    new_snippet: str
    refactoring_type: RefactoringType
    description: str
    rationale: str = ""
    confidence: float = 0.0
    status: PatchStatus = PatchStatus.PROPOSED
    created_at: str = field(default_factory=lambda: _utcnow_iso())
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
            "refactoring_type": self.refactoring_type.value,
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


@dataclass
class HotPatchRecord:
    """Registro de un hot-patch aplicado en caliente."""
    record_id: str
    module_name: str
    target_file: str
    patch_id: str
    applied_at: str = field(default_factory=lambda: _utcnow_iso())
    reloaded: bool = False
    reload_error: str = ""
    success: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "module_name": self.module_name,
            "target_file": self.target_file,
            "patch_id": self.patch_id,
            "applied_at": self.applied_at,
            "reloaded": self.reloaded,
            "reload_error": self.reload_error,
            "success": self.success,
        }


@dataclass
class ModuleState:
    """Estado de un módulo para hot-patching."""
    module_name: str
    file_path: str
    last_reload_ts: float = 0.0
    reload_count: int = 0
    checksum: str = ""
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_name": self.module_name,
            "file_path": self.file_path,
            "last_reload_ts": self.last_reload_ts,
            "reload_count": self.reload_count,
            "checksum": self.checksum,
            "is_active": self.is_active,
        }


@dataclass
class RefactoringMetrics:
    """Métricas de refactorización."""
    total_proposals: int = 0
    patches_applied: int = 0
    patches_rolled_back: int = 0
    hot_patches: int = 0
    hot_patches_failed: int = 0
    findings_detected: int = 0
    avg_confidence: float = 0.0
    last_run: str = ""
    offline_only: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_proposals": self.total_proposals,
            "patches_applied": self.patches_applied,
            "patches_rolled_back": self.patches_rolled_back,
            "hot_patches": self.hot_patches,
            "hot_patches_failed": self.hot_patches_failed,
            "findings_detected": self.findings_detected,
            "avg_confidence": self.avg_confidence,
            "last_run": self.last_run,
            "offline_only": True,
        }


__all__ = [
    "RefactoringType",
    "PatchStatus",
    "RefactoringFinding",
    "PatchProposal",
    "HotPatchRecord",
    "ModuleState",
    "RefactoringMetrics",
]