from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class MissionDirective:
    mission_id: str = ""
    title: str = ""
    description: str = ""
    scopes: List[str] = field(default_factory=list)
    priority: str = "normal"
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"mission_id": self.mission_id, "title": self.title, "description": self.description,
                "scopes": self.scopes, "priority": self.priority, "params": self.params}


@dataclass
class MissionStep:
    step_id: str = ""
    mission_id: str = ""
    order: int = 0
    name: str = ""
    scope: str = "noop"
    description: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"

    def to_dict(self) -> Dict[str, Any]:
        return {"step_id": self.step_id, "mission_id": self.mission_id, "order": self.order,
                "name": self.name, "scope": self.scope, "description": self.description,
                "params": self.params, "status": self.status}


@dataclass
class MissionStepResult:
    step_id: str = ""
    order: int = 0
    scope: str = ""
    status: str = "success"
    output: Any = None
    error: str = ""
    latency_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {"step_id": self.step_id, "order": self.order, "scope": self.scope, "status": self.status,
                "output": self.output, "error": self.error, "latency_ms": self.latency_ms}


@dataclass
class MissionSummary:
    mission_id: str = ""
    title: str = ""
    completed_steps: int = 0
    total_steps: int = 0
    success: bool = False
    target_scopes: List[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"mission_id": self.mission_id, "title": self.title, "completed_steps": self.completed_steps,
                "total_steps": self.total_steps, "success": self.success, "target_scopes": self.target_scopes,
                "notes": self.notes}


@dataclass
class MissionRun:
    mission_id: str = ""
    directive: MissionDirective = field(default_factory=MissionDirective)
    steps: List[MissionStep] = field(default_factory=list)
    results: List[MissionStepResult] = field(default_factory=list)
    summary: Optional[MissionSummary] = None
    started_at: float = 0.0
    finished_at: float = 0.0
    status: str = "pending"

    def to_dict(self) -> Dict[str, Any]:
        d = self.directive.to_dict() if isinstance(self.directive, MissionDirective) else (self.directive or {})
        steps = [s.to_dict() if hasattr(s, "to_dict") else s for s in self.steps]
        results = [r.to_dict() if hasattr(r, "to_dict") else r for r in self.results]
        return {"mission_id": self.mission_id, "directive": d,
                "steps": steps,
                "results": results,
                "summary": (self.summary.to_dict() if self.summary and hasattr(self.summary, "to_dict") else self.summary),
                "started_at": self.started_at, "finished_at": self.finished_at, "status": self.status,
                "offline_only": True}


class MissionTracker:
    """Historial local de misiones ejecutadas (JSON, thread-safe)."""

    def __init__(self, store_dir: str = "backend/runner_state") -> None:
        import json, os, threading
        self._json, self._os, self._threading = json, os, threading
        self._dir = os.path.abspath(store_dir)
        os.makedirs(self._dir, exist_ok=True)
        self._path = os.path.join(self._dir, "mission_history.json")
        self._lock = threading.RLock()

    def load(self) -> List[Dict[str, Any]]:
        with self._lock:
            if not self._os.path.exists(self._path):
                return []
            try:
                with open(self._path, "r", encoding="utf-8") as fh:
                    return self._json.load(fh)
            except Exception:
                return []

    def save(self, runs) -> None:
        with self._lock:
            with open(self._path, "w", encoding="utf-8") as fh:
                self._json.dump(runs, fh, indent=2, ensure_ascii=False)

    def append(self, run: MissionRun) -> None:
        runs = self.load()
        runs.append(run.to_dict())
        self.save(runs)

    def get(self, mission_id: str) -> Optional[MissionRun]:
        for r in self.load():
            if r.get("mission_id") == mission_id:
                return MissionRun(**{k: v for k, v in r.items()
                                     if k in MissionRun.__dataclass_fields__})
        return None

    def list(self, limit: Optional[int] = None) -> List[MissionRun]:
        runs = self.load()
        if limit:
            runs = runs[-limit:]
        return [MissionRun(**{k: v for k, v in r.items()
                              if k in MissionRun.__dataclass_fields__}) for r in runs]

