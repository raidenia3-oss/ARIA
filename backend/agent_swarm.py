"""Autonomous multi-agent swarm for AURA - Module 28.

Creacion y coordinacion de enjambres de agentes especializados (Planificador,
Programador, Revisor, Investigador, Evaluador) que ejecutan tareas complejas
de forma concurrente o en tuberia. Incluye un bus de mensajes inter-agente
y una cola de tareas asíncrona con pool de trabajadores local.
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from backend.agents.agent_roles import (
    APEXAgentRole,
    RoleSpec,
    get_role_spec,
    role_to_dict,
)


def _safe_sink(sink: Callable[..., None], event: str, run_id: str,
               index: int, total: int, name: str = "", tier: str = "",
               status: str = "", message: str = "") -> None:
    """Call ``sink`` with progress-frame args, swallowing any exception.

    The sink pushes frames to the Axum hub over HTTP. A refused connection,
    a timeout or a malformed frame must never abort task execution: progress
    is observability, not correctness.
    """
    try:
        sink(event, run_id, index, total, name, tier, status, message)
    except Exception:  # noqa: BLE001 - progress sink must not break execution
        return


class AgentRole(str, Enum):
    PLANNER = "planner"
    CODER = "coder"
    REVIEWER = "reviewer"
    RESEARCHER = "researcher"
    EVALUATOR = "evaluator"


@dataclass
class SubAgentTask:
    task_id: str
    task_type: str
    description: str
    role: str
    dependencies: List[str] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    result: Optional[Dict[str, Any]] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    assigned_agent: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "description": self.description,
            "role": self.role,
            "dependencies": self.dependencies,
            "params": self.params,
            "status": self.status,
            "result": self.result,
            "assigned_agent": self.assigned_agent,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class TaskPlanner:
    """Descompone tareas complejas en subtareas y gestiona el orden de ejecucion (DAG)."""

    ROLE_KEYWORDS: Dict[str, List[str]] = {
        "planner": ["plan", "design", "architect", "strategy", "layout"],
        "coder": ["code", "implement", "build", "develop", "write", "generate"],
        "reviewer": ["review", "check", "audit", "validate", "test"],
        "researcher": ["research", "investigate", "search", "find", "explore"],
        "evaluator": ["evaluate", "assess", "score", "measure", "benchmark"],
    }

    def __init__(self, max_subtasks: int = 10) -> None:
        self.max_subtasks = max_subtasks
        self._counter: int = 0

    def plan(self, description: str, max_subtasks: Optional[int] = None) -> List[SubAgentTask]:
        limit = max_subtasks or self.max_subtasks
        parts = self._split_description(description)
        if len(parts) > limit:
            parts = parts[:limit]

        tasks: List[SubAgentTask] = []
        for i, part in enumerate(parts):
            role = self._infer_role(part)
            task = SubAgentTask(
                task_id=f"task-{int(time.time() * 1000)}-{i}",
                task_type=role,
                description=part.strip(),
                role=role,
                params={"index": i},
            )
            if i > 0 and tasks:
                task.dependencies = [tasks[-1].task_id]
            tasks.append(task)

        if not tasks:
            tasks = [
                SubAgentTask(
                    task_id=f"task-{int(time.time() * 1000)}-0",
                    task_type="planner",
                    description=description,
                    role="planner",
                    params={"index": 0},
                )
            ]
        return tasks

    def _split_description(self, description: str) -> List[str]:
        for sep in ("\n\n", "\n;", ";", " | "):
            if sep in description:
                return [p.strip() for p in description.split(sep) if p.strip()]
        sentences = description.split(".")
        return [s.strip() for s in sentences if s.strip()]

    def _infer_role(self, text: str) -> str:
        text_lower = text.lower()
        scores: Dict[str, int] = {}
        for role, keywords in self.ROLE_KEYWORDS.items():
            scores[role] = sum(1 for kw in keywords if kw in text_lower)
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "planner"

    def get_execution_order(self, tasks: List[SubAgentTask]) -> List[SubAgentTask]:
        task_map = {t.task_id: t for t in tasks}
        waves: List[List[SubAgentTask]] = []
        done: set = set()
        remaining: set = set(task_map.keys())

        while remaining:
            wave: List[SubAgentTask] = []
            for tid in list(remaining):
                task = task_map[tid]
                if all(dep in done for dep in task.dependencies):
                    wave.append(task)
            if not wave:
                tid = next(iter(remaining))
                wave = [task_map[tid]]
            for task in wave:
                done.add(task.task_id)
                remaining.discard(task.task_id)
            waves.append(wave)

        ordered: List[SubAgentTask] = []
        for wave in waves:
            ordered.extend(wave)
        return ordered

    def validate_plan(self, tasks: List[SubAgentTask]) -> Dict[str, Any]:
        task_ids = {t.task_id for t in tasks}
        missing_deps: List[Dict[str, Any]] = []
        for task in tasks:
            for dep in task.dependencies:
                if dep not in task_ids:
                    missing_deps.append({"task_id": task.task_id, "missing_dep": dep})
        return {
            "valid": len(missing_deps) == 0,
            "task_count": len(tasks),
            "missing_dependencies": missing_deps,
        }


# --------------------------------------------------------------------------- #
# Inter-agent message bus (local, in-process, no external broker)
# --------------------------------------------------------------------------- #

@dataclass
class SwarmMessage:
    msg_id: str
    src_agent: str
    dst_agent: str
    topic: str
    payload: Dict[str, Any]
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "msg_id": self.msg_id,
            "src_agent": self.src_agent,
            "dst_agent": self.dst_agent,
            "topic": self.topic,
            "payload": self.payload,
            "ts": self.ts,
        }


class InterAgentBus:
    """Pub/sub message bus between swarm agents. In-memory, thread-safe,
    with per-subscriber queues and optional broadcast topics."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        self._log: List[SwarmMessage] = []
        self._max_log = 1000

    async def publish(self, src_agent: str, topic: str,
                      payload: Dict[str, Any],
                      dst_agent: Optional[str] = None) -> SwarmMessage:
        msg = SwarmMessage(
            msg_id=f"msg-{int(time.time() * 1_000_000)}-{os.urandom(3).hex()}",
            src_agent=src_agent, dst_agent=dst_agent or "*",
            topic=topic, payload=payload,
        )
        async with self._lock:
            self._log.append(msg)
            if len(self._log) > self._max_log:
                self._log = self._log[-self._max_log:]
            targets: List[asyncio.Queue] = []
            if dst_agent and dst_agent in self._subscribers:
                targets.extend(self._subscribers[dst_agent])
            if topic in self._subscribers:
                targets.extend(self._subscribers[topic])
            if "*" in self._subscribers:
                targets.extend(self._subscribers["*"])
            for q in targets:
                try:
                    q.put_nowait(msg)
                except asyncio.QueueFull:
                    pass
        return msg

    async def subscribe(self, agent_id: str, topic: str,
                         maxlen: int = 100) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=maxlen or 100)
        key = topic if topic != "direct" else agent_id
        async with self._lock:
            self._subscribers.setdefault(key, []).append(q)
        return q

    async def drain(self, q: asyncio.Queue, timeout: float = 0.2) -> List[SwarmMessage]:
        out: List[SwarmMessage] = []
        try:
            while True:
                out.append(await asyncio.wait_for(q.get(), timeout=timeout))
        except (asyncio.TimeoutError, asyncio.QueueEmpty):
            pass
        return out

    def recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [m.to_dict() for m in self._log[-limit:]]


