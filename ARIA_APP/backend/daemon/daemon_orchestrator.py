"""Daemon Orchestrator - gestiona procesos daemon del sistema."""
from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger("aria.daemon")


class DaemonOrchestrator:
    """Gestiona la vida ciclo de los daemon processes."""

    def __init__(self) -> None:
        self._daemons: dict[str, Any] = {}
        self._running = False
        self.health = self.HealthStatus()

    class HealthStatus:
        """Health tracking for the orchestrator"""
        def __init__(self):
            self.is_running = False
            self.uptime_seconds = 0
            self.last_check = None

    def register(self, name: str, daemon: Any) -> None:
        """Register a daemon for management"""
        self._daemons[name] = daemon

    def start(self) -> None:
        """Start the orchestrator (sync version for app.py)"""
        self._running = True
        self.health.is_running = True
        self.health.last_check = __import__('datetime').datetime.now()
        logger.info("DaemonOrchestrator started")

    def stop(self) -> None:
        """Stop the orchestrator"""
        self._running = False
        self.health.is_running = False
        logger.info("DaemonOrchestrator stopped")

    async def start_all(self) -> None:
        """Start all registered daemons (async)"""
        self._running = True
        for name, d in self._daemons.items():
            try:
                if hasattr(d, "start"):
                    result = d.start()
                    if hasattr(result, "__await__"):
                        await result
                logger.info(f"Daemon '{name}' started")
            except Exception as e:
                logger.error(f"Daemon '{name}' failed: {e}")

    async def stop_all(self) -> None:
        """Stop all registered daemons (async)"""
        self._running = False
        for name, d in self._daemons.items():
            try:
                if hasattr(d, "stop"):
                    result = d.stop()
                    if hasattr(result, "__await__"):
                        await result
                logger.info(f"Daemon '{name}' stopped")
            except Exception as e:
                logger.error(f"Daemon '{name}' stop error: {e}")
