# -*- coding: utf-8 -*-
"""ARIA OS - Base Environment.

Clase base para todos los entornos especializados de ARIA.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ARIA.Environments.Base")


class BaseEnvironment(ABC):
    """Clase base para entornos especializados."""

    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description
        self.created_at = time.time()
        self.active = False
        self.metrics: Dict[str, Any] = {}
        self.tasks: List[Dict[str, Any]] = []

    @abstractmethod
    def start(self) -> Dict[str, Any]:
        """Inicia el entorno."""
        pass

    @abstractmethod
    def stop(self) -> Dict[str, Any]:
        """Detiene el entorno."""
        pass

    @abstractmethod
    def process(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Procesa una tarea dentro del entorno."""
        pass

    def status(self) -> Dict[str, Any]:
        """Retorna el estado del entorno."""
        return {
            "name": self.name,
            "description": self.description,
            "active": self.active,
            "created_at": self.created_at,
            "uptime": round(time.time() - self.created_at, 2),
            "tasks_count": len(self.tasks),
            "metrics": self.metrics,
        }

    def add_task(self, task: Dict[str, Any]) -> str:
        """Agrega una tarea al entorno."""
        task_id = f"task_{int(time.time())}_{len(self.tasks)}"
        task["task_id"] = task_id
        task["created_at"] = time.time()
        task["status"] = "pending"
        self.tasks.append(task)
        return task_id