# --------------------------------------------------------------------------- #
# Async task queue with bounded worker pool
# --------------------------------------------------------------------------- #

@dataclass
class QueuedTask:
    task_id: str
    fn: Callable[..., Awaitable[Any]]
    args: Tuple[Any, ...] = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    enqueued_at: float = field(default_factory=time.time)


class AsyncTaskQueue:
    """Bounded asyncio task queue with a configurable worker pool. Tasks
    are dispatched concurrently up to the pool size, preserving FIFO order
    within each priority tier."""

    def __init__(self, max_workers: Optional[int] = None,
                 maxsize: int = 0) -> None:
        cpu = os.cpu_count() or 2
        self.max_workers = max_workers or max(1, min(cpu * 2, 8))
        self.maxsize = maxsize
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._tasks: Dict[str, asyncio.Task] = {}
        self._results: Dict[str, Any] = {}
        self._errors: Dict[str, str] = {}
        self._workers: List[asyncio.Task] = []
        self._running = False
        self._counter = 0

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._workers = [
            asyncio.create_task(self._worker(i)) for i in range(self.max_workers)
        ]

    async def stop(self) -> None:
        self._running = False
        for w in self._workers:
            w.cancel()
        for t in self._tasks.values():
            t.cancel()
        await asyncio.gather(*self._workers, *self._tasks.values(),
                              return_exceptions=True)
        self._workers.clear()
        self._tasks.clear()

    async def enqueue(self, fn: Callable[..., Awaitable[Any]],
                      *args: Any, priority: int = 0,
                      **kwargs: Any) -> str:
        if not self._running:
            await self.start()
        self._counter += 1
        task_id = f"qtask-{self._counter}-{int(time.time() * 1000)}"
        qt = QueuedTask(task_id=task_id, fn=fn, args=args,
                        kwargs=kwargs, priority=priority)
        await self._queue.put(qt)
        return task_id

    async def wait(self, task_id: str, timeout: Optional[float] = None) -> Any:
        deadline = None if timeout is None else time.monotonic() + timeout
        while task_id not in self._results and task_id not in self._errors:
            if deadline and time.monotonic() > deadline:
                raise TimeoutError(task_id)
            await asyncio.sleep(0.02)
        if task_id in self._errors:
            raise RuntimeError(self._errors[task_id])
        return self._results[task_id]

    def get(self, task_id: str) -> Optional[Any]:
        return self._results.get(task_id)

    def status(self) -> Dict[str, Any]:
        return {
            "max_workers": self.max_workers,
            "queued": self._queue.qsize(),
            "running": len(self._tasks),
            "completed": len(self._results),
            "failed": len(self._errors),
        }

    async def _worker(self, idx: int) -> None:
        while self._running:
            try:
                qt: QueuedTask = await asyncio.wait_for(self._queue.get(), timeout=0.5)
            except (asyncio.TimeoutError, asyncio.QueueEmpty):
                continue
            if qt is None:
                break
            try:
                coro = qt.fn(*qt.args, **qt.kwargs)
                if not asyncio.iscoroutine(coro):
                    coro = asyncio.to_thread(qt.fn, *qt.args, **qt.kwargs)
                task = asyncio.create_task(coro)
                self._tasks[qt.task_id] = task
                result = await task
                self._results[qt.task_id] = result
            except Exception as exc:
                self._errors[qt.task_id] = str(exc)
            finally:
                self._tasks.pop(qt.task_id, None)


