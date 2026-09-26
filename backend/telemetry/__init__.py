"""BLOQUE 71 - Local Hardware Telemetry, Resource Governor & Performance Profiler.

Subsystem package for local hardware telemetry and resource governance.
"""

from __future__ import annotations

from backend.telemetry.models import (
    GovernorAction,
    GovernorDecision,
    GovernorPolicy,
    GovernorReport,
    GovernorThresholds,
    HardwareSnapshot,
    SensorStatus,
    WorkloadItem,
)
from backend.telemetry.governor import (
    GovernorEngine,
    TelemetryCollector,
    get_governor,
    reset_governor,
    set_governor,
    enable_autostart,
)

__all__ = [
    "GovernorAction",
    "GovernorDecision",
    "GovernorPolicy",
    "GovernorReport",
    "GovernorThresholds",
    "HardwareSnapshot",
    "SensorStatus",
    "WorkloadItem",
    "GovernorEngine",
    "TelemetryCollector",
    "get_governor",
    "reset_governor",
    "set_governor",
    "enable_autostart",
]

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
