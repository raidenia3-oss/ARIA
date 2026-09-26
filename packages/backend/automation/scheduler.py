"""BLOQUE 67 - AURA Local Autonomous Task Scheduler & Cron Engine."""

from __future__ import annotations

import inspect
import asyncio
import json
import logging
import os
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("AURA.Scheduler")

DEFAULT_SCHEDULER_INTERVAL = 1.0
DEFAULT_MAX_TASKS = 100
DEFAULT_MAX_RUNS_HISTORY = 200
DEFAULT_PERSIST_DIR = os.path.join("data", "scheduler")

WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
          "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}

VALID_TRIGGERS = ("cron", "interval")
VALID_OVERLAP = ("skip", "queue")
VALID_STATUSES = ("idle", "running", "paused", "error")


class CronParseError(ValueError):
    """Expresion cron invalida."""


def _parse_field(expr: str, lo: int, hi: int) -> set:
    out: set = set()
    for part in expr.split(","):
        part = part.strip()
        if not part:
            raise CronParseError(f"campo vacio en {expr!r}")
        step = 1
        if "/" in part:
            base, step_s = part.split("/", 1)
            try:
                step = int(step_s)
            except ValueError as exc:
                raise CronParseError(f"paso invalido en {part!r}") from exc
            if step < 1:
                raise CronParseError(f"paso invalido en {part!r}")
        else:
            base = part
        if base == "*":
            start, end = lo, hi
        elif "-" in base:
            a_s, b_s = base.split("-", 1)
            try:
                start, end = int(a_s), int(b_s)
            except ValueError as exc:
                raise CronParseError(f"rango invalido en {part!r}") from exc
        else:
            try:
                start = int(base)
            except ValueError as exc:
                raise CronParseError(f"valor invalido en {part!r}") from exc
            end = start if step == 1 else hi
        if start < lo or end > hi or start > end:
            raise CronParseError(f"valor fuera de rango [{lo},{hi}] en {part!r}")
        out.update(range(start, end + 1, step))
    return out


def parse_cron(expr: str) -> Tuple[set, set, set, set, set, bool, bool]:
    parts = expr.split()
    if len(parts) != 5:
        raise CronParseError("cron debe tener 5 campos: min hora dom mes dow")
    mins = _parse_field(parts[0], 0, 59)
    hors = _parse_field(parts[1], 0, 23)
    doms = _parse_field(parts[2], 1, 31)
    mons = _parse_field(parts[3], 1, 12)
    dows = _parse_field(parts[4], 0, 6)
    if 7 in dows:
        dows.add(0)
    dom_all = doms == set(range(1, 32))
    dow_all = dows == set(range(0, 7))
    return mins, hors, doms, mons, dows, dom_all, dow_all


def _day_matches(dt: datetime, doms: set, dows: set, dom_all: bool, dow_all: bool) -> bool:
    if dom_all and dow_all:
        return True
    dom_ok = dt.day in doms
    cron_dow = (dt.weekday() + 1) % 7
    dow_ok = cron_dow in dows
    if dom_all:
        return dow_ok
    if dow_all:
        return dom_ok
    return dom_ok or dow_ok


def next_cron_fire(expr: str, from_epoch: float) -> float:
    mins, hors, doms, mons, dows, dom_all, dow_all = parse_cron(expr)
    dt = datetime.fromtimestamp(from_epoch).replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(500_000):
        if dt.month not in mons:
            y, m = (dt.year + 1, 1) if dt.month == 12 else (dt.year, dt.month + 1)
            dt = dt.replace(year=y, month=m, day=1, hour=0, minute=0)
            continue
        if not _day_matches(dt, doms, dows, dom_all, dow_all):
            dt = (dt + timedelta(days=1)).replace(hour=0, minute=0)
            continue
        if dt.hour not in hors:
            dt = (dt + timedelta(hours=1)).replace(minute=0)
            continue
        if dt.minute not in mins:
            dt = dt + timedelta(minutes=1)
            continue
        return dt.timestamp()
    raise CronParseError("no hay siguiente disparo en 500k iteraciones")


