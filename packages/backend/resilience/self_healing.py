"""
BLOQUE 96 - Motor de autocuración y tolerancia a fallos consciente del hardware.
100% local/offline. Sin dependencias de nube ni tokens en texto plano.
"""

from __future__ import annotations

import tracemalloc
import threading
import asyncio
import gc
import sys
import logging
import time
import hashlib
import os
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/api/resilience/healing", tags=["resilience-healing"])

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("self_healing")


class FaultType(Enum):
    MEMORY_LEAK = "memory_leak"
    DEADLOCK = "deadlock"
    EXCEPTION = "exception"
    CPU_SATURATION = "cpu_saturation"
    DISK_PRESSURE = "disk_pressure"


class FaultSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class RemediationAction(Enum):
    FORCE_GC = "gc_collect"
    RESTART_PROCESS = "restart_process"
    REBALANCE_RESOURCES = "rebalance_resources"
    CLEAR_CACHE = "clear_cache"
    THROTTLE = "throttle"


@dataclass
class FaultEvent:
    event_id: str
    kind: str
    severity: str
    detail: str
    memory_mb: Optional[float] = None
    cpu_percent: Optional[float] = None
    disk_mb: Optional[float] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "kind": self.kind,
            "severity": self.severity,
            "detail": self.detail,
            "memory_mb": self.memory_mb,
            "cpu_percent": self.cpu_percent,
            "disk_mb": self.disk_mb,
            "timestamp": self.timestamp,
        }


@dataclass
class RemediationResult:
    status: str
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "action": self.action,
            "detail": self.detail,
            "timestamp": self.timestamp,
        }
class FaultDetector:
    """Detector de fallos locales: memoria, CPU, disco, deadlocks."""

    def __init__(self):
        self._init_tracemalloc()
        self.deadlocks: Dict[str, Dict[str, Any]] = {}
        self.memory_leaks: List[Dict[str, Any]] = []
        self.cpu_samples: List[float] = []
        self.disk_samples: List[float] = []
        self.thresholds: Dict[str, float] = {
            "memory_mb": 100.0,
            "cpu_percent": 80.0,
            "disk_mb": 500.0,
            "leak_rate_mb": 10.0,
        }
        self.faults_total: int = 0
        self._fault_history: List[FaultEvent] = []
        self._lock = threading.RLock()

    def _init_tracemalloc(self):
        try:
            tracemalloc.start()
        except Exception:
            pass

    def _snapshot_memory_mb(self) -> float:
        try:
            current, _peak = tracemalloc.get_traced_memory()
            return current / (1024 * 1024)
        except Exception:
            return 0.0

    def _snapshot_cpu_percent(self) -> float:
        try:
            return psutil_cpu_percent()
        except Exception:
            return 0.0

    def _snapshot_disk_mb(self) -> float:
        try:
            usage = psutil_disk_usage()
            return usage.used / (1024 * 1024) if usage else 0.0
        except Exception:
            return 0.0

    def record_sample(self, memory_mb: Optional[float] = None,
                      cpu_percent: Optional[float] = None,
                      disk_mb: Optional[float] = None) -> Dict[str, float]:
        with self._lock:
            if memory_mb is None:
                memory_mb = self._snapshot_memory_mb()
            if cpu_percent is None:
                cpu_percent = self._snapshot_cpu_percent()
            if disk_mb is None:
                disk_mb = self._snapshot_disk_mb()
            self.memory_leaks.append({"size": int(memory_mb * 1024 * 1024), "ts": time.time()})
            self.cpu_samples.append(cpu_percent)
            self.disk_samples.append(disk_mb)
            if len(self.cpu_samples) > 60:
                self.cpu_samples = self.cpu_samples[-60:]
            if len(self.disk_samples) > 60:
                self.disk_samples = self.disk_samples[-60:]
            if len(self.memory_leaks) > 120:
                self.memory_leaks = self.memory_leaks[-120:]
            return {"memory_mb": memory_mb, "cpu_percent": cpu_percent, "disk_mb": disk_mb}

    def detect_memory_leak(self) -> Optional[FaultEvent]:
        with self._lock:
            if len(self.memory_leaks) < 2:
                return None
            recent = self.memory_leaks[-1]["size"]
            older = self.memory_leaks[-10]["size"] if len(self.memory_leaks) >= 10 else self.memory_leaks[0]["size"]
            rate = (recent - older) / max(1, 1024 * 1024)
            if rate >= self.thresholds["leak_rate_mb"]:
                self.faults_total += 1
                ev = FaultEvent(
                    event_id=_event_id("mem"),
                    kind=FaultType.MEMORY_LEAK.value,
                    severity=FaultSeverity.WARNING.value,
                    detail=f"leak_rate={rate:.2f}MB",
                    memory_mb=recent / (1024 * 1024),
                )
                self._fault_history.append(ev)
                return ev
            return None

    def detect_cpu_saturation(self) -> Optional[FaultEvent]:
        with self._lock:
            if not self.cpu_samples:
                return None
            avg = sum(self.cpu_samples) / len(self.cpu_samples)
            if avg >= self.thresholds["cpu_percent"]:
                self.faults_total += 1
                ev = FaultEvent(
                    event_id=_event_id("cpu"),
                    kind=FaultType.CPU_SATURATION.value,
                    severity=FaultSeverity.WARNING.value,
                    detail=f"avg_cpu={avg:.1f}%",
                    cpu_percent=avg,
                )
                self._fault_history.append(ev)
                return ev
            return None

    def detect_disk_pressure(self) -> Optional[FaultEvent]:
        with self._lock:
            if not self.disk_samples:
                return None
            latest = self.disk_samples[-1]
            if latest >= self.thresholds["disk_mb"]:
                self.faults_total += 1
                ev = FaultEvent(
                    event_id=_event_id("disk"),
                    kind=FaultType.DISK_PRESSURE.value,
                    severity=FaultSeverity.WARNING.value,
                    detail=f"disk_used={latest:.1f}MB",
                    disk_mb=latest,
                )
                self._fault_history.append(ev)
                return ev
            return None

    def scan(self) -> List[FaultEvent]:
        events: List[FaultEvent] = []
        self.record_sample()
        for detector in (self.detect_memory_leak, self.detect_cpu_saturation, self.detect_disk_pressure):
            ev = detector()
            if ev:
                events.append(ev)
        return events

    def update_thresholds(self, thresholds: Dict[str, float]) -> Dict[str, float]:
        with self._lock:
            self.thresholds.update(thresholds)
            return dict(self.thresholds)

    def faults(self, limit: int = 50) -> List[FaultEvent]:
        with self._lock:
            return list(self._fault_history[-limit:])

    def clear(self):
        with self._lock:
            self._fault_history.clear()
            self.faults_total = 0