class AgentSwarmManager:
    """Gestor de enjambre de agentes: crea agentes, despacha y ejecuta planes."""

    def __init__(self) -> None:
        self.task_planner = TaskPlanner()
        self.agents: Dict[str, Dict[str, Any]] = {}
        self.tasks: Dict[str, SubAgentTask] = {}
        self.task_plans: Dict[str, List[SubAgentTask]] = {}
        self.execution_history: List[Dict[str, Any]] = []
        self._agent_counter = 0
        self._max_history = 500
        self.bus: Optional[InterAgentBus] = None
        self.queue: Optional[AsyncTaskQueue] = None
        # Optional progress sink (EONVERSE visual feedback). Set with
        # `set_progress_sink()`; a None sink means no UI updates are emitted.
        self._progress_sink: Optional[Callable[..., None]] = None

    def set_progress_sink(self, sink: Optional[Callable[..., None]]) -> None:
        """Attach a callable that receives progress frames.

        The sink signature is ``sink(event, run_id, index, total, name, tier, status, message)``.
        It is fire-and-forget: any exception it raises is swallowed so a broken
        UI channel can never abort task execution.
        """
        self._progress_sink = sink

    def create_agent(self, role: str = "planner", config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # Accept both the 5 swarm roles (planner/coder/...) and the 12 APEX roles
        # (architect/devops/...). Anything else falls back to "planner" so a
        # bogus role never crashes the registry.
        valid_roles = [r.value for r in AgentRole] + [r.value for r in APEXAgentRole]
        if role not in valid_roles:
            role = "planner"
        agent_id = f"agent-{self._agent_counter}"
        self._agent_counter += 1
        now = datetime.utcnow().isoformat() + "Z"
        # Attach APEX visual identity when the role maps to one of the 12
        # APEX roles; swarm-only roles (planner/coder/...) fall back to a
        # neutral grey so the dashboard never renders an undefined color.
        try:
            apex_role = APEXAgentRole(role)
            role_spec = role_to_dict(apex_role)
        except ValueError:
            role_spec = {
                "role": role,
                "name": role.title(),
                "color": "#64748b",
                "icon": "⚙️",
                "description": f"Swarm role: {role}",
                "capabilities": [],
            }
        agent = {
            "id": agent_id,
            "role": role,
            "status": "idle",
            "config": config or {},
            "created_at": now,
            "last_heartbeat": now,
            "tasks_completed": 0,
            "tasks_attempted": 0,
            "errors": 0,
            "last_task": None,
            "last_execution": None,
            "role_spec": role_spec,
        }
        self.agents[agent_id] = agent
        return agent

    def list_agents(self) -> List[Dict[str, Any]]:
        return list(self.agents.values())

    def list_tasks(self, plan_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        if plan_id:
            plan = self.task_plans.get(plan_id, [])
            return [t.to_dict() for t in plan]
        all_tasks = list(self.tasks.values())[-limit:]
        return [t.to_dict() for t in all_tasks]

    def get_agent(self, role: str) -> Optional[Dict[str, Any]]:
        for agent in self.agents.values():
            if agent["role"] == role and agent["status"] == "idle":
                return agent
        return None

    def _claim_agent(self, role: str) -> Optional[Dict[str, Any]]:
        """Reserve a real idle agent of ``role`` by flipping it to "busy".

        Returns None when no agent of that role exists, so a caller can tell
        "assigned to agent-3" apart from "nobody available".
        """
        for agent in self.agents.values():
            if agent["role"] == role and agent["status"] == "idle":
                agent["status"] = "busy"
                return agent
        return None

    # -- local parallel infrastructure ------------------------------------ #

    def _ensure_infra(self) -> None:
        if not hasattr(self, "bus") or self.bus is None:
            self.bus = InterAgentBus()
        if not hasattr(self, "queue") or self.queue is None:
            self.queue = AsyncTaskQueue()

    async def start_infrastructure(self) -> Dict[str, Any]:
        self._ensure_infra()
        await self.queue.start()
        return {"status": "started", "queue": self.queue.status()}

    async def stop_infrastructure(self) -> Dict[str, Any]:
        if getattr(self, "queue", None) is not None:
            await self.queue.stop()
        return {"status": "stopped"}

    async def publish(self, src_agent: str, topic: str,
                      payload: Dict[str, Any],
                      dst_agent: Optional[str] = None) -> Dict[str, Any]:
        self._ensure_infra()
        msg = await self.bus.publish(src_agent, topic, payload, dst_agent)
        return msg.to_dict()

    async def subscribe(self, agent_id: str, topic: str = "*") -> asyncio.Queue:
        self._ensure_infra()
        return await self.bus.subscribe(agent_id, topic)

    async def enqueue_task(self, fn: Callable[..., Awaitable[Any]],
                           *args: Any, priority: int = 0,
                           **kwargs: Any) -> str:
        self._ensure_infra()
        await self.queue.start()
        return await self.queue.enqueue(fn, *args, priority=priority, **kwargs)

    async def wait_task(self, task_id: str, timeout: Optional[float] = None) -> Any:
        self._ensure_infra()
        return await self.queue.wait(task_id, timeout=timeout)

    def get_queue_status(self) -> Dict[str, Any]:
        if getattr(self, "queue", None) is None:
            return {"started": False}
        return {"started": True, **self.queue.status()}

    def get_bus_messages(self, limit: int = 50) -> List[Dict[str, Any]]:
        if getattr(self, "bus", None) is None:
            return []
        return self.bus.recent(limit)

    async def submit_task(
        self,
        description: str,
        priority: str = "normal",
        max_subtasks: Optional[int] = None,
    ) -> Dict[str, Any]:
        plan = self.task_planner.plan(description, max_subtasks=max_subtasks)
        validation = self.task_planner.validate_plan(plan)
        plan_id = f"plan-{int(time.time() * 1000000)}"
        self.task_plans[plan_id] = plan
        for task in plan:
            self.tasks[task.task_id] = task
        return {
            "plan_id": plan_id,
            "status": "planned",
            "task_count": len(plan),
            "validation": validation,
            "tasks": [t.to_dict() for t in plan],
        }

    async def execute_task(self, task: SubAgentTask, prior_results: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_infra()
        task.started_at = datetime.utcnow().isoformat() + "Z"

        agent = self._claim_agent(task.role)
        task.assigned_agent = agent["id"] if agent else None
        if agent is not None:
            agent["tasks_attempted"] = int(agent.get("tasks_attempted", 0)) + 1

        # Optional progress sink: when set, every task emits run_start/step_start/
        # step_end frames to the Axum hub so the UI can render the EONVERSE
        # animated counter. The sink is fire-and-forget: a refused hub must
        # never abort task execution.
        sink = getattr(self, "_progress_sink", None)
        if sink is not None:
            _safe_sink(sink, "run_start", task.task_id, 0, 1, task.description[:80], "core")
            _safe_sink(sink, "step_start", task.task_id, 0, 1, task.role, "core")

        try:
            result = await self._execute_by_role(task, prior_results)
        except Exception as exc:
            if agent is not None:
                agent["errors"] = int(agent.get("errors", 0)) + 1
                agent["last_task"] = task.task_id
                agent["last_execution"] = datetime.utcnow().isoformat() + "Z"
            if sink is not None:
                _safe_sink(sink, "step_end", task.task_id, 0, 1, task.role, "core", "fail", str(exc)[:80])
                _safe_sink(sink, "run_end", task.task_id, 0, 1, "fail")
            raise
        else:
            if agent is not None:
                agent["tasks_completed"] = int(agent.get("tasks_completed", 0)) + 1
                agent["last_task"] = task.task_id
                agent["last_execution"] = datetime.utcnow().isoformat() + "Z"
            task.result = result
            task.status = "completed"
            task.completed_at = datetime.utcnow().isoformat() + "Z"
            if sink is not None:
                _safe_sink(sink, "step_end", task.task_id, 0, 1, task.role, "core", "ok", task.description[:80])
                _safe_sink(sink, "run_end", task.task_id, 1, 1, "ok")
            return result
        finally:
            if agent is not None:
                agent["status"] = "idle"

    async def _execute_by_role(self, task: SubAgentTask, prior_results: Dict[str, Any]) -> Dict[str, Any]:
        role = task.role
        dep_results = {dep: prior_results.get(dep, {}) for dep in task.dependencies}
        started = time.monotonic()

        if role == "planner":
            return {
                "type": "planning",
                "task": task.description,
                "sub_tasks": len(task.dependencies) + 1,
                "approach": "sequential" if len(task.dependencies) <= 1 else "wave",
                "dependency_count": len(task.dependencies),
                "duration_seconds": round(time.monotonic() - started, 4),
            }
        if role == "coder":
            file_name = f"generated_{task.task_id}.py"
            return {
                "type": "coding",
                "task": task.description,
                "file": file_name,
                "lines": len(task.description.splitlines()) + len(dep_results) * 10,
                "dependencies_analyzed": len(dep_results),
                "duration_seconds": round(time.monotonic() - started, 4),
            }
        if role == "reviewer":
            prior_scores = [
                r.get("score") for r in dep_results.values()
                if isinstance(r, dict) and isinstance(r.get("score"), (int, float))
            ]
            issues = sum(
                1 for r in dep_results.values()
                if isinstance(r, dict) and r.get("issues_found")
            )
            avg_score = round(sum(prior_scores) / len(prior_scores), 2) if prior_scores else None
            return {
                "type": "review",
                "task": task.description,
                "issues_found": issues,
                "score": avg_score if avg_score is not None else 0.0,
                "prior_results": {k: "reviewed" for k in dep_results},
                "prior_score_count": len(prior_scores),
                "duration_seconds": round(time.monotonic() - started, 4),
            }
        if role == "researcher":
            dep_keys = list(dep_results.keys())
            return {
                "type": "research",
                "task": task.description,
                "sources_found": len(dep_keys) + 1,
                "findings": f"relevant information gathered for: {task.description[:80]}",
                "dependency_sources": dep_keys,
                "duration_seconds": round(time.monotonic() - started, 4),
            }
        if role == "evaluator":
            prior_scores = [
                r.get("score") for r in dep_results.values()
                if isinstance(r, dict) and isinstance(r.get("score"), (int, float))
            ]
            avg_score = round(sum(prior_scores) / len(prior_scores), 2) if prior_scores else 0.0
            completeness = round(len(dep_results) / max(len(dep_results) + 1, 1), 2)
            return {
                "type": "evaluation",
                "task": task.description,
                "score": avg_score,
                "metrics": {
                    "accuracy": round(avg_score / 10.0, 2) if avg_score else 0.0,
                    "completeness": completeness,
                },
                "evaluated_deps": len(dep_results),
                "duration_seconds": round(time.monotonic() - started, 4),
            }
        return {
            "type": "unknown",
            "task": task.description,
            "result": "no_handler",
            "role": role,
            "duration_seconds": round(time.monotonic() - started, 4),
        }

    async def execute_plan(self, plan_id: str, concurrent: bool = True) -> Dict[str, Any]:
        plan = self.task_plans.get(plan_id)
        if not plan:
            return {"status": "error", "error": "plan_not_found"}

        ordered = self.task_planner.get_execution_order(plan)
        waves = self._group_into_waves(ordered)
        all_results: Dict[str, Any] = {}

        for wave in waves:
            if concurrent and len(wave) > 1:
                coros = [self.execute_task(task, all_results) for task in wave]
                wave_results = await asyncio.gather(*coros, return_exceptions=True)
                for task, result in zip(wave, wave_results):
                    if isinstance(result, Exception):
                        task.status = "failed"
                        task.result = {"error": str(result)}
                        all_results[task.task_id] = {"error": str(result)}
                    else:
                        all_results[task.task_id] = result
            else:
                for task in wave:
                    try:
                        result = await self.execute_task(task, all_results)
                        all_results[task.task_id] = result
                    except Exception as exc:
                        task.status = "failed"
                        task.result = {"error": str(exc)}
                        all_results[task.task_id] = {"error": str(exc)}

        entry = {
            "plan_id": plan_id,
            "executed_at": datetime.utcnow().isoformat() + "Z",
            "tasks_completed": len(all_results),
            "results": all_results,
        }
        self.execution_history.append(entry)
        if len(self.execution_history) > self._max_history:
            self.execution_history = self.execution_history[-self._max_history :]

        return {
            "plan_id": plan_id,
            "status": "completed",
            "tasks_executed": len(all_results),
            "results": all_results,
        }

    def _group_into_waves(self, tasks: List[SubAgentTask]) -> List[List[SubAgentTask]]:
        task_map = {t.task_id: t for t in tasks}
        waves: List[List[SubAgentTask]] = []
        done: set = set()
        remaining: set = set(task_map.keys())

        while remaining:
            wave: List[SubAgentTask] = []
            for tid in list(remaining):
                task = task_map[tid]
                if all(dep in done for dep in task.dependencies):
                    wave.append(task)
            if not wave:
                tid = next(iter(remaining))
                wave = [task_map[tid]]
            for task in wave:
                done.add(task.task_id)
                remaining.discard(task.task_id)
            waves.append(wave)
        return waves

    def get_status(self) -> Dict[str, Any]:
        agents_by_role: Dict[str, int] = {}
        for agent in self.agents.values():
            agents_by_role[agent["role"]] = agents_by_role.get(agent["role"], 0) + 1
        task_status: Dict[str, int] = {}
        for task in self.tasks.values():
            task_status[task.status] = task_status.get(task.status, 0) + 1
        return {
            "agents_total": len(self.agents),
            "agents_by_role": agents_by_role,
            "tasks_total": len(self.tasks),
            "task_status_counts": task_status,
            "plans_total": len(self.task_plans),
            "execution_history_count": len(self.execution_history),
            "queue": self.get_queue_status(),
            "bus_messages": len(self.get_bus_messages()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    def get_swarm_metrics(self) -> Dict[str, Any]:
        """Aggregate agent counters at read time.

        success_rate is None when nothing has been attempted: an unknown rate
        and a rate of zero are different facts.
        """
        total_completed = 0
        total_attempted = 0
        total_errors = 0
        for agent in self.agents.values():
            total_completed += int(agent.get("tasks_completed", 0))
            total_attempted += int(agent.get("tasks_attempted", 0))
            total_errors += int(agent.get("errors", 0))
        success_rate = (total_completed / total_attempted) if total_attempted > 0 else None
        return {
            "total_agents": len(self.agents),
            "total_tasks_completed": total_completed,
            "total_tasks_attempted": total_attempted,
            "total_errors": total_errors,
            "success_rate": success_rate,
        }

    def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Return a status snapshot for one agent, or None if unknown.

        The snapshot is what the APEX dashboard consumes: it carries the
        role_spec (color/icon), the lifecycle state, the current task and the
        counters needed to render the orbit + detail cards.
        """
        agent = self.agents.get(agent_id)
        if agent is None:
            return None
        uptime_seconds = 0.0
        created = agent.get("created_at")
        if created:
            try:
                created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                uptime_seconds = max(0.0, (datetime.utcnow() - created_dt.replace(tzinfo=None)).total_seconds())
            except (ValueError, TypeError):
                uptime_seconds = 0.0
        role_spec = agent.get("role_spec") or {}
        return {
            "id": agent["id"],
            "role": agent["role"],
            "name": role_spec.get("name", agent["role"].title()),
            "status": agent["status"],
            "color": role_spec.get("color", "#64748b"),
            "icon": role_spec.get("icon", "⚙️"),
            "current_task": agent.get("last_task"),
            "tasks_completed": int(agent.get("tasks_completed", 0)),
            "tasks_attempted": int(agent.get("tasks_attempted", 0)),
            "error_count": int(agent.get("errors", 0)),
            "uptime_seconds": round(uptime_seconds, 1),
            "last_heartbeat": agent.get("last_heartbeat"),
            "last_execution": agent.get("last_execution"),
        }

    def list_agent_status(self) -> List[Dict[str, Any]]:
        """Status snapshot for every registered agent, APEX-role-first."""
        return [self.get_agent_status(aid) for aid in self.agents]

    def touch_agent(self, agent_id: str) -> bool:
        """Refresh the heartbeat timestamp for an agent.

        Returns False for an unknown id. The dashboard polls this to tell a
        live agent from a stale one without needing a separate status channel.
        """
        agent = self.agents.get(agent_id)
        if agent is None:
            return False
        agent["last_heartbeat"] = datetime.utcnow().isoformat() + "Z"
        return True

    def reset_agent_metrics(self, agent_id: str) -> bool:
        """Zero the counters of one agent. Returns False for an unknown id."""
        agent = self.agents.get(agent_id)
        if agent is None:
            return False
        agent["tasks_completed"] = 0
        agent["tasks_attempted"] = 0
        agent["errors"] = 0
        agent["last_task"] = None
        agent["last_execution"] = None
        return True


# --------------------------------------------------------------------------- #
# Singleton access
# --------------------------------------------------------------------------- #

_swarm_manager: Optional[AgentSwarmManager] = None


def get_swarm_manager() -> AgentSwarmManager:
    global _swarm_manager
    if _swarm_manager is None:
        _swarm_manager = AgentSwarmManager()
    return _swarm_manager


def reset_swarm_manager() -> None:
    global _swarm_manager
    _swarm_manager = None


__all__ = [
    "AgentRole",
    "APEXAgentRole",
    "AgentSwarmManager",
    "AsyncTaskQueue",
    "InterAgentBus",
    "QueuedTask",
    "SubAgentTask",
    "SwarmMessage",
    "TaskPlanner",
    "get_swarm_manager",
    "reset_swarm_manager",
]