def validate_cron(expr: str) -> bool:
    try:
        parse_cron(expr)
        return True
    except CronParseError:
        return False


class ScheduledTask:
    """Tarea programada con trigger cron/interval y recursos."""

    def __init__(self, task_id, name="noop", kind="noop", trigger="interval",
                 cron="", interval_seconds=60.0, priority=5,
                 overlap_policy="skip", resources=None, metadata=None,
                 enabled=True, status="idle", run_count=0, last_run=None,
                 next_run=None, error_count=0, created_at=None):
        self.task_id = task_id
        self.name = name
        self.kind = kind
        self.trigger = trigger
        self.cron = cron
        self.interval_seconds = float(interval_seconds)
        self.priority = int(priority)
        self.overlap_policy = overlap_policy
        self.resources = tuple(resources or ())
        self.metadata = dict(metadata or {})
        self.enabled = bool(enabled)
        self.status = status
        self.run_count = int(run_count)
        self.last_run = last_run
        self.next_run = next_run
        self.error_count = int(error_count)
        self.created_at = created_at or time.time()

    def validate(self):
        if self.trigger not in VALID_TRIGGERS:
            raise ValueError("trigger invalido: " + repr(self.trigger))
        if self.trigger == "cron" and not self.cron:
            raise ValueError("cron requerido para trigger=cron")
        if self.trigger == "cron" and not validate_cron(self.cron):
            raise ValueError("cron invalido: " + repr(self.cron))
        if self.overlap_policy not in VALID_OVERLAP:
            raise ValueError("overlap_policy invalido: " + repr(self.overlap_policy))
        if self.interval_seconds < 1:
            raise ValueError("interval_seconds debe ser >= 1")
        if self.priority < 0 or self.priority > 99:
            raise ValueError("priority debe estar en [0,99]")

    def to_dict(self):
        return {
            "task_id": self.task_id,
            "name": self.name,
            "kind": self.kind,
            "trigger": self.trigger,
            "cron": self.cron,
            "interval_seconds": self.interval_seconds,
            "priority": self.priority,
            "overlap_policy": self.overlap_policy,
            "resources": list(self.resources),
            "metadata": self.metadata,
            "enabled": self.enabled,
            "status": self.status,
            "run_count": self.run_count,
            "last_run": self.last_run,
            "next_run": self.next_run,
            "error_count": self.error_count,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d):
        import inspect
        valid = set(inspect.signature(cls.__init__).parameters) - {"self"}
        return cls(**{k: v for k, v in d.items() if k in valid})

    def __repr__(self):
        return "ScheduledTask(task_id=" + repr(self.task_id) + ", name=" + repr(self.name) + ", status=" + repr(self.status) + ")"

class ResourceConflictResolver:
    """Evita que dos tareas usen el mismo recurso simultaneamente."""

    def __init__(self):
        self._locks = {}

    def acquire_all(self, resources, owner):
        if not resources:
            return True
        for r in resources:
            if r in self._locks and self._locks[r] != owner:
                return False
        for r in resources:
            self._locks[r] = owner
        return True

    def release_all(self, resources, owner):
        for r in resources:
            if self._locks.get(r) == owner:
                del self._locks[r]

    def snapshot(self):
        return dict(self._locks)

    def is_busy(self, resource):
        return resource in self._locks


