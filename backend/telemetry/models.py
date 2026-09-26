"""BLOQUE 71 - Local Hardware Telemetry, Resource Governor & Performance Profiler.

Data models for the hardware telemetry subsystem.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SensorStatus(str, Enum):
    OK = "ok"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    NOT_SUPPORTED = "not_supported"


class GovernorAction(str, Enum):
    NONE = "none"
    THROTTLE = "throttle"
    PAUSE = "pause"
    DOWNGRADE = "downgrade"
    ESCALATE = "escalate"
    WARN = "warn"


class GovernorDecision(str, Enum):
    ALLOW = "allow"
    THROTTLE = "throttle"
    DEFER = "defer"
    PAUSE = "pause"
    REJECT = "reject"


class HardwareSnapshot(BaseModel):
    """Point-in-time hardware telemetry snapshot."""

    timestamp: float
    cpu_percent: float = 0.0
    cpu_per_core: List[float] = Field(default_factory=list)
    cpu_cores_logical: int = 0
    cpu_cores_physical: int = 0
    cpu_load_1m: float = 0.0
    cpu_load_5m: float = 0.0
    cpu_load_15m: float = 0.0
    cpu_temp_c: Optional[float] = None
    ram_percent: float = 0.0
    ram_used_gb: float = 0.0
    ram_total_gb: float = 0.0
    ram_available_gb: float = 0.0
    swap_percent: float = 0.0
    disk_percent: float = 0.0
    disk_read_bytes_s: float = 0.0
    disk_write_bytes_s: float = 0.0
    net_bytes_sent_s: float = 0.0
    net_bytes_recv_s: float = 0.0
    gpu_percent: Optional[float] = None
    gpu_memory_used_mb: Optional[float] = None
    gpu_memory_total_mb: Optional[float] = None
    gpu_name: Optional[str] = None
    gpu_driver: Optional[str] = None
    gpu_temp_c: Optional[float] = None
    sensors: Dict[str, SensorStatus] = Field(default_factory=dict)
    host_os: str = "unknown"
    host_machine: str = "unknown"
    host_processor: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")


class GovernorThresholds(BaseModel):
    """Configurable saturation thresholds for the resource governor."""

    cpu_warn: float = 70.0
    cpu_throttle: float = 85.0
    cpu_critical: float = 95.0
    ram_warn: float = 75.0
    ram_throttle: float = 88.0
    ram_critical: float = 95.0
    swap_warn: float = 20.0
    swap_throttle: float = 50.0
    swap_critical: float = 80.0
    disk_warn: float = 80.0
    disk_throttle: float = 92.0
    gpu_warn: float = 80.0
    gpu_throttle: float = 92.0
    gpu_critical: float = 98.0
    temp_warn_c: float = 75.0
    temp_throttle_c: float = 85.0
    temp_critical_c: float = 92.0
    cooldown_seconds: float = 3.0
    sample_interval_s: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")


class GovernorPolicy(BaseModel):
    """Dynamic priority policy for workload allocation."""

    policy_id: str = "default"
    description: str = ""
    swarm_priority: int = 50
    automation_priority: int = 50
    vision_priority: int = 60
    research_priority: int = 40
    evolution_priority: int = 30
    audio_priority: int = 55
    web_priority: int = 70
    max_concurrent_heavy_tasks: int = 2
    allow_background_during_saturation: bool = True
    pause_on_critical: bool = True
    throttle_on_high: bool = True
    updated_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")


class WorkloadItem(BaseModel):
    """A tracked workload that the governor can throttle or pause."""

    workload_id: str
    name: str = ""
    kind: str = "generic"
    priority: int = 50
    weight: float = 1.0
    started_at: float = 0.0
    paused: bool = False
    throttled: bool = False
    downgraded: bool = False
    reason: str = ""
    state: str = "running"
    updated_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")


class GovernorReport(BaseModel):
    """Result of a governor evaluation cycle."""

    timestamp: float
    snapshot: HardwareSnapshot
    thresholds: GovernorThresholds
    policy: GovernorPolicy
    decision: GovernorDecision
    action: GovernorAction
    severity: str = "info"
    reasons: List[str] = Field(default_factory=list)
    active_workloads: int = 0
    paused_workloads: int = 0
    throttled_workloads: int = 0
    affected_workloads: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    profile: Dict[str, Any] = Field(default_factory=dict)
    avg_cpu_5m: float = 0.0
    avg_ram_5m: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")
