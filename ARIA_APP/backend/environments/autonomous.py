# -*- coding: utf-8 -*-
"""ARIA OS - Autonomous Environment.

Entorno para crear agentes autónomos que hagan muchas tareas al mismo tiempo
y se desplieguen de forma autónoma.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from .base import BaseEnvironment

logger = logging.getLogger("ARIA.Environments.Autonomous")


class AutonomousAgent:
    """Agente autónomo individual."""

    def __init__(self, agent_id: str, name: str, capabilities: List[str]) -> None:
        self.agent_id = agent_id
        self.name = name
        self.capabilities = capabilities
        self.status = "idle"  # idle, busy, completed, error
        self.tasks_completed = 0
        self.tasks_failed = 0
        self.created_at = time.time()
        self.current_task: Optional[Dict[str, Any]] = None

    def assign_task(self, task: Dict[str, Any]) -> bool:
        if self.status != "idle":
            return False
        self.current_task = task
        self.status = "busy"
        return True

    def complete_task(self, success: bool = True) -> None:
        if success:
            self.tasks_completed += 1
        else:
            self.tasks_failed += 1
        self.status = "idle"
        self.current_task = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "capabilities": self.capabilities,
            "status": self.status,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "current_task": self.current_task,
        }


class AutonomousEnvironment(BaseEnvironment):
    """Entorno de agentes autónomos para multi-tarea.

    Funciones:
    - Crear agentes autónomos
    - Asignar tareas a agentes
    - Ejecutar múltiples tareas en paralelo
    - Desplegar agentes de forma autónoma
    """

    def __init__(self) -> None:
        super().__init__(
            name="agentes_autonomos",
            description="Entorno para crear y desplegar agentes autónomos",
        )
        self.agents: Dict[str, AutonomousAgent] = {}
        self.task_queue: List[Dict[str, Any]] = []
        self.completed_tasks: List[Dict[str, Any]] = []

    def start(self) -> Dict[str, Any]:
        self.active = True
        logger.info(f"Environment {self.name} started")
        return self.status()

    def stop(self) -> Dict[str, Any]:
        self.active = False
        return self.status()

    def process(self, task: Dict[str, Any]) -> Dict[str, Any]:
        task_type = task.get("type", "general")

        if task_type == "create_agent":
            return self._create_agent(task)
        if task_type == "assign_task":
            return self._assign_task(task)
        if task_type == "execute_parallel":
            return self._execute_parallel(task)
        if task_type == "agent_status":
            return self._agent_status(task)
        if task_type == "deploy_agent":
            return self._deploy_agent(task)

        return {"status": "error", "error": f"Tipo de tarea desconocido: {task_type}"}

    def _create_agent(self, task: Dict[str, Any]) -> Dict[str, Any]:
        agent_id = str(uuid.uuid4())[:8]
        name = task.get("name", f"Agente-{agent_id}")
        capabilities = task.get("capabilities", ["general"])
        agent = AutonomousAgent(agent_id, name, capabilities)
        self.agents[agent_id] = agent
        return {"status": "ok", "agent": agent.to_dict()}

    def _assign_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        # Encontrar agente disponible
        for agent in self.agents.values():
            if agent.status == "idle":
                agent.assign_task(task)
                return {"status": "ok", "agent_id": agent.agent_id, "assigned": True}
        # Ningún agente disponible, agregar a cola
        self.task_queue.append(task)
        return {"status": "queued", "assigned": False, "message": "Sin agentes disponibles"}

    def _execute_parallel(self, task: Dict[str, Any]) -> Dict[str, Any]:
        tasks = task.get("tasks", [])
        results = []
        for t in tasks:
            result = self._assign_task(t)
            results.append(result)
        return {"status": "ok", "results": results, "total": len(tasks)}

    def _agent_status(self, task: Dict[str, Any]) -> Dict[str, Any]:
        agent_id = task.get("agent_id", "")
        agent = self.agents.get(agent_id)
        if not agent:
            return {"status": "error", "error": "Agente no encontrado"}
        return {"status": "ok", "agent": agent.to_dict()}

    def _deploy_agent(self, task: Dict[str, Any]) -> Dict[str, Any]:
        agent_id = task.get("agent_id", "")
        agent = self.agents.get(agent_id)
        if not agent:
            return {"status": "error", "error": "Agente no encontrado"}
        return {
            "status": "ok",
            "agent_id": agent_id,
            "deployed": True,
            "message": f"Agente {agent.name} desplegado autónomamente",
        }

    def complete_agent_task(self, agent_id: str, success: bool = True) -> None:
        agent = self.agents.get(agent_id)
        if agent:
            agent.complete_task(success)

    def status(self) -> Dict[str, Any]:
        base = super().status()
        base.update({
            "agents": {aid: a.to_dict() for aid, a in self.agents.items()},
            "task_queue": len(self.task_queue),
            "completed_tasks": len(self.completed_tasks),
        })
        return base
