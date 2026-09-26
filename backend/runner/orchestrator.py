"""BLOQUE 82 - Mission Orchestrator: ciclo de vida de misiones autonomas
con soporte de interrupcion/fondo desde la interfaz visual u overlay."""
import threading
import uuid
from typing import Any, Dict, Optional

from backend.runner.ecosystem import MissionDirective, EcosystemRunner
from backend.runner.handlers import build_default_handlers


class MissionOrchestrator:
    _bg: Dict[str, Dict[str, Any]] = {}

    def __init__(self, runner: Optional[EcosystemRunner] = None) -> None:
        self._lock = threading.Lock()
        self.runner = runner or EcosystemRunner()
        for scope, fn in build_default_handlers().items():
            self.runner.register_handler(scope, fn)

    def synthesize(self, directive: MissionDirective) -> str:
        return self.runner.plan(directive).mission_id

    def launch(self, directive: MissionDirective,
               interrupt_event: Optional[threading.Event] = None,
               background: bool = False) -> Dict[str, Any]:
        interrupt_event = interrupt_event or threading.Event()
        if background:
            tid = uuid.uuid4().hex[:8]
            box: Dict[str, Any] = {}

            def _worker() -> None:
                box["run"] = self.runner.execute(directive, interrupt_event=interrupt_event)
            t = threading.Thread(target=_worker, daemon=True)
            with self._lock:
                self._bg[tid] = {"thread": t, "event": interrupt_event, "box": box}
            t.start()
            return {"mission_id": directive.mission_id, "task_id": tid, "background": True, "status": "launched"}
        else:
            run = self.runner.execute(directive, interrupt_event=interrupt_event)
            return {"mission_id": run.mission_id, "status": run.status,
                    "summary": run.summary.to_dict() if run.summary else None, "offline_only": True}

    def interrupt(self, task_id: str) -> Dict[str, Any]:
        with self._lock:
            info = self._bg.get(task_id)
            if info is None:
                return {"task_id": task_id, "interrupted": False, "reason": "not found"}
            info["event"].set()
            return {"task_id": task_id, "interrupted": True}

    def status(self, task_id: str) -> Dict[str, Any]:
        with self._lock:
            info = self._bg.get(task_id)
            if info is None:
                return {"task_id": task_id, "exists": False}
            run = info["box"].get("run")
            return {"task_id": task_id, "exists": True, "status": (run.status if run else "running")}


_global_orchestrator: Optional[MissionOrchestrator] = None


def get_ecosystem_orchestrator() -> MissionOrchestrator:
    global _global_orchestrator
    if _global_orchestrator is None:
        _global_orchestrator = MissionOrchestrator()
    return _global_orchestrator


def reset_ecosystem_orchestrator() -> None:
    global _global_orchestrator
    _global_orchestrator = None
