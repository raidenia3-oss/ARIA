"""BLOQUE 103 - Modelos del motor de testing E2E + estres del enjambre."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SuiteStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"


class ChainStep(str, Enum):
    """Pasos de la cadena E2E completa (102 bloques cubiertos por fases)."""
    MASTER_LAUNCH = "master_launch"
    GOVERNOR_GATE = "governor_gate"
    FUSION_INGEST = "fusion_ingest"
    FUSION_CONTEXT = "fusion_context"
    MEMORY_COGNITIVE = "memory_cognitive"
    MESH_PUBLISH = "mesh_publish"
    REFACTOR_PROPOSE = "refactor_propose"
    PLANNER_GOAL = "planner_goal"
    SIMULATION_SCENARIO = "simulation_scenario"
    FEDERATED_ROUND = "federated_round"
    MASTER_ECOSYSTEM = "master_ecosystem"


ALL_CHAIN_STEPS: List[str] = [s.value for s in ChainStep]


@dataclass
class StepResult:
    step: str
    ok: bool = False
    latency_ms: float = 0.0
    detail: Dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"step": self.step, "ok": self.ok,
                "latency_ms": round(self.latency_ms, 2),
                "detail": self.detail, "error": self.error}


@dataclass
class MatrixReport:
    report_id: str = ""
    started_at: str = ""
    finished_at: str = ""
    chain: str = "full_ecosystem"
    steps: List[StepResult] = field(default_factory=list)
    passed: int = 0
    failed: int = 0
    status: str = "idle"
    coverage_blocks: int = 0
    offline_only: bool = True

    def __post_init__(self) -> None:
        if not self.report_id:
            self.report_id = "e2e_" + uuid.uuid4().hex[:12]
        if not self.started_at:
            self.started_at = _utcnow_iso()

    def finalize(self) -> "MatrixReport":
        self.passed = sum(1 for s in self.steps if s.ok)
        self.failed = sum(1 for s in self.steps if not s.ok)
        if self.failed == 0 and self.steps:
            self.status = SuiteStatus.PASSED.value
        elif self.passed == 0:
            self.status = SuiteStatus.FAILED.value
        else:
            self.status = SuiteStatus.PARTIAL.value
        self.finished_at = _utcnow_iso()
        # Cobertura estimada: cada paso cubre una familia de bloques.
        self.coverage_blocks = min(102, len(self.steps) * 10)
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {"report_id": self.report_id, "started_at": self.started_at,
                "finished_at": self.finished_at, "chain": self.chain,
                "status": self.status, "passed": self.passed,
                "failed": self.failed,
                "steps": [s.to_dict() for s in self.steps],
                "coverage_blocks": self.coverage_blocks,
                "offline_only": True}


@dataclass
class StressReport:
    report_id: str = ""
    started_at: str = ""
    finished_at: str = ""
    agents: int = 0
    ops_per_agent: int = 0
    total_ops: int = 0
    ok_ops: int = 0
    failed_ops: int = 0
    deadlocks: int = 0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    throughput_ops: float = 0.0
    faults_injected: int = 0
    status: str = "idle"
    offline_only: bool = True

    def __post_init__(self) -> None:
        if not self.report_id:
            self.report_id = "stress_" + uuid.uuid4().hex[:12]
        if not self.started_at:
            self.started_at = _utcnow_iso()

    def to_dict(self) -> Dict[str, Any]:
        return {"report_id": self.report_id, "started_at": self.started_at,
                "finished_at": self.finished_at, "agents": self.agents,
                "ops_per_agent": self.ops_per_agent, "total_ops": self.total_ops,
                "ok_ops": self.ok_ops, "failed_ops": self.failed_ops,
                "deadlocks": self.deadlocks,
                "avg_latency_ms": round(self.avg_latency_ms, 2),
                "p95_latency_ms": round(self.p95_latency_ms, 2),
                "throughput_ops": round(self.throughput_ops, 2),
                "faults_injected": self.faults_injected,
                "status": self.status, "offline_only": True}


__all__ = ["SuiteStatus", "ChainStep", "ALL_CHAIN_STEPS", "StepResult",
           "MatrixReport", "StressReport", "_utcnow_iso"]