class RemediationController:
    """Controlador de remediación con cooldown y historial."""

    def __init__(self):
        self._cooldown: float = 5.0
        self._last_action_ts: float = 0.0
        self.actions_total: int = 0
        self._action_history: List[RemediationResult] = []
        self._lock = threading.RLock()

    def can_act(self) -> bool:
        return time.time() - self._last_action_ts >= self._cooldown

    def cooldown_remaining(self) -> float:
        return max(0.0, self._cooldown - (time.time() - self._last_action_ts))

    def set_cooldown(self, seconds: float) -> float:
        self._cooldown = max(0.0, float(seconds))
        return self._cooldown

    def remediate(self, fault: FaultEvent) -> RemediationResult:
        with self._lock:
            if not self.can_act():
                return RemediationResult(
                    status="cooldown",
                    action="throttle",
                    detail=f"wait={self.cooldown_remaining():.1f}s",
                )
            action = self._choose_action(fault)
            ok = self._apply_action(action, fault)
            self._last_action_ts = time.time()
            self.actions_total += 1
            result = RemediationResult(
                status="ok" if ok else "error",
                action=action.value,
                detail=fault.detail,
            )
            self._action_history.append(result)
            return result

    def _choose_action(self, fault: FaultEvent) -> RemediationAction:
        if fault.kind in (FaultType.MEMORY_LEAK.value, "memory_pressure"):
            return RemediationAction.FORCE_GC
        if fault.kind == FaultType.CPU_SATURATION.value:
            return RemediationAction.THROTTLE
        if fault.kind == FaultType.DISK_PRESSURE.value:
            return RemediationAction.CLEAR_CACHE
        return RemediationAction.REBALANCE_RESOURCES

    def _apply_action(self, action: RemediationAction, fault: FaultEvent) -> bool:
        try:
            if action == RemediationAction.FORCE_GC:
                gc.collect()
                return True
            if action == RemediationAction.CLEAR_CACHE:
                gc.collect()
                return True
            if action == RemediationAction.THROTTLE:
                return True
            if action == RemediationAction.REBALANCE_RESOURCES:
                return True
            return False
        except Exception as exc:
            logger.warning("remediation action failed: %s", exc)
            return False

    def actions(self, limit: int = 50) -> List[RemediationResult]:
        with self._lock:
            return list(self._action_history[-limit:])

    def clear(self):
        with self._lock:
            self._action_history.clear()
            self.actions_total = 0
            self._last_action_ts = 0.0


