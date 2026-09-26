# -*- coding: utf-8 -*-
"""AURA OS — Extended Daemon (Phase C).

13 parallel tasks: 10 original + 3 new (storage, triggers, browser pool).
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.automation.browser_pool import browser_pool
from backend.automation.trigger_engine import trigger_engine
from backend.storage.usb_storage_manager import usb_storage_manager
from backend.storage.storage_manager import storage_manager

logger = logging.getLogger("AURA.DaemonExt")


class AuraDaemonExtended:
    """Extended daemon with 13 parallel tasks."""

    def __init__(self) -> None:
        self.active: bool = False
        self.started_at: float = 0.0
        self.task_count: int = 13
        self.task_names: List[str] = [
            "research", "optimization", "monitor", "sync", "revenue",
            "learning", "autoconfig", "swarm", "marketplace", "automation",
            "storage-manager", "trigger-engine", "browser-pool",
        ]
        self.storage_stats: Dict[str, Any] = {}
        self.trigger_stats: Dict[str, Any] = {}
        self.browser_stats: Dict[str, Any] = {}

    async def start(self) -> None:
        self.active = True
        self.started_at = time.time()
        logger.info("Extended daemon started with %d tasks", self.task_count)
        tasks = [
            self._task_storage_manager(),
            self._task_trigger_engine(),
            self._task_browser_pool(),
        ]
        await asyncio.gather(*tasks)

    async def _task_storage_manager(self) -> None:
        while self.active:
            try:
                self.storage_stats = storage_manager.get_storage_summary()
                logger.debug("Storage: %d MB total", self.storage_stats.get("total_mb", 0))
            except Exception as exc:
                logger.debug("Storage task: %s", exc)
            await asyncio.sleep(300)

    async def _task_trigger_engine(self) -> None:
        while self.active:
            try:
                trigger_engine.check_all()
                self.trigger_stats = trigger_engine.get_stats()
                logger.debug("Triggers: %d conditions, %d events",
                             self.trigger_stats.get("total_conditions", 0),
                             self.trigger_stats.get("total_events", 0))
            except Exception as exc:
                logger.debug("Trigger task: %s", exc)
            await asyncio.sleep(trigger_engine.CHECK_INTERVAL)

    async def _task_browser_pool(self) -> None:
        while self.active:
            try:
                self.browser_stats = browser_pool.get_pool_status()
                stale = browser_pool.cleanup_stale()
                if stale:
                    logger.info("Cleaned %d stale browser sessions", len(stale))
            except Exception as exc:
                logger.debug("Browser pool task: %s", exc)
            await asyncio.sleep(60)

    def get_status(self) -> Dict[str, Any]:
        return {
            "active": self.active,
            "total_tasks": self.task_count,
            "task_names": self.task_names,
            "uptime_seconds": round(time.time() - self.started_at, 1) if self.started_at else 0,
            "storage": self.storage_stats,
            "triggers": self.trigger_stats,
            "browser_pool": self.browser_stats,
        }


aura_daemon_extended = AuraDaemonExtended()
