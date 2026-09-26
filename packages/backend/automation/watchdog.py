"""BLOQUE 66 - AURA Local Runtime Watchdog, Auto-Recovery & Session State Persistence Engine."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import psutil

logger = logging.getLogger("AURA.Watchdog")

DEFAULT_HEALTH_INTERVAL = 2.0
DEFAULT_INACTIVITY_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_RECOVERY_COOLDOWN = 5.0
DEFAULT_CHECKPOINT_INTERVAL = 60.0
DEFAULT_MAX_SESSION_SNAPSHOTS = 20


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNRESPONSIVE = "unresponsive"
    CRASHED = "crashed"
    RECOVERING = "recovering"


class RecoveryAction(str, Enum):
    NONE = "none"
    RESTART_PROCESS = "restart_process"
    KILL_PROCESS = "kill_process"
    RELOAD_CONTEXT = "reload_context"
    RESUME_SESSION = "resume_session"
    FULL_RECOVERY = "full_recovery"


@dataclass
class ProcessHealth:
    pid: int
    name: str
    alive: bool
    cpu_percent: float
    memory_mb: float
    num_threads: int
    status: HealthStatus
    timestamp: float = field(default_factory=time.time)
    error: Optional[str] = None

    def to_dict(self):
        return {"pid": self.pid, "name": self.name, "alive": self.alive,
                "cpu_percent": self.cpu_percent, "memory_mb": self.memory_mb,
                "num_threads": self.num_threads, "status": self.status.value,
                "timestamp": self.timestamp, "error": self.error}


@dataclass
class WatchdogEvent:
    event_id: str
    session_id: str
    kind: str
    severity: str
    description: str
    action_taken: RecoveryAction
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {"event_id": self.event_id, "session_id": self.session_id,
                "kind": self.kind, "severity": self.severity,
                "description": self.description, "action_taken": self.action_taken.value,
                "timestamp": self.timestamp, "metadata": self.metadata}


@dataclass
class SessionCheckpoint:
    checkpoint_id: str
    session_id: str
    task_id: str
    objective: str
    progress: Dict[str, Any]
    active_macros: List[str]
    last_action: Optional[Dict[str, Any]]
    created_at: float = field(default_factory=time.time)

    def to_dict(self):
        return {"checkpoint_id": self.checkpoint_id, "session_id": self.session_id,
                "task_id": self.task_id, "objective": self.objective,
                "progress": self.progress, "active_macros": self.active_macros,
                "last_action": self.last_action, "created_at": self.created_at}


@dataclass
class WatchdogPolicy:
    inactivity_timeout: float = DEFAULT_INACTIVITY_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    recovery_cooldown: float = DEFAULT_RECOVERY_COOLDOWN
    checkpoint_interval: float = DEFAULT_CHECKPOINT_INTERVAL
    max_session_snapshots: int = DEFAULT_MAX_SESSION_SNAPSHOTS
    auto_kill_orphans: bool = True
    auto_restart: bool = True
    cpu_high_threshold: float = 90.0
    memory_high_mb: float = 512.0

    def to_dict(self):
        return {"inactivity_timeout": self.inactivity_timeout,
                "max_retries": self.max_retries,
                "recovery_cooldown": self.recovery_cooldown,
                "checkpoint_interval": self.checkpoint_interval,
                "max_session_snapshots": self.max_session_snapshots,
                "auto_kill_orphans": self.auto_kill_orphans,
                "auto_restart": self.auto_restart,
                "cpu_high_threshold": self.cpu_high_threshold,
                "memory_high_mb": self.memory_high_mb}


@dataclass
class WatchdogStatus:
    session_id: str
    running: bool
    health: HealthStatus
    last_heartbeat: float
    processes_monitored: int
    events_total: int
    recoveries_executed: int
    checkpoints_saved: int
    policy: WatchdogPolicy
    uptime_seconds: float = 0.0

    def to_dict(self):
        return {"session_id": self.session_id, "running": self.running,
                "health": self.health.value, "last_heartbeat": self.last_heartbeat,
                "processes_monitored": self.processes_monitored,
                "events_total": self.events_total,
                "recoveries_executed": self.recoveries_executed,
                "checkpoints_saved": self.checkpoints_saved,
                "policy": self.policy.to_dict(), "uptime_seconds": self.uptime_seconds}


class ProcessHealthMonitor:
    """Monitorea procesos locales mediante psutil, detectando bloqueos y fallos."""

    def __init__(self):
        self._lock = threading.Lock()
        self._processes = {}
        self._last_check = {}

    def track(self, pid):
        with self._lock:
            try:
                p = psutil.Process(pid)
                self._processes[pid] = p
                self._last_check[pid] = time.time()
                return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # Record the pid anyway so the next check() reports CRASHED
                self._processes[pid] = None
                self._last_check[pid] = time.time()
                return False

    def untrack(self, pid):
        with self._lock:
            self._processes.pop(pid, None)
            self._last_check.pop(pid, None)

    def check(self):
        results = []
        with self._lock:
            pids = list(self._processes.keys())
        for pid in pids:
            try:
                p = self._processes.get(pid)
                if p is None:
                    p = psutil.Process(pid)
                if not p.is_running():
                    results.append(ProcessHealth(pid=pid, name="", alive=False,
                                                 cpu_percent=0.0, memory_mb=0.0,
                                                 num_threads=0, status=HealthStatus.CRASHED))
                    continue
                cpu = p.cpu_percent(interval=None)
                mem = p.memory_info().rss / (1024 * 1024)
                nthreads = p.num_threads()
                name = p.name()
                status = HealthStatus.HEALTHY
                if cpu > 90.0 or mem > 512.0:
                    status = HealthStatus.DEGRADED
                results.append(ProcessHealth(pid=pid, name=name, alive=True,
                                              cpu_percent=cpu, memory_mb=mem,
                                              num_threads=nthreads, status=status))
                with self._lock:
                    self._last_check[pid] = time.time()
            except psutil.NoSuchProcess:
                results.append(ProcessHealth(pid=pid, name="", alive=False,
                                             cpu_percent=0.0, memory_mb=0.0,
                                             num_threads=0, status=HealthStatus.CRASHED))
            except Exception as exc:
                results.append(ProcessHealth(pid=pid, name="", alive=False,
                                             cpu_percent=0.0, memory_mb=0.0,
                                             num_threads=0, status=HealthStatus.UNRESPONSIVE,
                                             error=str(exc)))
        return results

    def kill(self, pid):
        with self._lock:
            p = self._processes.get(pid)
        if p is None:
            try:
                p = psutil.Process(pid)
            except psutil.NoSuchProcess:
                return False
        try:
            p.kill()
            return True
        except Exception:
            return False

    def restart(self, pid, command):
        self.kill(pid)
        try:
            import subprocess
            proc = subprocess.Popen(command, shell=True)
            self.track(proc.pid)
            return proc.pid
        except Exception:
            return None

    def tracked_pids(self):
        with self._lock:
            return list(self._processes.keys())

    def clear(self):
        with self._lock:
            self._processes.clear()
            self._last_check.clear()


class SessionCheckpointManager:
    """Gestiona checkpoints de sesion: captura, persistencia y reanudacion."""

    def __init__(self, session_id: str, checkpoint_dir: Optional[str] = None,
                 max_snapshots: int = DEFAULT_MAX_SESSION_SNAPSHOTS) -> None:
        self.session_id = session_id
        self.max_snapshots = max_snapshots
        self._lock = threading.Lock()
        self._checkpoints: List[SessionCheckpoint] = []
        self._dir = Path(checkpoint_dir or os.getenv(
            "AURA_CHECKPOINT_DIR", os.path.join("data", "checkpoints")))
        self._dir.mkdir(parents=True, exist_ok=True)
        self._load()

    def _path(self, cid: str) -> Path:
        return self._dir / f"{self.session_id}_{cid}.json"

    def _load(self) -> None:
        try:
            for f in sorted(self._dir.glob(f"{self.session_id}_*.json")):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    self._checkpoints.append(SessionCheckpoint(
                        checkpoint_id=data["checkpoint_id"],
                        session_id=data["session_id"],
                        task_id=data["task_id"],
                        objective=data["objective"],
                        progress=data.get("progress", {}),
                        active_macros=data.get("active_macros", []),
                        last_action=data.get("last_action"),
                        created_at=data.get("created_at", time.time()),
                    ))
                except Exception:
                    pass
            self._checkpoints.sort(key=lambda c: c.created_at)
            while len(self._checkpoints) > self.max_snapshots:
                self._checkpoints.pop(0)
        except Exception as exc:
            logger.debug("checkpoint load failed: %s", exc)

    def save(self, task_id: str, objective: str, progress: Dict[str, Any],
             active_macros: Optional[List[str]] = None,
             last_action: Optional[Dict[str, Any]] = None) -> SessionCheckpoint:
        cid = secrets.token_hex(8)
        cp = SessionCheckpoint(checkpoint_id=cid, session_id=self.session_id,
                                task_id=task_id, objective=objective,
                                progress=progress,
                                active_macros=active_macros or [],
                                last_action=last_action)
        with self._lock:
            self._checkpoints.append(cp)
            while len(self._checkpoints) > self.max_snapshots:
                removed = self._checkpoints.pop(0)
                try:
                    self._path(removed.checkpoint_id).unlink(missing_ok=True)
                except Exception:
                    pass
            try:
                self._path(cid).write_text(
                    json.dumps(cp.to_dict(), default=str), encoding="utf-8")
            except Exception as exc:
                logger.debug("checkpoint persist failed: %s", exc)
        return cp

    def latest(self) -> Optional[SessionCheckpoint]:
        with self._lock:
            return self._checkpoints[-1] if self._checkpoints else None

    def restore_latest(self) -> Optional[Dict[str, Any]]:
        cp = self.latest()
        return cp.to_dict() if cp else None

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [c.to_dict() for c in self._checkpoints]

    def count(self) -> int:
        with self._lock:
            return len(self._checkpoints)

    def clear(self) -> None:
        with self._lock:
            self._checkpoints.clear()
        try:
            for f in self._dir.glob(f"{self.session_id}_*.json"):
                f.unlink(missing_ok=True)
        except Exception:
            pass


class RuntimeWatchdog:
    """Motor principal: monitorea salud de procesos, aplica recuperacion
    autonoma y persiste checkpoints de sesion para reanudar tareas."""

    def __init__(self, session_id: str, policy: Optional[WatchdogPolicy] = None,
                 checkpoint_dir: Optional[str] = None,
                 on_recovery: Optional[Callable[[WatchdogEvent], None]] = None) -> None:
        self.session_id = session_id
        self.policy = policy or WatchdogPolicy()
        self.monitor = ProcessHealthMonitor()
        self.checkpoints = SessionCheckpointManager(
            session_id=session_id, checkpoint_dir=checkpoint_dir,
            max_snapshots=self.policy.max_session_snapshots)
        self.on_recovery = on_recovery
        self._lock = threading.Lock()
        self._events: List[WatchdogEvent] = []
        self._health = HealthStatus.HEALTHY
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_heartbeat = time.time()
        self._started_at = time.time()
        self._retry_count = 0
        self._last_recovery_at = 0.0
        self._macro_states: Dict[str, Any] = {}

    def track_process(self, pid: int, name: str = "") -> bool:
        return self.monitor.track(pid)

    def untrack_process(self, pid: int) -> None:
        self.monitor.untrack(pid)

    def heartbeat(self) -> None:
        self._last_heartbeat = time.time()

    def save_checkpoint(self, task_id: str, objective: str,
                        progress: Optional[Dict[str, Any]] = None,
                        active_macros: Optional[List[str]] = None,
                        last_action: Optional[Dict[str, Any]] = None) -> SessionCheckpoint:
        return self.checkpoints.save(task_id=task_id, objective=objective,
                                      progress=progress or {},
                                      active_macros=active_macros,
                                      last_action=last_action)

    def restore_session(self) -> Optional[Dict[str, Any]]:
        return self.checkpoints.restore_latest()

    def _record_event(self, kind: str, severity: str, description: str,
                      action: RecoveryAction,
                      metadata: Optional[Dict[str, Any]] = None) -> WatchdogEvent:
        ev = WatchdogEvent(event_id=secrets.token_hex(8), session_id=self.session_id,
                            kind=kind, severity=severity, description=description,
                            action_taken=action, metadata=metadata or {})
        with self._lock:
            self._events.append(ev)
        if action != RecoveryAction.NONE and self.on_recovery:
            try:
                self.on_recovery(ev)
            except Exception:
                pass
        return ev

    def check_once(self) -> List[ProcessHealth]:
        healths = self.monitor.check()
        now = time.time()
        for h in healths:
            if h.status == HealthStatus.CRASHED:
                self._health = HealthStatus.CRASHED
                self._record_event("process_crash", "critical",
                                    f"Process {h.pid} ({h.name}) crashed",
                                    RecoveryAction.RESTART_PROCESS,
                                    {"pid": h.pid, "name": h.name})
                if self.policy.auto_restart:
                    self._recover_process(h)
            elif h.status == HealthStatus.DEGRADED:
                self._health = HealthStatus.DEGRADED
                self._record_event("resource_pressure", "warning",
                                    f"Process {h.pid} high CPU/mem",
                                    RecoveryAction.RELOAD_CONTEXT,
                                    {"pid": h.pid, "cpu": h.cpu_percent,
                                     "memory_mb": h.memory_mb})
        inactivity = now - self._last_heartbeat
        if self._running and inactivity > self.policy.inactivity_timeout:
            self._record_event("inactivity", "warning",
                                f"No heartbeat for {inactivity:.1f}s",
                                RecoveryAction.RESUME_SESSION,
                                {"inactivity_seconds": inactivity})
            self._last_heartbeat = now
        return healths

    def _recover_process(self, health: ProcessHealth) -> None:
        now = time.time()
        if now - self._last_recovery_at < self.policy.recovery_cooldown:
            return
        if self._retry_count >= self.policy.max_retries:
            self._record_event("recovery_exhausted", "critical",
                                "Max retries reached",
                                RecoveryAction.FULL_RECOVERY,
                                {"retry_count": self._retry_count})
            return
        self._retry_count += 1
        self._last_recovery_at = now
        self._health = HealthStatus.RECOVERING
        ok = self.monitor.kill(health.pid)
        self._record_event("recovery", "warning",
                            f"Killed process {health.pid} (ok={ok})",
                            RecoveryAction.KILL_PROCESS,
                            {"pid": health.pid, "killed": ok})

    def start(self) -> bool:
        if self._running:
            return False
        self._running = True
        self._started_at = time.time()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _loop(self) -> None:
        interval = DEFAULT_HEALTH_INTERVAL
        while self._running:
            try:
                self.check_once()
            except Exception as exc:
                logger.debug("watchdog loop error: %s", exc)
            time.sleep(interval)

    def get_status(self) -> WatchdogStatus:
        with self._lock:
            return WatchdogStatus(
                session_id=self.session_id,
                running=self._running,
                health=self._health,
                last_heartbeat=self._last_heartbeat,
                processes_monitored=len(self.monitor.tracked_pids()),
                events_total=len(self._events),
                recoveries_executed=sum(1 for e in self._events
                                         if e.action_taken != RecoveryAction.NONE),
                checkpoints_saved=self.checkpoints.count(),
                policy=self.policy,
                uptime_seconds=time.time() - self._started_at)

    def recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return [e.to_dict() for e in self._events[-limit:]]

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        return self.checkpoints.list_checkpoints()


_watchdog: Optional[RuntimeWatchdog] = None
_watchdog_lock = threading.Lock()


def get_watchdog(session_id: str = "default",
                  policy: Optional[WatchdogPolicy] = None) -> RuntimeWatchdog:
    global _watchdog
    with _watchdog_lock:
        if _watchdog is None or _watchdog.session_id != session_id:
            _watchdog = RuntimeWatchdog(session_id=session_id, policy=policy)
        return _watchdog


def reset_watchdog() -> None:
    global _watchdog
    with _watchdog_lock:
        if _watchdog is not None:
            _watchdog.stop()
        _watchdog = None


__all__ = [
    "DEFAULT_CHECKPOINT_INTERVAL",
    "DEFAULT_HEALTH_INTERVAL",
    "DEFAULT_INACTIVITY_TIMEOUT",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_MAX_SESSION_SNAPSHOTS",
    "DEFAULT_RECOVERY_COOLDOWN",
    "HealthStatus",
    "ProcessHealth",
    "ProcessHealthMonitor",
    "RecoveryAction",
    "RuntimeWatchdog",
    "SessionCheckpoint",
    "SessionCheckpointManager",
    "WatchdogEvent",
    "WatchdogPolicy",
    "WatchdogStatus",
    "get_watchdog",
    "reset_watchdog",
]


# --------------------------------------------------------------------------- #
# REST routes
# --------------------------------------------------------------------------- #

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel

    router = APIRouter(prefix="/api/automation/watchdog", tags=["automation", "watchdog"])

    class TrackProcessRequest(BaseModel):
        pid: int
        name: str = ""

    class PolicyRequest(BaseModel):
        inactivity_timeout: Optional[float] = None
        max_retries: Optional[int] = None
        recovery_cooldown: Optional[float] = None
        checkpoint_interval: Optional[float] = None
        max_session_snapshots: Optional[int] = None
        auto_kill_orphans: Optional[bool] = None
        auto_restart: Optional[bool] = None
        cpu_high_threshold: Optional[float] = None
        memory_high_mb: Optional[float] = None

    class CheckpointRequest(BaseModel):
        task_id: str
        objective: str
        progress: Optional[Dict[str, Any]] = None
        active_macros: Optional[List[str]] = None
        last_action: Optional[Dict[str, Any]] = None

    @router.get("/status")
    async def watchdog_status(session_id: str = "default") -> Dict[str, Any]:
        return get_watchdog(session_id=session_id).get_status().to_dict()

    @router.post("/start")
    async def watchdog_start(session_id: str = "default") -> Dict[str, Any]:
        wd = get_watchdog(session_id=session_id)
        ok = wd.start()
        return {"status": "ok" if ok else "already_running", "session_id": session_id}

    @router.post("/stop")
    async def watchdog_stop(session_id: str = "default") -> Dict[str, Any]:
        wd = get_watchdog(session_id=session_id)
        wd.stop()
        return {"status": "ok", "session_id": session_id}

    @router.post("/track")
    async def track_process(req: TrackProcessRequest,
                            session_id: str = "default") -> Dict[str, Any]:
        wd = get_watchdog(session_id=session_id)
        ok = wd.track_process(req.pid, req.name)
        return {"status": "ok" if ok else "error", "pid": req.pid}

    @router.delete("/track/{pid}")
    async def untrack_process(pid: int, session_id: str = "default") -> Dict[str, Any]:
        wd = get_watchdog(session_id=session_id)
        wd.untrack_process(pid)
        return {"status": "ok", "pid": pid}

    @router.post("/check")
    async def check_health(session_id: str = "default") -> Dict[str, Any]:
        wd = get_watchdog(session_id=session_id)
        healths = wd.check_once()
        return {"status": "ok", "health": [h.to_dict() for h in healths]}

    @router.post("/policy")
    async def update_policy(req: PolicyRequest,
                            session_id: str = "default") -> Dict[str, Any]:
        wd = get_watchdog(session_id=session_id)
        p = wd.policy
        if req.inactivity_timeout is not None:
            p.inactivity_timeout = req.inactivity_timeout
        if req.max_retries is not None:
            p.max_retries = req.max_retries
        if req.recovery_cooldown is not None:
            p.recovery_cooldown = req.recovery_cooldown
        if req.checkpoint_interval is not None:
            p.checkpoint_interval = req.checkpoint_interval
        if req.max_session_snapshots is not None:
            p.max_session_snapshots = req.max_session_snapshots
            wd.checkpoints.max_snapshots = req.max_session_snapshots
        if req.auto_kill_orphans is not None:
            p.auto_kill_orphans = req.auto_kill_orphans
        if req.auto_restart is not None:
            p.auto_restart = req.auto_restart
        if req.cpu_high_threshold is not None:
            p.cpu_high_threshold = req.cpu_high_threshold
        if req.memory_high_mb is not None:
            p.memory_high_mb = req.memory_high_mb
        return {"status": "ok", "policy": p.to_dict()}

    @router.post("/checkpoint")
    async def save_checkpoint(req: CheckpointRequest,
                              session_id: str = "default") -> Dict[str, Any]:
        wd = get_watchdog(session_id=session_id)
        cp = wd.save_checkpoint(task_id=req.task_id, objective=req.objective,
                                 progress=req.progress,
                                 active_macros=req.active_macros,
                                 last_action=req.last_action)
        return {"status": "ok", "checkpoint": cp.to_dict()}

    @router.get("/checkpoints")
    async def list_checkpoints(session_id: str = "default") -> Dict[str, Any]:
        wd = get_watchdog(session_id=session_id)
        return {"status": "ok", "checkpoints": wd.list_checkpoints()}

    @router.get("/checkpoints/restore")
    async def restore_checkpoint(session_id: str = "default") -> Dict[str, Any]:
        wd = get_watchdog(session_id=session_id)
        cp = wd.restore_session()
        return {"status": "ok" if cp else "error", "checkpoint": cp}

    @router.get("/events")
    async def recent_events(session_id: str = "default",
                            limit: int = 50) -> Dict[str, Any]:
        wd = get_watchdog(session_id=session_id)
        return {"status": "ok", "events": wd.recent_events(limit)}

except Exception as exc:  # pragma: no cover
    logger.warning("watchdog routes skipped: %s", exc)
    router = None  # type: ignore