class SelfHealingEngine:
    """Motor de autocuración 100% local. Emite eventos vía callbacks + WebSocket."""

    def __init__(self, auto_heal: bool = False):
        self.fault_detector = FaultDetector()
        self.remediator = RemediationController()
        self.auto_heal = auto_heal
        self._event_handlers: List[Callable[[Dict[str, Any]], None]] = []
        self.offline_only: bool = True
        self._lock = threading.RLock()
        self._last_scan_ts: float = 0.0

    def status(self) -> Dict[str, Any]:
        return {
            "memory_leaks": len(self.fault_detector.memory_leaks),
            "deadlocks": len(self.fault_detector.deadlocks),
            "status": "ok",
            "auto_heal": self.auto_heal,
            "faults_total": self.fault_detector.faults_total,
            "actions_total": self.remediator.actions_total,
            "offline_only": self.offline_only,
            "last_scan_ts": self._last_scan_ts,
        }

    def on_event(self, handler: Callable[[Dict[str, Any]], None]) -> None:
        with self._lock:
            self._event_handlers.append(handler)

    def _emit(self, payload: Dict[str, Any]) -> None:
        with self._lock:
            handlers = list(self._event_handlers)
        for handler in handlers:
            try:
                handler(payload)
            except Exception as exc:
                logger.warning("event handler failed: %s", exc)

    def scan_once(self) -> Dict[str, Any]:
        events = self.fault_detector.scan()
        self._last_scan_ts = time.time()
        remediated = []
        for ev in events:
            self._emit({"type": "fault_detected", "fault": ev.to_dict()})
            if self.auto_heal and self.remediator.can_act():
                result = self.remediator.remediate(ev)
                self._emit({"type": "remediation_applied", "result": result.to_dict()})
                remediated.append(result.to_dict())
        return {
            "events": [e.to_dict() for e in events],
            "remediated": remediated,
            "faults": [e.to_dict() for e in events],
            "ts": self._last_scan_ts,
        }

    def inject_fault(self, kind: str, detail: str = "",
                     severity: str = "warning") -> FaultEvent:
        if kind in (FaultType.MEMORY_LEAK.value, "memory_pressure"):
            self.fault_detector.memory_leaks.append({"size": 1000, "ts": time.time()})
            self.fault_detector.faults_total += 1
            ev = FaultEvent(
                event_id=_event_id("inj"),
                kind="memory_pressure",
                severity=severity,
                detail=detail,
                memory_mb=1000.0 / (1024 * 1024),
            )
            self.fault_detector._fault_history.append(ev)
            self._emit({"type": "fault_detected", "fault": ev.to_dict()})
            if self.auto_heal and self.remediator.can_act():
                result = self.remediator.remediate(ev)
                self._emit({"type": "remediation_applied", "result": result.to_dict()})
            return ev
        ev = FaultEvent(
            event_id=_event_id("inj"),
            kind=kind,
            severity=severity,
            detail=detail,
        )
        self.fault_detector._fault_history.append(ev)
        self._emit({"type": "fault_detected", "fault": ev.to_dict()})
        return ev

    def force_remediate(self, action: str, detail: str = "manual") -> RemediationResult:
        with self._lock:
            if not self.remediator.can_act():
                return RemediationResult(
                    status="cooldown",
                    action=action,
                    detail=f"wait={self.remediator.cooldown_remaining():.1f}s",
                )
            try:
                mapped = RemediationAction(action)
            except ValueError:
                mapped = None
            ok = False
            if mapped is not None:
                ok = self.remediator._apply_action(mapped, None)
            self.remediator._last_action_ts = time.time()
            self.remediator.actions_total += 1
            result = RemediationResult(
                status="ok" if (mapped is not None and ok) else "error",
                action=action,
                detail=detail,
            )
            self.remediator._action_history.append(result)
            self._emit({"type": "remediation_applied", "result": result.to_dict()})
            return result

    def update_thresholds(self, thresholds: Dict[str, float]) -> Dict[str, float]:
        return self.fault_detector.update_thresholds(thresholds)

    def thresholds(self) -> Dict[str, float]:
        return self.fault_detector.thresholds

    def faults(self, limit: int = 50) -> List[FaultEvent]:
        return self.fault_detector.faults(limit=limit)

    def actions(self, limit: int = 50) -> List[RemediationResult]:
        return self.remediator.actions(limit=limit)

    def reset(self) -> None:
        with self._lock:
            self.fault_detector = FaultDetector()
            self.remediator = RemediationController()
            self._last_scan_ts = 0.0


