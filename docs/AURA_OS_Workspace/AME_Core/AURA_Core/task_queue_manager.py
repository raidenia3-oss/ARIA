"""
AURA Task Queue Manager - Sistema de cola de tareas en memoria
"""

import asyncio
import json
import time
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
import threading


class TaskStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Task:
    def __init__(self, task_id: str, task_type: str, payload: Dict):
        self.task_id = task_id
        self.task_type = task_type
        self.payload = payload
        self.status = TaskStatus.PENDING
        self.created_at = datetime.now().isoformat()
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None
        self.result: Optional[Dict] = None
        self.error: Optional[str] = None
        self.progress: int = 0

    def to_dict(self):
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "payload": self.payload,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
            "progress": self.progress,
        }


class TaskQueueManager:
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.lock = threading.Lock()
        self._task_counter = 0

    def _generate_task_id(self) -> str:
        with self.lock:
            self._task_counter += 1
            return f"task_{int(time.time())}_{self._task_counter}"

    def enqueue(self, task_type: str, payload: Dict) -> Task:
        task_id = self._generate_task_id()
        task = Task(task_id, task_type, payload)
        with self.lock:
            self.tasks[task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        with self.lock:
            return self.tasks.get(task_id)

    def get_all_tasks(self, limit: int = 50) -> List[Dict]:
        with self.lock:
            sorted_tasks = sorted(self.tasks.values(), key=lambda t: t.created_at, reverse=True)
            return [task.to_dict() for task in sorted_tasks[:limit]]

    def get_tasks_by_status(self, status: TaskStatus, limit: int = 50) -> List[Dict]:
        with self.lock:
            filtered = [t for t in self.tasks.values() if t.status == status]
            sorted_tasks = sorted(filtered, key=lambda t: t.created_at, reverse=True)
            return [task.to_dict() for task in sorted_tasks[:limit]]

    def update_status(
        self,
        task_id: str,
        status: TaskStatus,
        result: Optional[Dict] = None,
        error: Optional[str] = None,
    ):
        with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                return False

            task.status = status
            if status == TaskStatus.RUNNING and not task.started_at:
                task.started_at = datetime.now().isoformat()
            if status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                task.completed_at = datetime.now().isoformat()
            if result:
                task.result = result
            if error:
                task.error = error
            return True

    def update_progress(self, task_id: str, progress: int):
        with self.lock:
            task = self.tasks.get(task_id)
            if task:
                task.progress = min(max(progress, 0), 100)

    def cancel_task(self, task_id: str) -> bool:
        with self.lock:
            task = self.tasks.get(task_id)
            if task and task.status == TaskStatus.PENDING:
                task.status = TaskStatus.FAILED
                task.error = "Cancelled by user"
                task.completed_at = datetime.now().isoformat()
                return True
            return False


# Instancia singleton
_task_queue = TaskQueueManager()


def get_task_queue() -> TaskQueueManager:
    return _task_queue
