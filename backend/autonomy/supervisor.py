"""
AURA Autonomy Layer
===================

Supervisión de procesos en segundo plano. Garantiza que las funciones
autónomas nunca se detengan silenciosamente: si un bucle de larga duración
lanza una excepción inesperada, el supervisor la reinicia con *backoff*
exponencial y registra el incidente. El estado es observable sin abrir un
navegador vía ``GET /api/system/autonomy`` (o vía las métricas de Prometheus
en el puerto 8001).

Diseño:
- ``AutonomousSupervisor.run(name, coro_factory)`` programa la corutina como
  tarea. Nunca lanza hacia el emisor: siempre envuelve ``create_task`` por
  dentro, replicando la semántica segura del antiguo ``asyncio.create_task``.
- Cada servicio mantiene: ``running``, ``crashes`` (reinicios), ``last_error``
  y ``last_restart`` (epoch) para auditoría offline.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, Dict, Optional

logger = logging.getLogger("AURA.Autonomy")

_SERVICE_RESTART_DELAY = 0.25


class AutonomousSupervisor:
    """Reinicio automático y observabilidad de servicios asíncronos de fondo."""

    def __init__(self, backoff_base: float = 2.0, max_backoff: float = 60.0) -> None:
        self._backoff_base = backoff_base
        self._max_backoff = max_backoff
        self._tasks: Dict[str, "asyncio.Task[Any]"] = {}
        self._status: Dict[str, Dict[str, Any]] = {}

    def run(self, name: str, coro_factory: Callable[[], Awaitable[Any]], *, restart: bool = True) -> None:
        """Programa ``coro_factory()`` como servicio autónomo."""
        if name in self._tasks and not self._tasks[name].done():
            logger.warning("AutonomousSupervisor: '%s' ya estaba activo; se reemplaza.", name)
            self._tasks[name].cancel()
        now = time.time()
        self._status[name] = {
            "running": True,
            "crashes": 0,
            "last_error": None,
            "last_restart": None,
            "started_at": now,
        }
        self._tasks[name] = asyncio.create_task(self._loop(name, coro_factory, restart))
        logger.info("AutonomousSupervisor: servicio '%s' registrado (autónomo).", name)

    def cancel(self, name: str) -> bool:
        task = self._tasks.get(name)
        if task is None:
            return False
        if not task.done():
            task.cancel()
        st = self._status.get(name)
        if st is not None:
            st["running"] = False
        return True

    async def _loop(self, name: str, coro_factory: Callable[[], Awaitable[Any]], restart: bool) -> None:
        while True:
            crashed = False
            try:
                await coro_factory()
            except asyncio.CancelledError:
                self._status[name]["running"] = False
                raise
            except Exception as exc:
                crashed = True
                st = self._status[name]
                st["crashes"] += 1
                st["last_error"] = f"{type(exc).__name__}: {exc}"
                st["last_restart"] = time.time()
                logger.exception("AutonomousSupervisor: '%s' falló (incidente #%d).", name, st["crashes"])
                if not restart:
                    st["running"] = False
                    return
            else:
                if not restart:
                    self._status[name]["running"] = False
                    return
                logger.info("AutonomousSupervisor: '%s' terminó sin error; manteniendo servicio.", name)
                await asyncio.sleep(_SERVICE_RESTART_DELAY)
                continue

            if crashed:
                st = self._status[name]
                exponent = min(st["crashes"] - 1, 5)
                backoff = min(self._max_backoff, self._backoff_base * (2 ** exponent))
                logger.info("AutonomousSupervisor: reiniciando '%s' en %.1fs.", name, backoff)
                await asyncio.sleep(backoff)

    def status(self) -> Dict[str, Dict[str, Any]]:
        snapshot: Dict[str, Dict[str, Any]] = {}
        for name, st in self._status.items():
            task = self._tasks.get(name)
            done = task is None or task.done()
            snapshot[name] = {**st, "running": bool(st.get("running", False) and not done)}
        return snapshot


_supervisor: Optional[AutonomousSupervisor] = None


def get_supervisor() -> AutonomousSupervisor:
    global _supervisor
    if _supervisor is None:
        _supervisor = AutonomousSupervisor()
    return _supervisor