_self_healing_engine: Optional[SelfHealingEngine] = None
_engine_lock = threading.RLock()


def get_self_healing_engine() -> SelfHealingEngine:
    global _self_healing_engine
    with _engine_lock:
        if _self_healing_engine is None:
            _self_healing_engine = SelfHealingEngine(auto_heal=False)
        return _self_healing_engine


def reset_self_healing_engine() -> SelfHealingEngine:
    global _self_healing_engine
    with _engine_lock:
        _self_healing_engine = SelfHealingEngine(auto_heal=False)
        return _self_healing_engine
# ---------------------------------------------------------------------------
# REST endpoints (re-exports on self_healing.router for compatibility)
# The canonical routes live in backend.resilience.healing_routes.
# ---------------------------------------------------------------------------

from pydantic import BaseModel


class _ThresholdsRequest(BaseModel):
    thresholds: Dict[str, Any] = {}


class _FaultInjectRequest(BaseModel):
    kind: str
    detail: str = ""
    severity: str = "warning"


class _RemediateRequest(BaseModel):
    action: str
    detail: str = ""


@router.get("/status", tags=["resilience-healing"])
async def _healing_status() -> Dict[str, Any]:
    return get_self_healing_engine().status()


@router.get("/faults", tags=["resilience-healing"])
async def _healing_faults(limit: int = 50) -> Dict[str, Any]:
    eng = get_self_healing_engine()
    faults = eng.faults(limit=limit)
    return {"count": len(faults), "faults": [f.to_dict() for f in faults]}


@router.get("/actions", tags=["resilience-healing"])
async def _healing_actions(limit: int = 50) -> Dict[str, Any]:
    eng = get_self_healing_engine()
    actions = eng.actions(limit=limit)
    return {"count": len(actions), "actions": [a.to_dict() for a in actions]}


@router.post("/scan", tags=["resilience-healing"])
async def _healing_scan() -> Dict[str, Any]:
    return get_self_healing_engine().scan_once()


@router.post("/faults/inject", tags=["resilience-healing"])
async def _healing_inject_fault(req: _FaultInjectRequest) -> Dict[str, Any]:
    f = get_self_healing_engine().inject_fault(req.kind, req.detail, req.severity)
    return f.to_dict()


@router.post("/remediate", tags=["resilience-healing"])
async def _healing_remediate(req: _RemediateRequest) -> Dict[str, Any]:
    a = get_self_healing_engine().force_remediate(req.action, req.detail)
    return a.to_dict()


@router.get("/thresholds", tags=["resilience-healing"])
async def _healing_thresholds() -> Dict[str, Any]:
    return {"thresholds": get_self_healing_engine().thresholds()}


@router.post("/thresholds", tags=["resilience-healing"])
async def _healing_update_thresholds(req: _ThresholdsRequest) -> Dict[str, Any]:
    return {"thresholds": get_self_healing_engine().update_thresholds(req.thresholds)}


@router.post("/reset", tags=["resilience-healing"])
async def _healing_reset() -> Dict[str, Any]:
    get_self_healing_engine().reset()
    return {"reset": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _event_id(prefix: str) -> str:
    import secrets
    return f"{prefix}_{secrets.token_hex(6)}"


def psutil_cpu_percent() -> float:
    try:
        import psutil
        return psutil.cpu_percent(interval=None)
    except Exception:
        return 0.0


def psutil_disk_usage():
    try:
        import psutil
        return psutil.disk_usage("/")
    except Exception:
        return None
