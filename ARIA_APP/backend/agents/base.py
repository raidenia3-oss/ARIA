# -*- coding: utf-8 -*-
"""ARIA OS - Agent Base Class.

Provides the abstract Agent interface and AgentSwarm orchestrator
for parallel task execution across specialized agents.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ARIA.Agents")


class Agent(ABC):
    """Base class for all ARIA specialized agents."""

    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role
        self.status = "idle"
        self.last_task: Optional[Dict[str, Any]] = None
        self.created_at = datetime.now()
        self.task_count = 0
        self.error_count = 0

    @abstractmethod
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a specific task. Must be implemented by subclasses."""
        pass

    async def work(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task with status tracking and error handling."""
        self.status = "working"
        self.last_task = task
        self.task_count += 1
        try:
            result = await self.execute(task)
            self.status = "idle"
            return {
                "agent": self.name,
                "role": self.role,
                "status": "success",
                "result": result,
            }
        except Exception as e:
            self.status = "error"
            self.error_count += 1
            logger.error(f"Agent {self.name} failed: {e}")
            return {
                "agent": self.name,
                "role": self.role,
                "status": "error",
                "error": str(e),
            }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "status": self.status,
            "created_at": str(self.created_at),
            "task_count": self.task_count,
            "error_count": self.error_count,
        }


class AgentSwarm:
    """Orchestrates multiple agents with parallel task execution."""

    def __init__(self, name: str = "ARIA-Swarm"):
        self.name = name
        self.agents: List[Agent] = []
        self.task_queue: List[Dict[str, Any]] = []
        self.history: List[Dict[str, Any]] = []
        # Per-agent locks for thread-safe state mutation (Rust Arc<Mutex> pattern)
        self._locks: Dict[str, "asyncio.Lock"] = {}

    def _get_lock(self, agent_name: str) -> "asyncio.Lock":
        """Get or create an asyncio.Lock for an agent (thread-safe state)."""
        if agent_name not in self._locks:
            self._locks[agent_name] = asyncio.Lock()
        return self._locks[agent_name]

    def register_agent(self, agent: Agent):
        """Register an agent in the swarm."""
        self.agents.append(agent)
        self._locks[agent.name] = asyncio.Lock()
        logger.info(f"Registered agent: {agent.name} ({agent.role})")

    def unregister_agent(self, name: str):
        """Remove an agent by name."""
        self.agents = [a for a in self.agents if a.name != name]
        self._locks.pop(name, None)

    def get_agent(self, name: str) -> Optional[Agent]:
        """Get an agent by name."""
        for a in self.agents:
            if a.name == name:
                return a
        return None

    async def execute_parallel(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute multiple tasks in parallel using round-robin distribution.

        Each agent's state is protected by an asyncio.Lock (Rust Arc<Mutex> pattern).
        Tasks without an 'agent' key are distributed round-robin.
        """
        if not self.agents:
            return [{"status": "error", "error": "No agents registered"}]

        # Build coroutines with per-agent locks for state safety
        coros = []
        for i, task in enumerate(tasks):
            agent_name = task.get("agent")
            agent = self.get_agent(agent_name) if agent_name else None
            if agent is None:
                agent = self.agents[i % len(self.agents)]
            lock = self._get_lock(agent.name)
            coros.append(self._execute_locked(agent, task, lock))

        results = await asyncio.gather(*coros, return_exceptions=True)

        # Normalize results
        normalized = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                normalized.append({
                    "agent": "unknown",
                    "status": "error",
                    "error": str(r),
                })
            else:
                normalized.append(r)

        self.history.extend(normalized)
        # Keep history bounded
        if len(self.history) > 1000:
            self.history = self.history[-1000:]

        return normalized

    async def _execute_locked(self, agent: Agent, task: Dict[str, Any], lock: "asyncio.Lock") -> Dict[str, Any]:
        """Execute a task on an agent with state protection (Rust Arc<Mutex> pattern)."""
        async with lock:
            return await agent.work(task)

    async def execute_sequential(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute tasks sequentially (each task may depend on previous results)."""
        results = []
        for task in tasks:
            agent_name = task.get("agent")
            agent = self.get_agent(agent_name) if agent_name else None
            if agent is None and self.agents:
                agent = self.agents[0]
            if agent is None:
                results.append({"status": "error", "error": "No agent available"})
                continue
            result = await agent.work(task)
            results.append(result)
        self.history.extend(results)
        return results

    def status(self) -> Dict[str, Any]:
        """Return swarm status."""
        return {
            "name": self.name,
            "agents": len(self.agents),
            "agent_list": [a.to_dict() for a in self.agents],
            "tasks_pending": len(self.task_queue),
            "history_size": len(self.history),
        }

    def clear_history(self):
        """Clear task history."""
        self.history = []