"""
Self-healing daemon for AURA workers.

Monitorea tareas de automatización (Playwright/Selenium). Si detecta un worker
congelado/inactivo por más tiempo del umbral, mata los procesos de navegador,
libera recursos y relanza el worker limpiamente.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import time
from datetime import datetime
from typing import Optional, Dict, Any

import psutil

logger = logging.getLogger(__name__)


class SelfHealingDaemon:
    def __init__(
        self,
        task_manager: Any,
        inactivity_threshold: int = 120,
        check_interval: int = 15,
    ) -> None:
        self._task_manager = task_manager
        self._inactivity_threshold = inactivity_threshold
        self._check_interval = check_interval
        self._last_activity: Dict[str, float] = {}
        self._last_url: Dict[str, str] = {}
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None

    def record_activity(self, task_name: str, url: str = "") -> None:
        self._last_activity[task_name] = time.time()
        if url:
            self._last_url[task_name] = url

    def _kill_browser_processes(self) -> None:
        try:
            current_pid = os.getpid()
            parent = psutil.Process(current_pid)
            for child in parent.children(recursive=True):
                try:
                    name = child.name().lower()
                    if any(
                        token in name
                        for token in [
                            "chromium", "chrome", "msedge", "firefox", "webdriver"
                        ]
                    ):
                        logger.warning("Killing stale browser process: %s (pid=%s)", name, child.pid)
                        child.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
                    logger.debug("Browser kill skipped: %s", exc)
        except Exception as exc:
            logger.error("Error killing browser processes: %s", exc)

    async def _heal_worker(self, task_name: str) -> None:
        logger.info("Self-healing triggered for worker: %s", task_name)

        # 1) Cancelar tarea colgada
        try:
            status = self._task_manager.status()
            task_info = status.get(task_name, {})
            logger.info("Worker %s status before heal: %s", task_name, task_info)
        except Exception as exc:
            logger.debug("No se pudo obtener status: %s", exc)

        try:
            self._task_manager.stop_survey_bot()
        except Exception as exc:
            logger.error("Error deteniendo worker %s: %s", task_name, exc)

        # 2) Matar procesos de navegador
        self._kill_browser_processes()

        # 3) Relanzar worker limpiamente
        await asyncio.sleep(1.0)
        try:
            start_url = self._last_url.get(task_name) or "https://example.com/survey"
            result = self._task_manager.start_survey_bot(start_url)
            logger.info("Worker %s relanzado: %s", task_name, result)
            self._last_activity[task_name] = time.time()
        except Exception as exc:
            logger.error("No se pudo relanzar el worker %s: %s", task_name, exc)

    async def _monitor_loop(self) -> None:
        self._running = True
        logger.info("Self-healing daemon started (threshold=%ss, interval=%ss)", self._inactivity_threshold, self._check_interval)

        while self._running:
            try:
                now = time.time()
                for task_name, last_ts in list(self._last_activity.items()):
                    if now - last_ts > self._inactivity_threshold:
                        logger.warning(
                            "Worker %s inactive for %ss -> healing",
                            task_name,
                            int(now - last_ts),
                        )
                        await self._heal_worker(task_name)
            except Exception as exc:
                logger.error("Error in self-healing monitor loop: %s", exc)

            await asyncio.sleep(self._check_interval)

    async def start(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._running = True
            self._worker_task = asyncio.create_task(self._monitor_loop())

    async def stop(self) -> None:
        self._running = False
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        self._worker_task = None
        logger.info("Self-healing daemon stopped")
