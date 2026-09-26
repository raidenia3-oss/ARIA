# -*- coding: utf-8 -*-
"""
AURA OS - Chunk 2: Executor Agent.

Ejecuta comandos locales (sandbox basico) y llama a las APIs de AURA
para realizar acciones del sistema (status, health, scan, etc).
"""
from __future__ import annotations

import logging
import os
import subprocess
from typing import Any, Dict, List, Optional

import httpx

from backend.agent.swarm_base import BaseAgent, AgentRegistry
from backend.core.event_bus import CoreEvent, EventType, get_event_bus

logger = logging.getLogger("AURA.Agent.Executor")


class ExecutorAgent(BaseAgent):
    """Agente executor: comandos locales + llamadas a APIs de AURA."""

    # Comandos autorizados (sandbox basico)
    SAFE_COMMANDS: List[str] = [
        "echo", "ls", "dir", "pwd", "whoami", "python --version",
        "git status", "git log", "date", "uname",
        "curl -s localhost:8000/api/core/health",
        "curl -s localhost:8000/api/core/status",
    ]

    def __init__(self, session_id: str = "", bus=None, api_base: str = "") -> None:
        super().__init__(name="executor_agent", session_id=session_id, bus=bus)
        self.api_base = api_base or os.getenv("AURA_API_URL", "http://localhost:8000")

    # ------------------------------------------------------------------
    # Comandos locales
    # ------------------------------------------------------------------
    def _is_safe(self, cmd: str) -> bool:
        """Verifica si el comando esta en la lista de comandos seguros."""
        cmd = cmd.strip()
        for safe in self.SAFE_COMMANDS:
            if cmd == safe or cmd.startswith(safe + " "):
                return True
        return False

    def _run_command(self, cmd: str, timeout: float = 10.0) -> Dict[str, Any]:
        """Ejecuta un comando local (sandbox basico)."""
        if not self._is_safe(cmd):
            self._emit_action("unauthorized_command", {"command": cmd})
            return {"success": False, "error": "Comando no autorizado",
                    "command": cmd, "stdout": "", "stderr": "", "returncode": -1}

        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=timeout,
            )
            self._emit_action("command_executed", {
                "command": cmd, "success": result.returncode == 0,
                "returncode": result.returncode,
            })
            return {
                "command": cmd,
                "success": result.returncode == 0,
                "stdout": result.stdout[:500],
                "stderr": result.stderr[:500],
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timeout",
                    "command": cmd, "stdout": "", "stderr": "", "returncode": -1}
        except Exception as exc:
            return {"success": False, "error": str(exc),
                    "command": cmd, "stdout": "", "stderr": "", "returncode": -1}

    # ------------------------------------------------------------------
    # APIs de AURA
    # ------------------------------------------------------------------
    def _execute_aura_api(self, endpoint: str, method: str = "GET",
                          data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Llama a una API de AURA (FastAPI)."""
        url = f"{self.api_base}{endpoint}"
        self.emit_thought("api_call", {"url": url, "method": method})
        try:
            with httpx.Client(timeout=15.0) as client:
                if method.upper() == "POST":
                    resp = client.post(url, json=data or {})
                else:
                    resp = client.get(url)
                ct = resp.headers.get("content-type", "")
                parsed = resp.json() if ct.startswith("application/json") else resp.text[:500]
                self._emit_action("api_result", {"url": url, "status": resp.status_code})
                return {"url": url, "method": method, "status": resp.status_code, "data": parsed}
        except Exception as exc:
            logger.warning("Executor API error: %s", exc)
            return {"url": url, "method": method, "status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    def _emit_action(self, detail_type: str, detail: Dict[str, Any]) -> None:
        """Emite evento ACTION al EventBus."""
        self._bus.emit(CoreEvent(
            type=EventType.ACTION,
            data={"agent": self.name, "detail_type": detail_type,
                  "detail": detail, "session_id": self.session_id},
            agent=self.name, status="running",
        ))

    # ------------------------------------------------------------------
    def _do_execute(self, task: str, **kwargs) -> Dict[str, Any]:
        """Ejecuta un comando o llama a una API segun el action."""
        action = kwargs.get("action", "command")

        if action == "api":
            endpoint = kwargs.get("endpoint", "/api/core/status")
            method = kwargs.get("method", "GET")
            data = kwargs.get("data")
            result = self._execute_aura_api(endpoint, method, data)
            self.report_progress(100.0, "API ejecutada")
            return result

        # Default: ejecutar como comando local
        cmd = kwargs.get("command", task)
        self.emit_thought("command", {"command": cmd, "sandbox": "basico"})
        result = self._run_command(cmd)
        self.report_progress(100.0, "comando ejecutado")
        return result


AgentRegistry.register("executor_agent", ExecutorAgent)