class TaskPersistence:
    """Persiste tareas e historial en JSON bajo el directorio indicado."""

    def __init__(self, persist_dir):
        self._path = os.path.join(persist_dir, "tasks.json")
        os.makedirs(persist_dir, exist_ok=True)

    def save(self, tasks, history):
        data = {"tasks": [t.to_dict() for t in tasks], "history": history}
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self._path)

    def load(self):
        if not os.path.exists(self._path):
            return [], []
        with open(self._path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [ScheduledTask.from_dict(td) for td in data], []
        tasks = [ScheduledTask.from_dict(td) for td in data.get("tasks", [])]
        return tasks, data.get("history", [])

class TaskSchedulerEngine:
    """Motor principal: registra tareas, resuelve conflictos, ejecuta ticks."""

    def __init__(self, persist_dir=None, on_task=None, max_tasks=DEFAULT_MAX_TASKS,
                 max_history=DEFAULT_MAX_RUNS_HISTORY):
        self._persist_dir = persist_dir or os.environ.get(
            "AURA_SCHEDULER_DIR", DEFAULT_PERSIST_DIR)
        self._persistence = TaskPersistence(self._persist_dir)
        self._tasks = {}
        self._handlers = {}
        self._resolver = ResourceConflictResolver()
        self._on_task = on_task
        self._max_tasks = max_tasks
        self._max_history = max_history
        self._history = []
        self._running = False
        self._loop = None
        self._tick_count = 0
        self._lock = threading.RLock()
        self._load()

    def _load(self):
        tasks, history = self._persistence.load()
        for t in tasks:
            self._tasks[t.task_id] = t
        self._history = history[-self._max_history:]

    def _persist(self):
        self._persistence.save(list(self._tasks.values()), self._history[-self._max_history:])

    def register_handler(self, kind, fn):
        self._handlers[kind] = fn

    def list_handlers(self):
        return list(self._handlers.keys())

    def add_task(self, task):
        with self._lock:
            if task.task_id in self._tasks:
                return False
            if len(self._tasks) >= self._max_tasks:
                return False
            task.validate()
            if task.next_run is None:
                task.next_run = self._compute_next(task)
            self._tasks[task.task_id] = task
            self._persist()
            return True

    def get_task(self, task_id):
        with self._lock:
            return self._tasks.get(task_id)

    def list_tasks(self, enabled=None, status=None, limit=200):
        with self._lock:
            out = []
            for t in self._tasks.values():
                if enabled is not None and t.enabled != enabled:
                    continue
                if status is not None and t.status != status:
                    continue
                out.append(t.to_dict())
            out.sort(key=lambda d: (d["priority"], d["created_at"]))
            return out[:limit]

    def remove_task(self, task_id):
        with self._lock:
            if task_id not in self._tasks:
                return False
            del self._tasks[task_id]
            self._persist()
            return True

    def pause_task(self, task_id):
        with self._lock:
            t = self._tasks.get(task_id)
            if not t:
                return False
            t.status = "paused"
            self._persist()
            return True

    def resume_task(self, task_id):
        with self._lock:
            t = self._tasks.get(task_id)
            if not t:
                return False
            t.status = "idle"
            self._persist()
            return True

    def enable_task(self, task_id, enabled):
        with self._lock:
            t = self._tasks.get(task_id)
            if not t:
                return False
            t.enabled = bool(enabled)
            self._persist()
            return True

    def set_enabled(self, task_id, enabled):
        return self.enable_task(task_id, enabled)

    def _compute_next(self, task):
        now = time.time()
        if task.trigger == "cron":
            try:
                return next_cron_fire(task.cron, now)
            except CronParseError:
                return now + task.interval_seconds
        return now + task.interval_seconds

    def _record(self, task, success, error=None, duration_ms=0.0):
        self._history.append({
            "task_id": task.task_id,
            "name": task.name,
            "kind": task.kind,
            "ts": time.time(),
            "success": bool(success),
            "error": str(error) if error else None,
            "duration_ms": duration_ms,
        })
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
        task.run_count += 1
        task.last_run = time.time()
        task.next_run = self._compute_next(task)
        if success:
            task.status = "idle"
            task.error_count = 0
        else:
            task.status = "error"
            task.error_count += 1

    def tick_once(self):
        fired = []
        now = time.time()
        with self._lock:
            ready = [t for t in self._tasks.values()
                     if t.enabled and t.status != "paused" and t.next_run and t.next_run <= now]
            ready.sort(key=lambda t: (t.priority, t.next_run or 0))
            tick_locks = {}
            for t in ready:
                if not t.enabled or t.status == "paused":
                    continue
                conflict = False
                if t.resources:
                    for r in t.resources:
                        if r in tick_locks:
                            conflict = True
                            break
                    if conflict:
                        continue
                    for r in t.resources:
                        tick_locks[r] = t.task_id
                try:
                    fn = self._handlers.get(t.kind)
                    if fn is None:
                        result = {"ok": True, "detail": "no-handler"}
                    else:
                        result = fn(t, t.metadata) or {"ok": True}
                    self._record(t, True, None, 0.0)
                except Exception as exc:
                    self._record(t, False, exc, 0.0)
                    result = {"ok": False, "error": str(exc)}
                fired.append({"task_id": t.task_id, "result": result})
                self._on_task and self._on_task(t, result)
        self._tick_count += 1
        self._persist()
        return fired

    def audit(self, limit=50):
        with self._lock:
            return list(reversed(self._history[-limit:]))

    def busy_resources(self):
        return self._resolver.snapshot()

    def status(self):
        with self._lock:
            return {
                "running": self._running,
                "tick_count": self._tick_count,
                "tasks_total": len(self._tasks),
                "tasks_enabled": sum(1 for t in self._tasks.values() if t.enabled),
                "tasks_paused": sum(1 for t in self._tasks.values() if t.status == "paused"),
                "tasks_error": sum(1 for t in self._tasks.values() if t.status == "error"),
                "busy_resources": self.busy_resources(),
            }

    async def start(self):
        if self._running:
            return {"status": "already_running"}
        self._running = True
        return {"status": "started", "tasks": len(self._tasks)}

    async def stop(self):
        self._running = False
        return {"status": "stopped"}

    def run_task_now(self, task_id):
        with self._lock:
            t = self._tasks.get(task_id)
            if not t:
                return False
            t.next_run = time.time() - 1
            return True

    def update_task(self, task_id, updates):
        with self._lock:
            t = self._tasks.get(task_id)
            if not t:
                return False
            for k, v in updates.items():
                if hasattr(t, k):
                    setattr(t, k, v)
            t.validate()
            self._persist()
            return True

_scheduler = None
_scheduler_lock = threading.Lock()


def get_scheduler(persist_dir=None, on_task=None):
    global _scheduler
    if _scheduler is None:
        with _scheduler_lock:
            if _scheduler is None:
                _scheduler = TaskSchedulerEngine(persist_dir=persist_dir, on_task=on_task)
    return _scheduler


def reset_scheduler():
    global _scheduler
    with _scheduler_lock:
        _scheduler = None


SchedulerEngine = TaskSchedulerEngine


from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


router = APIRouter(
    prefix="/api/automation/scheduler",
    tags=["automation", "scheduler"],
)


class RegisterTaskRequest(BaseModel):
    task_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    kind: str = Field(default="noop", min_length=1, max_length=100)
    trigger: str = Field(default="interval", pattern="^(cron|interval)$")
    cron: str = Field(default="", max_length=100)
    interval_seconds: float = Field(default=60.0, ge=1, le=31_536_000)
    priority: int = Field(default=5, ge=0, le=99)
    overlap_policy: str = Field(default="skip", pattern="^(skip|queue)$")
    resources: Optional[List[str]] = Field(default=None, max_items=10)
    metadata: Optional[Dict[str, Any]] = None
    enabled: bool = True


class UpdateTaskRequest(BaseModel):
    name: Optional[str] = None
    kind: Optional[str] = None
    trigger: Optional[str] = None
    cron: Optional[str] = None
    interval_seconds: Optional[float] = None
    priority: Optional[int] = None
    overlap_policy: Optional[str] = None
    resources: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None


def _engine():
    return get_scheduler()


@router.get("/status")
async def scheduler_status():
    return _engine().status()


@router.get("/handlers")
async def scheduler_handlers():
    return {"handlers": _engine().list_handlers()}


@router.post("/tasks")
async def register_task(payload: RegisterTaskRequest):
    if payload.trigger == "cron" and not validate_cron(payload.cron):
        raise HTTPException(status_code=422, detail="cron invalido: " + repr(payload.cron))
    try:
        task = ScheduledTask(
            task_id=payload.task_id, name=payload.name, kind=payload.kind,
            trigger=payload.trigger, cron=payload.cron,
            interval_seconds=payload.interval_seconds, priority=payload.priority,
            overlap_policy=payload.overlap_policy, resources=payload.resources,
            metadata=payload.metadata, enabled=payload.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not _engine().add_task(task):
        raise HTTPException(status_code=409, detail="task_already_exists")
    return {"status": "registered", "task": task.to_dict()}


@router.get("/tasks")
async def list_tasks(enabled: Optional[bool] = None, status: Optional[str] = None, limit: int = 200):
    tasks = _engine().list_tasks(enabled=enabled, status=status, limit=limit)
    return {"count": len(tasks), "tasks": tasks}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    task = _engine().get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task_not_found")
    return {"task": task.to_dict()}


@router.put("/tasks/{task_id}")
async def update_task_endpoint(task_id: str, payload: UpdateTaskRequest):
    updates = {k: v for k, v in payload.dict().items() if v is not None}
    if not _engine().update_task(task_id, updates):
        raise HTTPException(status_code=404, detail="task_not_found")
    return {"status": "updated", "task": _engine().get_task(task_id).to_dict()}


@router.post("/tasks/{task_id}/pause")
async def pause_task(task_id: str):
    if not _engine().pause_task(task_id):
        raise HTTPException(status_code=404, detail="task_not_found")
    return {"status": "paused", "task_id": task_id}


@router.post("/tasks/{task_id}/resume")
async def resume_task(task_id: str):
    if not _engine().resume_task(task_id):
        raise HTTPException(status_code=404, detail="task_not_found")
    return {"status": "resumed", "task_id": task_id}


@router.post("/tasks/{task_id}/enable")
async def enable_task(task_id: str, enabled: bool = True):
    if not _engine().enable_task(task_id, enabled):
        raise HTTPException(status_code=404, detail="task_not_found")
    return {"status": "enabled" if enabled else "disabled", "task_id": task_id}


@router.post("/tasks/{task_id}/run-now")
async def run_task_now(task_id: str):
    if not _engine().run_task_now(task_id):
        raise HTTPException(status_code=404, detail="task_not_found")
    return {"status": "queued_for_immediate_run", "task_id": task_id}


@router.delete("/tasks/{task_id}")
async def remove_task(task_id: str):
    if not _engine().remove_task(task_id):
        raise HTTPException(status_code=404, detail="task_not_found")
    return {"status": "removed", "task_id": task_id}


@router.get("/tasks/{task_id}/runs")
async def list_runs(task_id: str, limit: int = 50):
    task = _engine().get_task(str(task_id))
    if not task:
        raise HTTPException(status_code=404, detail="task_not_found")
    runs = [e for e in _engine().audit(limit=limit) if e["task_id"] == task.task_id]
    return {"count": len(runs), "runs": runs}


@router.post("/tick")
async def tick():
    fired = _engine().tick_once()
    return {"fired": fired, "tick_count": _engine().status()["tick_count"]}


@router.post("/start")
async def engine_start():
    return await _engine().start()


@router.post("/stop")
async def engine_stop():
    return await _engine().stop()


@router.get("/audit")
async def scheduler_audit(limit: int = 50):
    events = _engine().audit(limit=limit)
    return {"count": len(events), "events": events}


@router.get("/locks")
async def scheduler_locks():
    return {"busy_resources": _engine().busy_resources()}


_startup_registered = False


async def _autostart():
    if os.getenv("AURA_SCHEDULER_AUTOSTART", "1") == "0":
        return
    if os.getenv("PYTEST_CURRENT_TEST"):
        return
    await _engine().start()


async def _autostop():
    if os.getenv("PYTEST_CURRENT_TEST"):
        return
    await _engine().stop()


def enable_autostart():
    global _startup_registered
    if _startup_registered:
        return
    router.on_startup.append(_autostart)
    router.on_shutdown.append(_autostop)
    _startup_registered = True


__all__ = [
    "CronParseError", "ResourceConflictResolver", "ScheduledTask",
    "TaskPersistence", "TaskSchedulerEngine", "SchedulerEngine",
    "get_scheduler", "reset_scheduler", "validate_cron",
    "parse_cron", "next_cron_fire", "router", "enable_autostart",
]
