"""Task Manager for AURA/AME automation."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.task_models import TaskModel, TaskStatus, TaskOrigin, TaskStep

logger = logging.getLogger("AURATaskManager")

TASKS_FILE = os.getenv("AURA_TASKS_FILE", "./data/tasks.json")
LEARNED_FILE = os.getenv("AURA_LEARNED_FILE", "./data/learned_procedures.json")


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


class TaskManager:
    def __init__(self) -> None:
        self.tasks: Dict[str, TaskModel] = {}
        self._lock = asyncio.Lock()
        self._running_tasks: Dict[str, asyncio.Task[Any]] = {}
        self._load_tasks()
        self._learned_procedures: Dict[str, Dict[str, Any]] = {}
        self._load_learned()

    def _load_tasks(self) -> None:
        if not os.path.exists(TASKS_FILE):
            return
        try:
            with open(TASKS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data.values():
                try:
                    task = TaskModel(**item)
                    self.tasks[task.task_id] = task
                except Exception as exc:
                    logger.error("Error loading task: %s", exc)
        except Exception as exc:
            logger.error("Error loading tasks file: %s", exc)

    def _save_tasks(self) -> None:
        try:
            _ensure_dir(TASKS_FILE)
            data = {t.task_id: t.model_dump() for t in self.tasks.values()}
            with open(TASKS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as exc:
            logger.error("Error saving tasks: %s", exc)

    def _load_learned(self) -> None:
        if not os.path.exists(LEARNED_FILE):
            return
        try:
            with open(LEARNED_FILE, "r", encoding="utf-8") as f:
                self._learned_procedures = json.load(f)
        except Exception as exc:
            logger.error("Error loading learned procedures: %s", exc)

    def _save_learned(self) -> None:
        try:
            _ensure_dir(LEARNED_FILE)
            with open(LEARNED_FILE, "w", encoding="utf-8") as f:
                json.dump(self._learned_procedures, f, ensure_ascii=False, indent=2, default=str)
        except Exception as exc:
            logger.error("Error saving learned procedures: %s", exc)

    async def create_task(
        self,
        name: str,
        action_type: str,
        goal: str,
        origin: TaskOrigin = TaskOrigin.AURA,
        parameters: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TaskModel:
        task_id = f"task-{int(time.time() * 1000)}-{os.urandom(4).hex()}"
        task = TaskModel(
            task_id=task_id,
            origin=origin,
            name=name,
            action_type=action_type,
            goal=goal,
            parameters=parameters or {},
            session_id=session_id,
            metadata=metadata or {},
        )
        async with self._lock:
            self.tasks[task_id] = task
            self._save_tasks()
        logger.info("Task created: %s (%s)", task_id, name)
        return task

    async def get_task(self, task_id: str) -> Optional[TaskModel]:
        return self.tasks.get(task_id)

    async def list_tasks(self, status: Optional[TaskStatus] = None, origin: Optional[TaskOrigin] = None) -> List[TaskModel]:
        items = list(self.tasks.values())
        if status:
            items = [t for t in items if t.status == status]
        if origin:
            items = [t for t in items if t.origin == origin]
        return sorted(items, key=lambda t: t.created_at, reverse=True)

    async def update_task(self, task_id: str, **updates: Any) -> Optional[TaskModel]:
        task = self.tasks.get(task_id)
        if not task:
            return None
        for key, value in updates.items():
            if hasattr(task, key):
                setattr(task, key, value)
        self._save_tasks()
        return task

    async def cancel_task(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if not task:
            return False
        if task.status in (TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.PAUSED):
            task.status = TaskStatus.CANCELLED
            task.finished_at = datetime.now().isoformat()
            self._save_tasks()
            if task_id in self._running_tasks:
                self._running_tasks[task_id].cancel()
                del self._running_tasks[task_id]
            return True
        return False

    async def _run_task(self, task_id: str, steps: List[Dict[str, Any]]) -> None:
        task = self.tasks.get(task_id)
        if not task:
            return
        task.status = TaskStatus.RUNNING
        task.steps = [TaskStep(**s) for s in steps]
        task.pending_steps = [s.get("step_id") for s in steps]
        self._save_tasks()

        try:
            for step in task.steps:
                if task.status == TaskStatus.CANCELLED:
                    break
                step.status = TaskStatus.RUNNING
                step.started_at = datetime.now().isoformat()
                self._save_tasks()
                try:
                    from backend.services.action_engine import action_engine
                    result = action_engine.execute(step.tool or "run_command", step.params)
                    step.result = result.to_dict()
                    step.status = TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
                    step.error = result.error
                    if step.step_id in task.pending_steps:
                        task.pending_steps.remove(step.step_id)
                    task.progress = max(0.0, min(1.0, 1.0 - len(task.pending_steps) / max(1, len(task.steps))))
                except Exception as exc:
                    step.status = TaskStatus.FAILED
                    step.error = str(exc)
                    logger.error("Task %s step %s failed: %s", task_id, step.step_id, exc)
                step.finished_at = datetime.now().isoformat()
                self._save_tasks()

            if task.status != TaskStatus.CANCELLED:
                task.status = TaskStatus.COMPLETED if all(s.status == TaskStatus.COMPLETED for s in task.steps) else TaskStatus.FAILED
                task.finished_at = datetime.now().isoformat()
                task.progress = 1.0 if task.status == TaskStatus.COMPLETED else task.progress
        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            task.finished_at = datetime.now().isoformat()
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error = str(exc)
            task.finished_at = datetime.now().isoformat()
        finally:
            self._save_tasks()
            self._running_tasks.pop(task_id, None)

    async def start_task(self, task_id: str, steps: Optional[List[Dict[str, Any]]] = None) -> bool:
        task = self.tasks.get(task_id)
        if not task or task.status not in (TaskStatus.PENDING, TaskStatus.PAUSED, TaskStatus.FAILED):
            return False
        if steps:
            task.steps = [TaskStep(**s) for s in steps]
        if not task.steps:
            logger.error("Task %s has no steps", task_id)
            return False
        coro = self._run_task(task_id, [s.model_dump() for s in task.steps])
        self._running_tasks[task_id] = asyncio.create_task(coro)
        return True

    async def pause_task(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if not task or task.status != TaskStatus.RUNNING:
            return False
        if task_id in self._running_tasks:
            self._running_tasks[task_id].cancel()
            del self._running_tasks[task_id]
        task.status = TaskStatus.PAUSED
        self._save_tasks()
        return True

    async def learn_procedure(self, name: str, steps: List[Dict[str, Any]], goal: str) -> Dict[str, Any]:
        proc_id = f"proc-{int(time.time() * 1000)}-{os.urandom(4).hex()}"
        procedure = {
            "procedure_id": proc_id,
            "name": name,
            "goal": goal,
            "steps": steps,
            "created_at": datetime.now().isoformat(),
            "execution_count": 0,
            "last_executed": None,
            "last_error": None,
        }
        self._learned_procedures[proc_id] = procedure
        self._save_learned()
        logger.info("Learned procedure: %s (%s)", proc_id, name)
        return procedure

    async def get_learned_procedures(self) -> List[Dict[str, Any]]:
        return sorted(self._learned_procedures.values(), key=lambda p: p.get("created_at", ""), reverse=True)

    async def get_learned_procedure(self, proc_id: str) -> Optional[Dict[str, Any]]:
        return self._learned_procedures.get(proc_id)

    async def search_procedures(self, query: str) -> List[Dict[str, Any]]:
        q = query.lower()
        results = []
        for proc in self._learned_procedures.values():
            text = json.dumps(proc, ensure_ascii=False).lower()
            if q in text:
                results.append(proc)
        return results

    async def delete_learned_procedure(self, proc_id: str) -> bool:
        if proc_id in self._learned_procedures:
            del self._learned_procedures[proc_id]
            self._save_learned()
            return True
        return False

    async def increment_procedure_execution(self, proc_id: str) -> None:
        proc = self._learned_procedures.get(proc_id)
        if proc:
            proc["execution_count"] = proc.get("execution_count", 0) + 1
            proc["last_executed"] = datetime.now().isoformat()
            self._save_learned()

    async def get_procedure(self, proc_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene un procedimiento individual por ID."""
        return self._learned_procedures.get(proc_id)

    def _resolve_step_params(self, step: Dict[str, Any], params_override: Dict[str, Any]) -> Dict[str, Any]:
        """Resuelve parámetros de un step, aplicando overrides del llamador."""
        params = dict(step.get("params", {}))
        if params_override:
            params.update(params_override)
        return params

    async def run_procedure(
        self, proc_id: str, params_override: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Ejecuta un procedimiento guardado como una tarea con seguimiento de progreso."""
        proc = self._learned_procedures.get(proc_id)
        if not proc:
            raise ValueError(f"Procedure {proc_id} not found")

        params_override = params_override or {}
        steps = proc.get("steps", [])
        if not steps:
            raise ValueError(f"Procedure {proc_id} has no steps")

        resolved_steps = []
        for raw_step in steps:
            resolved_params = self._resolve_step_params(raw_step, params_override)
            resolved_steps.append({
                "step_id": raw_step.get("step_id", f"step_{len(resolved_steps)}"),
                "name": raw_step.get("name", "unnamed"),
                "tool": raw_step.get("tool"),
                "params": resolved_params,
            })

        task = await self.create_task(
            name=proc.get("name", "procedure_execution"),
            action_type="automation",
            goal=proc.get("goal", ""),
            parameters={"procedure_id": proc_id},
        )

        await self.start_task(task.task_id, steps=resolved_steps)
        return {"task_id": task.task_id, "procedure_id": proc_id}

    async def create_workflow(
        self, name: str, procedure_ids: List[str], goal: str = ""
    ) -> str:
        """Crea un workflow compuesto a partir de varios procedimientos."""
        missing = [pid for pid in procedure_ids if pid not in self._learned_procedures]
        if missing:
            raise ValueError(f"Unknown procedure IDs: {missing}")

        wf_steps = []
        for pid in procedure_ids:
            proc = self._learned_procedures[pid]
            for step in proc.get("steps", []):
                wf_steps.append({
                    "step_id": step.get("step_id"),
                    "name": step.get("name", "unnamed"),
                    "tool": step.get("tool"),
                    "params": step.get("params", {}),
                })

        task = await self.create_task(
            name=name,
            action_type="automation",
            goal=goal or f"Workflow: {name}",
            parameters={"procedure_ids": procedure_ids, "is_workflow": True},
        )
        logger.info("Created workflow %s from procedures: %s", task.task_id, procedure_ids)
        task.parameters["steps"] = wf_steps
        self._save_tasks()
        return task.task_id

    async def run_workflow(self, workflow_id: str, params_override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Ejecuta un workflow previamente creado (por task_id)."""
        task = self.tasks.get(workflow_id)
        if not task:
            raise ValueError(f"Workflow {workflow_id} not found")

        wf_steps = task.parameters.get("steps", [])
        if not wf_steps:
            proc_ids = task.parameters.get("procedure_ids", [])
            if not proc_ids:
                raise ValueError(f"Workflow {workflow_id} has no steps or procedures")
            missing = [pid for pid in proc_ids if pid not in self._learned_procedures]
            if missing:
                raise ValueError(f"Unknown procedure IDs in workflow: {missing}")
            for pid in proc_ids:
                proc = self._learned_procedures[pid]
                for step in proc.get("steps", []):
                    wf_steps.append({
                        "step_id": step.get("step_id"),
                        "name": step.get("name", "unnamed"),
                        "tool": step.get("tool"),
                        "params": step.get("params", {}),
                    })

        params_override = params_override or {}
        resolved_steps = []
        for step in wf_steps:
            step_dict = dict(step)
            resolved_params = self._resolve_step_params(step_dict, params_override)
            resolved_steps.append({
                "step_id": step_dict.get("step_id", f"step_{len(resolved_steps)}"),
                "name": step_dict.get("name", "unnamed"),
                "tool": step_dict.get("tool"),
                "params": resolved_params,
            })

        await self.start_task(workflow_id, steps=resolved_steps)
        return {"task_id": workflow_id, "workflow": True}

    async def capture_task_to_procedure(
        self, task_id: str, name: str, goal: Optional[str] = None
    ) -> Dict[str, Any]:
        """Captura los pasos de una tarea completada y la guarda como procedimiento reutilizable."""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        if task.status != TaskStatus.COMPLETED:
            raise ValueError(f"Task {task_id} is not completed (status={task.status})")
        if not task.steps:
            raise ValueError(f"Task {task_id} has no steps to capture")

        steps_serializado: List[Dict[str, Any]] = []
        for step in task.steps:
            step_dict = step.model_dump()
            steps_serializado.append({
                "step_id": step.step_id,
                "name": step.name,
                "tool": step.tool,
                "params": step.params,
                "result": step.result or {},
            })

        proc_goal = goal or task.goal or f"Procedimiento capturado de: {task.name}"
        procedure = await self.learn_procedure(name=name, steps=steps_serializado, goal=proc_goal)
        procedure["source_task_id"] = task_id
        procedure["captured_from"] = task.name
        self._save_learned()
        logger.info("Captured procedure from task %s: %s", task_id, procedure["procedure_id"])
        return procedure


task_manager = TaskManager()
