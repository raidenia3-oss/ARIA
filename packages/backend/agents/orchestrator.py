"""AURA Local Autonomous Task Orchestrator & Reasoning Loop (Bloque 55)."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shlex
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from backend.agent.memory_store import (
    AgentMemoryStore, ExecutionTrace, TraceOutcome, get_agent_memory,
)

logger = logging.getLogger("AURA.Agent.Orchestrator")


class TaskStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    RUNNING = "running"
    EVALUATING = "evaluating"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class ToolResultStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    EMPTY = "empty"
    TIMEOUT = "timeout"


@dataclass
class ToolResult:
    tool: str
    status: ToolResultStatus
    output: str = ""
    error: str = ""
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReasoningStep:
    step_id: str
    iteration: int
    thought: str
    action: str
    tool: str
    result: Optional[ToolResult] = None
    evaluation: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class AgentTask:
    task_id: str
    objective: str
    context: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    plan: List[Dict[str, Any]] = field(default_factory=list)
    steps: List[ReasoningStep] = field(default_factory=list)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    max_iterations: int = 10
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ToolConnector:
    """Conector unificado a herramientas de consola, navegador y vision."""

    def __init__(self) -> None:
        self._os = None
        self._gui = None
        self._browser = None
        self._screen = None
        self._registry = None

    def _get_registry(self):
        """Dynamic tool registry (Bloque 56) — lazy singleton."""
        if self._registry is None:
            try:
                from backend.agents.tools_registry import get_tools_registry
                self._registry = get_tools_registry()
            except Exception as exc:
                logger.debug("tools registry unavailable: %s", exc)
        return self._registry

    def _get_os(self):
        if self._os is None:
            try:
                from backend.automation.os_controller import os_controller
                self._os = os_controller
            except Exception as exc:
                logger.debug("os_controller import failed: %s", exc)
        return self._os

    def _get_gui(self):
        if self._gui is None:
            try:
                from backend.gui_automation_engine import ComputerUseAgent
                self._gui = ComputerUseAgent()
            except Exception as exc:
                logger.debug("gui engine import failed: %s", exc)
        return self._gui

    def _get_browser(self):
        if self._browser is None:
            try:
                from backend.automation.browser_agent import browser_agent
                self._browser = browser_agent
            except Exception as exc:
                logger.debug("browser agent import failed: %s", exc)
        return self._browser

    def _get_screen(self):
        if self._screen is None:
            try:
                from backend.vision.screen_bridge import screen_bridge
                self._screen = screen_bridge
            except Exception as exc:
                logger.debug("screen bridge import failed: %s", exc)
        return self._screen

    async def execute(self, tool: str, params: Dict[str, Any]) -> ToolResult:
        start = time.perf_counter()
        try:
            if tool == "shell":
                return await self._shell_action(params)
            if tool == "read_file":
                return self._read_file(params)
            if tool == "write_file":
                return self._write_file(params)
            if tool == "list_dir":
                return self._list_dir(params)
            if tool == "os":
                return await self._os_action(params)
            if tool == "gui":
                return await self._gui_action(params)
            if tool == "browser":
                return await self._browser_action(params)
            if tool == "vision":
                return await self._vision_action(params)
            # Bloque 56: fall back to the dynamic skill registry for custom tools.
            registry = self._get_registry()
            if registry is not None and registry.has(tool):
                return await self._registry_action(tool, params)
            return ToolResult(tool=tool, status=ToolResultStatus.FAILED, error=f"unknown tool: {tool}")
        finally:
            pass

    async def _registry_action(self, tool: str, params: Dict[str, Any]) -> ToolResult:
        start = time.perf_counter()
        registry = self._get_registry()
        try:
            result = await registry.execute_tool(tool, dict(params or {}))
            status = ToolResultStatus.SUCCESS if result.get("success") else ToolResultStatus.FAILED
            return ToolResult(
                tool=tool,
                status=status,
                output=str(result.get("output", "")),
                error=str(result.get("error", "")),
                duration_ms=float(result.get("duration_ms", (time.perf_counter() - start) * 1000.0)),
                metadata={"source": "dynamic_registry"},
            )
        except Exception as exc:
            return ToolResult(tool=tool, status=ToolResultStatus.FAILED, error=str(exc))

    async def _shell_action(self, params: Dict[str, Any]) -> ToolResult:
        cmd = str(params.get("command", "")).strip()
        timeout = float(params.get("timeout", 30))
        if not cmd:
            return ToolResult(tool="shell", status=ToolResultStatus.FAILED, error="empty command")
        start = time.perf_counter()
        try:
            proc = await asyncio.create_subprocess_exec(
                "cmd", "/c", cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            out = (stdout or b"").decode("utf-8", errors="replace")
            err = (stderr or b"").decode("utf-8", errors="replace")
            ok = proc.returncode == 0
            return ToolResult(
                tool="shell",
                status=ToolResultStatus.SUCCESS if ok else ToolResultStatus.FAILED,
                output=out.strip()[:4000],
                error="" if ok else f"exit={proc.returncode} {err[:200]}",
                duration_ms=(time.perf_counter() - start) * 1000.0,
            )
        except asyncio.TimeoutError:
            return ToolResult(tool="shell", status=ToolResultStatus.TIMEOUT, error=f"timeout after {timeout}s")
        except Exception as exc:
            return ToolResult(tool="shell", status=ToolResultStatus.FAILED, error=str(exc))

    async def _os_action(self, params: Dict[str, Any]) -> ToolResult:
        os_ctrl = self._get_os()
        if os_ctrl is None:
            return ToolResult(tool="os", status=ToolResultStatus.FAILED, error="os controller unavailable")
        try:
            kind = str(params.get("kind", "status"))
            if kind == "status":
                out = os_ctrl.get_status()
            else:
                out = await os_ctrl.execute_action(params)
            return ToolResult(tool="os", status=ToolResultStatus.SUCCESS, output=str(out))
        except Exception as exc:
            return ToolResult(tool="os", status=ToolResultStatus.FAILED, error=str(exc))

    async def _gui_action(self, params: Dict[str, Any]) -> ToolResult:
        gui = self._get_gui()
        if gui is None:
            return ToolResult(tool="gui", status=ToolResultStatus.FAILED, error="gui engine unavailable")
        try:
            result = await gui.execute_command(str(params.get("command", "")))
            return ToolResult(tool="gui", status=ToolResultStatus.SUCCESS, output=str(result))
        except Exception as exc:
            return ToolResult(tool="gui", status=ToolResultStatus.FAILED, error=str(exc))

    async def _browser_action(self, params: Dict[str, Any]) -> ToolResult:
        browser = self._get_browser()
        if browser is None:
            return ToolResult(tool="browser", status=ToolResultStatus.FAILED, error="browser agent unavailable")
        try:
            if hasattr(browser, "navigate"):
                await browser.navigate(str(params.get("url", "")))
            return ToolResult(tool="browser", status=ToolResultStatus.SUCCESS, output="ok")
        except Exception as exc:
            return ToolResult(tool="browser", status=ToolResultStatus.FAILED, error=str(exc))

    async def _vision_action(self, params: Dict[str, Any]) -> ToolResult:
        screen = self._get_screen()
        if screen is None:
            return ToolResult(tool="vision", status=ToolResultStatus.FAILED, error="screen bridge unavailable")
        try:
            if hasattr(screen, "describe"):
                desc = await screen.describe()
                return ToolResult(tool="vision", status=ToolResultStatus.SUCCESS, output=str(desc))
            return ToolResult(tool="vision", status=ToolResultStatus.FAILED, error="no describe method")
        except Exception as exc:
            return ToolResult(tool="vision", status=ToolResultStatus.FAILED, error=str(exc))

    def _read_file(self, params: Dict[str, Any]) -> ToolResult:
        path = str(params.get("path", ""))
        if not path or not Path(path).is_file():
            return ToolResult(tool="read_file", status=ToolResultStatus.FAILED, error="file not found")
        try:
            content = Path(path).read_text(encoding="utf-8", errors="replace")
            return ToolResult(tool="read_file", status=ToolResultStatus.SUCCESS, output=content)
        except Exception as exc:
            return ToolResult(tool="read_file", status=ToolResultStatus.FAILED, error=str(exc))

    def _write_file(self, params: Dict[str, Any]) -> ToolResult:
        path = str(params.get("path", ""))
        content = str(params.get("content", ""))
        if not path:
            return ToolResult(tool="write_file", status=ToolResultStatus.FAILED, error="empty path")
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return ToolResult(tool="write_file", status=ToolResultStatus.SUCCESS, output=f"{len(content)} bytes written")
        except Exception as exc:
            return ToolResult(tool="write_file", status=ToolResultStatus.FAILED, error=str(exc))

    def _list_dir(self, params: Dict[str, Any]) -> ToolResult:
        path = str(params.get("path", "."))
        try:
            p = Path(path)
            if not p.is_dir():
                return ToolResult(tool="list_dir", status=ToolResultStatus.FAILED, error="not a directory")
            entries = sorted([e.name for e in p.iterdir()])
            return ToolResult(tool="list_dir", status=ToolResultStatus.SUCCESS, output="\n".join(entries))
        except Exception as exc:
            return ToolResult(tool="list_dir", status=ToolResultStatus.FAILED, error=str(exc))


class VibeCodingOrchestrator:
    """Orquestador autónomo Plan-Execute-Evaluate 100% local."""

    def __init__(
        self,
        state_dir: Optional[str] = None,
        ai_router: Any = None,
        tool_connector: Optional[ToolConnector] = None,
        max_parallel: int = 4,
        memory: Optional[AgentMemoryStore] = None,
    ) -> None:
        base = state_dir or os.getenv("AURA_AGENT_STATE_DIR", os.path.join("data", "agent_tasks"))
        self.state_dir = Path(base)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.ai_router = ai_router
        self.tools = tool_connector or ToolConnector()
        self.max_parallel = max(1, int(max_parallel))
        self.tasks: Dict[str, AgentTask] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self.memory = memory or get_agent_memory()
        self._load_all()

    def _task_file(self, task_id: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_-]", "_", task_id)[:64] or "task"
        return self.state_dir / f"{safe}.json"

    def _task_to_dict(self, task: AgentTask) -> Dict[str, Any]:
        return {
            "task_id": task.task_id,
            "objective": task.objective,
            "context": task.context,
            "status": task.status.value,
            "plan": task.plan,
            "steps": [
                {
                    "step_id": s.step_id,
                    "iteration": s.iteration,
                    "thought": s.thought,
                    "action": s.action,
                    "tool": s.tool,
                    "result": {
                        "tool": s.result.tool,
                        "status": s.result.status.value,
                        "output": s.result.output,
                        "error": s.result.error,
                        "duration_ms": s.result.duration_ms,
                        "metadata": s.result.metadata,
                    } if s.result else None,
                    "evaluation": s.evaluation,
                    "timestamp": s.timestamp,
                }
                for s in task.steps
            ],
            "result": task.result,
            "error": task.error,
            "max_iterations": task.max_iterations,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "metadata": task.metadata,
        }

    def _save_task(self, task: AgentTask) -> None:
        try:
            self._task_file(task.task_id).write_text(
                json.dumps(self._task_to_dict(task), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.debug("task persist failed %s: %s", task.task_id, exc)

    def _load_all(self) -> None:
        try:
            for f in sorted(self.state_dir.glob("*.json")):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    self._restore_task(data)
                except Exception as exc:
                    logger.debug("skip corrupt task file %s: %s", f.name, exc)
        except Exception as exc:
            logger.debug("task dir load failed: %s", exc)

    def _restore_task(self, data: Dict[str, Any]) -> None:
        try:
            status = TaskStatus(str(data.get("status", "pending")))
        except ValueError:
            status = TaskStatus.PENDING
        steps: List[ReasoningStep] = []
        for raw in data.get("steps", []) or []:
            res = None
            rraw = raw.get("result")
            if isinstance(rraw, dict):
                try:
                    rstatus = ToolResultStatus(str(rraw.get("status", "failed")))
                except ValueError:
                    rstatus = ToolResultStatus.FAILED
                res = ToolResult(
                    tool=str(rraw.get("tool", "")),
                    status=rstatus,
                    output=str(rraw.get("output", "")),
                    error=str(rraw.get("error", "")),
                    duration_ms=float(rraw.get("duration_ms", 0.0)),
                    metadata=dict(rraw.get("metadata", {}) or {}),
                )
            steps.append(ReasoningStep(
                step_id=str(raw.get("step_id", uuid.uuid4().hex[:8])),
                iteration=int(raw.get("iteration", 0)),
                thought=str(raw.get("thought", "")),
                action=str(raw.get("action", "")),
                tool=str(raw.get("tool", "")),
                result=res,
                evaluation=str(raw.get("evaluation", "")),
                timestamp=float(raw.get("timestamp", time.time())),
            ))
        self.tasks[str(data.get("task_id", ""))] = AgentTask(
            task_id=str(data.get("task_id", "")),
            objective=str(data.get("objective", "")),
            context=dict(data.get("context", {}) or {}),
            status=status,
            plan=list(data.get("plan", []) or []),
            steps=steps,
            result=data.get("result"),
            error=data.get("error"),
            max_iterations=int(data.get("max_iterations", 10)),
            created_at=float(data.get("created_at", time.time())),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            metadata=dict(data.get("metadata", {}) or {}),
        )

    def _lock_for(self, task_id: str) -> asyncio.Lock:
        lock = self._locks.get(task_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[task_id] = lock
        return lock

    def create_task(self, objective: str, context: Optional[Dict[str, Any]] = None, max_iterations: int = 10) -> AgentTask:
        task_id = f"agent-{int(time.time() * 1000)}-{uuid.uuid4().hex[:6]}"
        task = AgentTask(
            task_id=task_id,
            objective=(objective or "").strip(),
            context=dict(context or {}),
            max_iterations=max(1, int(max_iterations)),
        )
        self.tasks[task_id] = task
        self._save_task(task)
        return task

    def get_task(self, task_id: str) -> Optional[AgentTask]:
        return self.tasks.get(task_id)

    def list_tasks(self, status: Optional[str] = None) -> List[AgentTask]:
        items = list(self.tasks.values())
        if status:
            items = [t for t in items if t.status.value == status]
        return sorted(items, key=lambda t: t.created_at, reverse=True)

    def available_tools(self) -> List[str]:
        """Names of every tool the connector can dispatch, including Bloque 56 registry."""
        names = {"shell", "read_file", "write_file", "list_dir", "os", "gui", "browser", "vision"}
        registry = self.tools._get_registry() if hasattr(self.tools, "_get_registry") else None
        if registry is not None:
            names.update(registry._entries.keys())
        return sorted(names)

    def plan_task(self, task: AgentTask) -> List[Dict[str, Any]]:
        task.status = TaskStatus.PLANNING
        low = task.objective.lower()
        plan: List[Dict[str, Any]] = []
        counter = [0]

        def _add(name: str, tool: str, params: Optional[Dict[str, Any]] = None, parallel_group: Optional[str] = None) -> None:
            counter[0] += 1
            plan.append({
                "step_id": f"s{counter[0]}",
                "name": name,
                "tool": tool,
                "params": dict(params or {}),
                "parallel_group": parallel_group,
            })

        # Bloque 56: if the objective names a registered custom tool, dispatch to it.
        registry = self.tools._get_registry() if hasattr(self.tools, "_get_registry") else None
        if registry is not None:
            for entry in registry._entries.values():
                short = entry.name.split(".")[-1]
                if short in low and len(short) > 3:
                    _add(
                        f"Ejecutar habilidad especializada '{entry.name}'",
                        entry.name,
                        dict(task.context or {}).get("params", {}),
                    )
                    task.plan = plan
                    self._save_task(task)
                    return plan

        if any(k in low for k in ("crear proyecto", "create project", "proyecto", "project", "scaffold")):
            _add("Explorar directorio objetivo", "list_dir", {"path": "."})
            _add("Leer manifiesto existente", "read_file", {"path": "README.md"}, parallel_group="g1")
            _add("Crear estructura base del proyecto", "write_file", {"path": "proyecto/README.md", "content": f"# {task.objective}\n"}, parallel_group="g1")
            _add("Verificar estructura creada", "list_dir", {"path": "proyecto"})
        elif any(k in low for k in ("investigar", "research", "buscar", "search", "analizar url", "leer web")):
            _add("Explorar contexto local", "list_dir", {"path": "."})
            _add("Consultar estado del sistema", "os", {"kind": "status"}, parallel_group="web")
            _add("Leer fuente web indicada", "browser", {"url": (task.context or {}).get("url", "")}, parallel_group="web")
            _add("Sintetizar hallazgos en nota local", "write_file", {"path": "investigacion/notas.md", "content": task.objective})
        elif any(k in low for k in ("automatizar", "automate", "script", "flujo", "workflow")):
            _add("Inspeccionar directorio de trabajo", "list_dir", {"path": "."})
            _add("Crear script de automatización", "write_file", {"path": "automatizacion/tarea.md", "content": task.objective})
            _add("Registrar verificación del flujo", "shell", {"command": "echo aura-agent-check", "timeout": 10})
        else:
            _add("Explorar contexto de trabajo", "list_dir", {"path": "."})
            _add("Ejecutar diagnóstico local", "shell", {"command": "echo aura-agent-check", "timeout": 10}, parallel_group="p1")
            _add("Leer estado del sistema", "os", {"kind": "status"}, parallel_group="p1")
            _add("Consolidar resultado en informe", "write_file", {"path": "agent_runs/informe.md", "content": task.objective})

        task.plan = plan
        self._save_task(task)
        return plan

    def _evaluate_result(self, result: ToolResult) -> str:
        if result.status == ToolResultStatus.SUCCESS:
            if not result.output.strip():
                return "Éxito técnico pero salida vacía: continuar con verificación."
            return "Éxito: avance válido, continuar con el siguiente paso."
        if result.status == ToolResultStatus.TIMEOUT:
            return "Timeout: reintentar con alcance menor o comando más simple."
        return f"Fallo ({result.error or 'sin detalle'}): ajustar parámetros y reintentar una vez."

    async def run_task(self, task_id: str) -> AgentTask:
        task = self.tasks.get(task_id)
        if not task:
            raise KeyError(f"task_not_found: {task_id}")
        lock = self._lock_for(task_id)
        async with lock:
            if task.status == TaskStatus.RUNNING:
                return task
            if task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
                return task
            task.started_at = task.started_at or time.time()
            task.status = TaskStatus.RUNNING
            self._save_task(task)
            if not task.plan:
                self.plan_task(task)
            await self._run_plan(task)
            return task

    async def _run_plan(self, task: AgentTask) -> None:
        task.status = TaskStatus.RUNNING
        groups: Dict[Optional[str], List[Dict[str, Any]]] = {}
        ordered: List[Optional[str]] = []
        for item in task.plan:
            key = item.get("parallel_group")
            if key not in groups:
                groups[key] = []
                ordered.append(key)
            groups[key].append(item)
        iteration = len(task.steps)
        for key in ordered:
            if task.status not in (TaskStatus.RUNNING, TaskStatus.RETRYING):
                break
            items = groups[key]
            if key is None or len(items) == 1:
                for item in items:
                    if task.status not in (TaskStatus.RUNNING, TaskStatus.RETRYING):
                        break
                    iteration += 1
                    await self._run_step(task, item, iteration)
                    if iteration >= task.max_iterations:
                        task.status = TaskStatus.FAILED
                        task.error = "max_iterations alcanzado"
                        break
            else:
                iteration = await self._run_parallel_group(task, items, iteration)
                if iteration >= task.max_iterations:
                    task.status = TaskStatus.FAILED
                    task.error = "max_iterations alcanzado"
                    break
        if task.status in (TaskStatus.RUNNING, TaskStatus.RETRYING, TaskStatus.EVALUATING):
            failed = [s for s in task.steps if s.result and s.result.status != ToolResultStatus.SUCCESS]
            if failed and iteration < task.max_iterations and any(
                "reintentar" in (s.evaluation or "").lower() or "timeout" in (s.evaluation or "").lower() for s in failed
            ):
                task.status = TaskStatus.RETRYING
                task.error = f"{len(failed)} pasos requieren revisión"
            elif failed:
                task.status = TaskStatus.FAILED
                task.error = "; ".join((s.result.error or s.tool) for s in failed[:3])
            else:
                task.status = TaskStatus.COMPLETED
                task.result = {
                    "summary": f"Objetivo '{task.objective}' completado en {len(task.steps)} pasos.",
                    "steps_completed": len(task.steps),
                    "completed_at": datetime.now().isoformat(),
                }
        task.completed_at = time.time()
        self._save_task(task)
        self._record_task_trace(task)

    def _record_task_trace(self, task: AgentTask) -> None:
        try:
            failed = [s for s in task.steps if s.result and s.result.status != ToolResultStatus.SUCCESS]
            if task.status == TaskStatus.COMPLETED:
                outcome = TraceOutcome.SUCCESS
            elif task.status == TaskStatus.FAILED:
                outcome = TraceOutcome.FAILED
            elif task.status == TaskStatus.CANCELLED:
                outcome = TraceOutcome.PARTIAL
            else:
                outcome = TraceOutcome.PARTIAL
            correction = ""
            if failed:
                corrections = []
                for s in failed[:3]:
                    if s.evaluation:
                        corrections.append(f"{s.tool}: {s.evaluation}")
                correction = "; ".join(corrections)
            steps_data = []
            for s in task.steps:
                steps_data.append({
                    "step_id": s.step_id,
                    "iteration": s.iteration,
                    "thought": s.thought,
                    "action": s.action,
                    "tool": s.tool,
                    "result": {
                        "status": s.result.status.value if s.result else None,
                        "output": (s.result.output or "")[:500] if s.result else "",
                        "error": s.result.error if s.result else "",
                    } if s.result else None,
                    "evaluation": s.evaluation,
                })
            trace = ExecutionTrace(
                trace_id=f"trace-{task.task_id}",
                task_id=task.task_id,
                objective=task.objective,
                outcome=outcome,
                steps=steps_data,
                error=task.error or "",
                correction=correction,
                duration_ms=(task.completed_at - (task.started_at or task.created_at)) * 1000.0,
                metadata={"max_iterations": task.max_iterations},
            )
            self.memory.record_trace(trace)
        except Exception as exc:
            logger.debug("trace record failed: %s", exc)

    async def _run_step(self, task: AgentTask, item: Dict[str, Any], iteration: int) -> ReasoningStep:
        task.status = TaskStatus.RUNNING
        thought = f"Iteración {iteration}: {item.get('name', item.get('step_id', ''))} con {item.get('tool', '')}."
        step = ReasoningStep(
            step_id=str(item.get("step_id", f"s{iteration}")),
            iteration=iteration,
            thought=thought,
            action=str(item.get("name", "")),
            tool=str(item.get("tool", "")),
        )
        task.steps.append(step)
        self._save_task(task)
        result = await self.tools.execute(step.tool, dict(item.get("params", {}) or {}))
        step.result = result
        task.status = TaskStatus.EVALUATING
        step.evaluation = self._evaluate_result(result)
        task.status = TaskStatus.RUNNING
        self._save_task(task)
        return step

    async def _run_parallel_group(self, task: AgentTask, items: List[Dict[str, Any]], iteration: int) -> int:
        bounded = items[: max(1, self.max_parallel)]
        results = await asyncio.gather(*[
            self._run_step(task, item, iteration + idx + 1) for idx, item in enumerate(bounded)
        ])
        for extra in items[len(bounded):]:
            iteration += 1
            if iteration >= task.max_iterations:
                break
            await self._run_step(task, extra, iteration)
        return iteration + len(results)

    async def pause_task(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if not task or task.status != TaskStatus.RUNNING:
            return False
        task.status = TaskStatus.PAUSED
        task.error = "pausada por el operador"
        self._save_task(task)
        return True

    def pause_task_sync(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if not task or task.status != TaskStatus.RUNNING:
            return False
        task.status = TaskStatus.PAUSED
        task.error = "pausada por el operador"
        self._save_task(task)
        return True

    async def resume_task(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if not task or task.status != TaskStatus.PAUSED:
            return False
        task.status = TaskStatus.RUNNING
        task.error = None
        self._save_task(task)
        await self._run_plan(task)
        return True

    async def cancel_task(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if not task:
            return False
        task.status = TaskStatus.CANCELLED
        task.error = task.error or "cancelada por el operador"
        task.completed_at = time.time()
        self._save_task(task)
        return True

    async def retry_task(self, task_id: str, max_iterations: Optional[int] = None) -> bool:
        task = self.tasks.get(task_id)
        if not task:
            return False
        if max_iterations:
            task.max_iterations = max(1, int(max_iterations))
        task.status = TaskStatus.RETRYING
        task.error = None
        self._save_task(task)
        await self._run_plan(task)
        return True

    def delete_task(self, task_id: str) -> bool:
        task = self.tasks.pop(task_id, None)
        if task is None:
            return False
        try:
            self._task_file(task_id).unlink(missing_ok=True)
        except Exception:
            pass
        return True

    def status(self) -> Dict[str, Any]:
        """Estado global del orquestador."""
        by_status: Dict[str, int] = {}
        for t in self.tasks.values():
            by_status[t.status.value] = by_status.get(t.status.value, 0) + 1
        return {
            "state_dir": str(self.state_dir),
            "tasks_total": len(self.tasks),
            "tasks_by_status": by_status,
            "max_parallel": self.max_parallel,
            "timestamp": datetime.now().isoformat(),
        }

    def status_dict(self, task: AgentTask) -> Dict[str, Any]:
        done = sum(1 for s in task.steps if s.result and s.result.status == ToolResultStatus.SUCCESS)
        total = max(1, len(task.plan) or len(task.steps) or 1)
        return {
            "task_id": task.task_id,
            "objective": task.objective,
            "status": task.status.value,
            "progress": round(done / total, 3),
            "iterations": len(task.steps),
            "max_iterations": task.max_iterations,
            "plan": task.plan,
            "steps": [
                {
                    "step_id": s.step_id,
                    "iteration": s.iteration,
                    "thought": s.thought,
                    "action": s.action,
                    "tool": s.tool,
                    "result": {
                        "status": s.result.status.value if s.result else None,
                        "output": (s.result.output or "")[:2000] if s.result else "",
                        "error": s.result.error if s.result else "",
                    } if s.result else None,
                    "evaluation": s.evaluation,
                }
                for s in task.steps
            ],
            "result": task.result,
            "error": task.error,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
        }

    async def query_llm(self, prompt: str, system_prompt: str = "Eres AURA, un planificador autónomo local.") -> str:
        router = self.ai_router
        if router is None:
            try:
                from backend.ai_router import AIRouter
                router = AIRouter()
                self.ai_router = router
            except Exception:
                return ""
        try:
            out = await router.generate_response(prompt=prompt, context={}, system_prompt=system_prompt, max_tokens=256)
            text = str((out or {}).get("message", "")).strip()
            return text
        except Exception as exc:
            logger.debug("llm local no disponible: %s", exc)
            return ""

    def inject_experience_context(self, query: str, max_results: int = 3) -> str:
        """Busca experiencias previas similares y las inyecta como contexto few-shot."""
        try:
            return self.memory.build_few_shot_context(query, max_results=max_results)
        except Exception as exc:
            logger.debug("experience inject failed: %s", exc)
            return ""

    def search_experiences(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Busca trazas de ejecución previas similares por similitud vectorial."""
        try:
            return self.memory.search_experiences(query, max_results=max_results)
        except Exception as exc:
            logger.debug("experience search failed: %s", exc)
            return []

    def record_manual_trace(
        self,
        objective: str,
        outcome: str,
        steps: Optional[List[Dict[str, Any]]] = None,
        error: str = "",
        correction: str = "",
        task_id: str = "",
    ) -> str:
        """Registra una traza de ejecución manual o externa."""
        try:
            trace = ExecutionTrace(
                trace_id=f"trace-manual-{int(time.time() * 1000)}-{uuid.uuid4().hex[:6]}",
                task_id=task_id or f"manual-{int(time.time() * 1000)}",
                objective=objective,
                outcome=TraceOutcome(str(outcome)) if outcome in ("success", "failed", "corrected", "partial") else TraceOutcome.PARTIAL,
                steps=steps or [],
                error=error,
                correction=correction,
            )
            return self.memory.record_trace(trace)
        except Exception as exc:
            logger.debug("manual trace record failed: %s", exc)
            return ""


_orchestrator: Optional[VibeCodingOrchestrator] = None


def get_orchestrator(state_dir: Optional[str] = None, ai_router: Any = None) -> VibeCodingOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = VibeCodingOrchestrator(state_dir=state_dir, ai_router=ai_router)
    return _orchestrator


def reset_orchestrator() -> None:
    global _orchestrator
    _orchestrator = None


vibe_orchestrator: VibeCodingOrchestrator = get_orchestrator()
