"""BLOQUE 79 - Local Master Control Dashboard & Unified Autonomous Orchestration Engine.

Nucleo central de orquestacion del ecosistema AURA: coordina y supervisa todos
los submodulos especializados bajo un unico ciclo de control soberano local.

Arquitectura:
- MasterConfig: politica del ciclo maestro (intervalo, retencion, strict).
- SubmoduleStatus: salud de cada motor previo (desacoplado, por adapter).
- GlobalEvent: bus de eventos centralizados con niveles y respuesta automatica.
- PipelineRun: mision compuesta (RAG -> visual -> memoria -> P2P) encadenable.
- MasterOrchestrator: registro de modulos, collect_status protegido,
  emit/handle de eventos, sintetizador de pipelines y snapshot global.

Reglas:
- No toca subsistemas previos (registro por adapters; sin imports duros).
- 100% offline; no expone tokens ni credenciales en texto plano.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

LEVEL_INFO = "info"
LEVEL_WARN = "warn"
LEVEL_ERROR = "error"
LEVEL_CRITICAL = "critical"
_LEVELS = (LEVEL_INFO, LEVEL_WARN, LEVEL_ERROR, LEVEL_CRITICAL)


@dataclass
class MasterConfig:
    max_events: int = 500
    max_pipelines: int = 100
    cycle_interval_s: float = 30.0
    strict_mode: bool = False


@dataclass
class SubmoduleStatus:
    name: str
    enabled: bool = True
    healthy: bool = False
    last_check: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "enabled": self.enabled, "healthy": self.healthy,
                "last_check": self.last_check, "details": self.details, "error": self.error}


@dataclass
class GlobalEvent:
    event_id: str
    ts: float
    source: str
    kind: str
    level: str = LEVEL_INFO
    payload: Dict[str, Any] = field(default_factory=dict)
    decision: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"event_id": self.event_id, "ts": self.ts, "source": self.source,
                "kind": self.kind, "level": self.level, "payload": self.payload,
                "decision": self.decision}


@dataclass
class PipelineStep:
    kind: str
    params: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    result: Any = None
    duration_ms: int = 0


@dataclass
class PipelineRun:
    pipeline_id: str
    name: str
    steps: List[PipelineStep] = field(default_factory=list)
    status: str = "pending"
    started_at: float = 0.0
    finished_at: float = 0.0
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"pipeline_id": self.pipeline_id, "name": self.name, "status": self.status,
                "started_at": self.started_at, "finished_at": self.finished_at,
                "error": self.error,
                "steps": [{"kind": s.kind, "params": s.params, "status": s.status,
                           "result": s.result, "duration_ms": s.duration_ms}
                          for s in self.steps]}

class MasterOrchestrator:
    """Nucleo central: registro, salud, eventos, pipelines y ciclo maestro."""

    def __init__(self, config: Optional[MasterConfig] = None,
                 handlers: Optional[Dict[str, Callable[..., Any]]] = None) -> None:
        self.config = config or MasterConfig()
        self._lock = threading.RLock()
        self._modules: Dict[str, Callable[..., Dict[str, Any]]] = {}
        self._module_cache: Dict[str, SubmoduleStatus] = {}
        self._events: List[GlobalEvent] = []
        self._handlers: Dict[str, Callable[..., Any]] = dict(handlers or {})
        self._pipelines: List[PipelineRun] = []
        self.cycles = 0
        self.started_at = time.time()

    def register_module(self, name: str, adapter: Callable[..., Dict[str, Any]]) -> None:
        with self._lock:
            self._modules[name] = adapter

    def unregister_module(self, name: str) -> None:
        with self._lock:
            self._modules.pop(name, None)
            self._module_cache.pop(name, None)

    def module_names(self) -> List[str]:
        with self._lock:
            return sorted(self._modules.keys())

    def module_health(self, name: str) -> SubmoduleStatus:
        with self._lock:
            adapter = self._modules.get(name)
        now = time.time()
        st = SubmoduleStatus(name=name, last_check=now)
        if adapter is None:
            st.error = "module not registered"
            return st
        try:
            info = adapter()
            if isinstance(info, dict):
                st.healthy = True
                st.details = info
            else:
                st.healthy = True
                st.details = {"raw": str(info)}
        except Exception as exc:
            st.healthy = False
            st.error = str(exc)
        with self._lock:
            self._module_cache[name] = st
        return st

    def collect_status(self) -> List[SubmoduleStatus]:
        return [self.module_health(n) for n in self.module_names()]

    def emit_event(self, source: str, kind: str, level: str = LEVEL_INFO,
                   payload: Optional[Dict[str, Any]] = None) -> GlobalEvent:
        if level not in _LEVELS:
            level = LEVEL_INFO
        ev = GlobalEvent(event_id=uuid.uuid4().hex[:12], ts=time.time(),
                         source=source, kind=kind, level=level, payload=payload or {})
        ev.decision = self.handle_event(ev)
        with self._lock:
            self._events.append(ev)
            if len(self._events) > self.config.max_events:
                self._events = self._events[-(self.config.max_events // 2):]
        return ev

    def handle_event(self, ev: GlobalEvent) -> str:
        """Respuesta automatica ante incidentes (reglas globales)."""
        if ev.level == LEVEL_CRITICAL:
            return "escalate"
        if ev.level == LEVEL_ERROR:
            return "investigate"
        if ev.level == LEVEL_WARN:
            return "monitor"
        return "acknowledge"

    def events(self, limit: Optional[int] = None, level: Optional[str] = None,
               source: Optional[str] = None) -> List[GlobalEvent]:
        with self._lock:
            items = list(self._events)
        if level:
            items = [e for e in items if e.level == level]
        if source:
            items = [e for e in items if e.source == source]
        if limit:
            items = items[-limit:]
        return items

    def register_handler(self, kind: str, fn: Callable[..., Any]) -> None:
        with self._lock:
            self._handlers[kind] = fn

    def handler_names(self) -> List[str]:
        with self._lock:
            return sorted(self._handlers.keys())

    def _dispatch_step(self, step: PipelineStep) -> PipelineStep:
        fn = self._handlers.get(step.kind)
        if fn is None:
            step.status = "error"
            step.result = f"no handler for kind: {step.kind}"
            return step
        start = time.monotonic()
        try:
            step.result = fn(**step.params) if step.params else fn()
            step.status = "success"
        except Exception as exc:
            step.status = "error"
            step.result = str(exc)
        step.duration_ms = int((time.monotonic() - start) * 1000)
        return step

    def run_pipeline(self, name: str, steps: List[Dict[str, Any]]) -> PipelineRun:
        run = PipelineRun(pipeline_id=uuid.uuid4().hex[:12], name=name,
                          started_at=time.time(), status="running",
                          steps=[PipelineStep(kind=s.get("kind", "noop"),
                                              params=dict(s.get("params") or {}))
                                 for s in steps])
        for step in run.steps:
            self._dispatch_step(step)
            if step.status != "success":
                run.status = "error"
                run.error = f"step '{step.kind}' failed: {step.result}"
                break
        else:
            run.status = "success"
        run.finished_at = time.time()
        with self._lock:
            self._pipelines.append(run)
            if len(self._pipelines) > self.config.max_pipelines:
                self._pipelines = self._pipelines[-(self.config.max_pipelines // 2):]
        return run

    def pipelines(self, limit: Optional[int] = None) -> List[PipelineRun]:
        with self._lock:
            items = list(self._pipelines)
        if limit:
            items = items[-limit:]
        return items

    def run_cycle(self) -> Dict[str, Any]:
        """Ciclo maestro: health de modulos + eventos automaticos por anomalias."""
        self.cycles += 1
        statuses = self.collect_status()
        unhealthy = [s.name for s in statuses if not s.healthy]
        for name in unhealthy:
            st = self.module_health(name)
            self.emit_event(source="orchestrator", kind="module_unhealthy",
                            level=LEVEL_WARN,
                            payload={"module": name, "error": st.error})
        healthy = [s.name for s in statuses if s.healthy]
        return {"cycle": self.cycles, "modules": len(statuses),
                "healthy": healthy, "unhealthy": unhealthy,
                "at": time.time()}

    def status(self) -> Dict[str, Any]:
        with self._lock:
            events = list(self._events)
            pipelines = list(self._pipelines)
            modules = sorted(self._module_cache.keys())
        by_level: Dict[str, int] = {}
        for e in events:
            by_level[e.level] = by_level.get(e.level, 0) + 1
        return {
            "enabled": True,
            "uptime_s": round(time.time() - self.started_at, 2),
            "cycles": self.cycles,
            "modules_registered": self.module_names(),
            "modules_checked": modules,
            "handlers": self.handler_names(),
            "events_total": len(events),
            "events_by_level": by_level,
            "pipelines_total": len(pipelines),
            "last_pipeline": pipelines[-1].to_dict() if pipelines else None,
            "offline_only": True,
        }


_orch: Optional[MasterOrchestrator] = None
_orch_lock = threading.Lock()


def get_master_orchestrator(config: Optional[MasterConfig] = None,
                            handlers: Optional[Dict[str, Callable[..., Any]]] = None) -> MasterOrchestrator:
    global _orch
    if _orch is None:
        with _orch_lock:
            if _orch is None:
                default_handlers: Dict[str, Callable[..., Any]] = {
                    "noop": lambda **kw: {"kind": "noop", "ok": True},
                    "echo": lambda **kw: dict(kw),
                }
                if handlers:
                    default_handlers.update(handlers)
                _orch = MasterOrchestrator(config=config, handlers=default_handlers)
    return _orch


def reset_master_orchestrator() -> None:
    global _orch
    with _orch_lock:
        _orch = None


MasterEngine = MasterOrchestrator
get_master_engine = get_master_orchestrator
reset_master_engine = reset_master_orchestrator