class EcosystemRunner:
    """Motor de ejecucion integral de misiones autonomas.

    Orquesta el ciclo de vida completo: validacion de intenciones ->
    planificacion de pasos -> ejecucion ordenada por scopes especializados
    -> generacion de artefactos -> tracking + reporte. Todo 100% local.
    """

    SUPPORTED_SCOPES = ("rag", "mesh", "sandbox", "audit", "memory", "master")

    def __init__(self, tracker: Optional[MissionTracker] = None) -> None:
        self.tracker = tracker or MissionTracker()
        self._directives: Dict[str, MissionDirective] = {}
        self._runs: Dict[str, MissionRun] = {}
        self._lock = threading.RLock()
        self._handlers: Dict[str, Callable[..., Dict[str, Any]]] = {}

    def register_handler(self, scope: str, fn: Callable[..., Dict[str, Any]]) -> None:
        with self._lock:
            self._handlers[scope] = fn

    def _validate_directive(self, directive: MissionDirective) -> None:
        if not directive.mission_id:
            directive.mission_id = f"mission-{uuid.uuid4().hex[:8]}"
        if not directive.title:
            directive.title = "Autonoma"
        if not directive.description and not directive.params:
            raise ValueError("MissionDirective requiere description o params")
        bad = [s for s in directive.scopes if s not in self.SUPPORTED_SCOPES]
        if bad:
            raise ValueError(f"scopes no soportados: {bad}")

    def plan(self, directive: MissionDirective) -> MissionRun:
        self._validate_directive(directive)
        with self._lock:
            self._directives[directive.mission_id] = directive
            run = MissionRun(mission_id=directive.mission_id, directive=directive, status="planning")
            steps: List[MissionStep] = []
            for i, scope in enumerate(directive.scopes):
                steps.append(MissionStep(
                    step_id=f"{directive.mission_id}-s{i+1}",
                    mission_id=directive.mission_id, order=i + 1,
                    name=f"step-{scope}-{i+1}", scope=scope,
                    description=f"Ejecutar scope: {scope}",
                    params=directive.params.get(scope, directive.params)))
            run.steps = steps
            self._runs[directive.mission_id] = run
            return run

    def execute(self, directive: MissionDirective,
                interrupt_event: Optional[threading.Event] = None) -> MissionRun:
        interrupt_event = interrupt_event or threading.Event()
        run = self.plan(directive)
        run.status = "running"
        run.started_at = time.time()
        for step in run.steps:
            if interrupt_event.is_set():
                step.status = "skip"
                run.results.append(MissionStepResult(step_id=step.step_id, order=step.order,
                                                     scope=step.scope, status="skip"))
                continue
            handler = self._handlers.get(step.scope)
            t0 = time.time()
            if handler is None:
                result = MissionStepResult(step_id=step.step_id, order=step.order, scope=step.scope,
                                           status="error", error=f"no handler for scope: {step.scope}")
            else:
                try:
                    out = handler(directive=directive, step=step, params=step.params)
                    result = MissionStepResult(step_id=step.step_id, order=step.order, scope=step.scope,
                                               status="success", output=out)
                except Exception as exc:
                    result = MissionStepResult(step_id=step.step_id, order=step.order, scope=step.scope,
                                               status="error", error=str(exc)[:200])
            result.latency_ms = int((time.time() - t0) * 1000)
            step.status = result.status
            run.results.append(result)
        run.finished_at = time.time()
        completed = sum(1 for s in run.steps if s.status == "success")
        total = len(run.steps)
        run.summary = MissionSummary(mission_id=run.mission_id, title=(directive.title if isinstance(directive, MissionDirective) else directive.get("title", "")),
                                      completed_steps=completed, total_steps=total,
                                      success=(completed == total and total > 0),
                                      target_scopes=list(directive.scopes),
                                      notes=f"Ejecucion completada; {run.results[-1].latency_ms if run.results else 0}ms ultimo step")
        run.status = "success" if run.summary.success else ("aborted" if interrupt_event.is_set() else "error")
        with self._lock:
            self._runs[directive.mission_id] = run
            self.tracker.append(run)
        return run

    def get_run(self, mission_id: str) -> Optional[MissionRun]:
        with self._lock:
            return self._runs.get(mission_id) or self.tracker.get(mission_id)

    def history(self, limit: Optional[int] = None) -> List[MissionRun]:
        with self._lock:
            local = list(self._runs.values())
            tracked = self.tracker.list(limit=limit)
            return (local + tracked)[-(limit or len(local + tracked)):] if limit else (local + tracked)
