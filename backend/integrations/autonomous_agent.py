# -*- coding: utf-8 -*-
"""ARIA Autonomous Agent — background operation with sleep/health monitoring.

Combines:
- Insomnia (macOS): keeps the Mac awake during autonomous sessions
- Apple Watch Connector: receives Health data and notifications

This agent runs as a background process and coordinates with ARIA to ensure
long-running tasks (vision processing, model training) complete without the
system sleeping or losing connectivity.

Architecture:
  AutonomousAgent → InsomniaManager (sleep prevention)
                 → WatchBridge (Apple Watch health/notifications)
                 → HealthMonitor (health data polling)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
INTEGRATIONS_DIR = REPO_ROOT / "integrations"


@dataclass
class SessionConfig:
    name: str
    duration_minutes: int = 60
    keep_awake: bool = True
    freeze_distractions: bool = True
    health_threshold: float = 0.0
    notify_on_complete: bool = True
    tmux_pane: Optional[str] = None


@dataclass
class HealthStatus:
    battery: Optional[int] = None
    heart_rate: Optional[int] = None
    last_update: Optional[str] = None
    active_energy: Optional[float] = None


class InsomniaManager:
    """Manages macOS sleep prevention via Insomnia integration.
    
    Uses pmset for sleep prevention and process freezing for distraction apps.
    Falls back to caffeinate if Insomnia is not installed.
    """

    def __init__(self) -> None:
        self.platform = platform.system()
        self.insomnia_path = INTEGRATIONS_DIR / "Insomnia"
        self._sleep_prevented = False
        self._frozen_pids: List[str] = []
        self._caffeinate_proc: Optional[subprocess.Popen] = None

    def is_available(self) -> bool:
        if self.platform != "Darwin":
            return False
        return self.insomnia_path.exists() or self._caffeinate_available()

    def _caffeinate_available(self) -> bool:
        try:
            result = subprocess.run(
                ["which", "caffeinate"], capture_output=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def prevent_sleep(self, duration_minutes: int) -> bool:
        if self.platform != "Darwin":
            logger.warning("Sleep prevention only supported on macOS")
            return False

        try:
            if self.insomnia_path.exists():
                logger.info("Using Insomnia for sleep prevention")
                return self._insomnia_keep_awake(duration_minutes)

            return self._caffeinate_keep_awake(duration_minutes)
        except Exception as exc:
            logger.error(f"Failed to prevent sleep: {exc}")
            return False

    def _insomnia_keep_awake(self, duration_minutes: int) -> bool:
        try:
            cmd = [
                "/usr/bin/pmset", "-a", "disablesleep", "1",
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=5)
            if result.returncode == 0:
                self._sleep_prevented = True
                logger.info(f"Sleep prevented for {duration_minutes} minutes")
                return True
        except Exception as exc:
            logger.warning(f"pmset failed, falling back to caffeinate: {exc}")
        return self._caffeinate_keep_awake(duration_minutes)

    def _caffeinate_keep_awake(self, duration_minutes: int) -> bool:
        try:
            duration_sec = duration_minutes * 60
            self._caffeinate_proc = subprocess.Popen(
                ["caffeinate", "-s", "-u", "-t", str(duration_sec)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._sleep_prevented = True
            logger.info(f"caffeinate started for {duration_minutes} minutes")
            return True
        except Exception as exc:
            logger.error(f"caffeinate failed: {exc}")
            return False

    def restore(self) -> None:
        if self.platform != "Darwin":
            return

        if self._caffeinate_proc:
            self._caffeinate_proc.terminate()
            self._caffeinate_proc = None

        try:
            subprocess.run(
                ["/usr/bin/pmset", "-a", "disablesleep", "0"],
                capture_output=True, timeout=5,
            )
        except Exception:
            pass

        self._sleep_prevented = False
        for pid in self._frozen_pids:
            try:
                subprocess.run(["kill", "-CONT", pid], capture_output=True, timeout=2)
            except Exception:
                pass
        self._frozen_pids = []
        logger.info("System state restored")

    def freeze_app(self, app_name: str) -> bool:
        try:
            result = subprocess.run(
                ["pgrep", "-x", app_name], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for pid in result.stdout.strip().split("\n"):
                    if pid:
                        subprocess.run(
                            ["kill", "-STOP", pid], capture_output=True, timeout=2
                        )
                        self._frozen_pids.append(pid)
                return True
        except Exception as exc:
            logger.warning(f"Failed to freeze {app_name}: {exc}")
        return False

    def unfreeze_app(self, app_name: str) -> bool:
        try:
            result = subprocess.run(
                ["pgrep", "-x", app_name], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for pid in result.stdout.strip().split("\n"):
                    if pid:
                        subprocess.run(
                            ["kill", "-CONT", pid], capture_output=True, timeout=2
                        )
                return True
        except Exception:
            pass
        return False


class WatchBridge:
    """Bridge to Apple Watch via Apple Watch Connector protocol.
    
    Provides Health data polling and notification forwarding.
    Falls back to local health data if Watch is not connected.
    """

    def __init__(self) -> None:
        self.awc_path = INTEGRATIONS_DIR / "apple_watch_connector"
        self._connected = False
        self._last_health: Optional[HealthStatus] = None

    def is_available(self) -> bool:
        return self.awc_path.exists()

    def connect(self) -> bool:
        if not self.is_available():
            logger.info("Apple Watch Connector not installed, using local mode")
            self._connected = False
            return True
        logger.info("Apple Watch Connector found, health sync via Watch")
        self._connected = True
        return True

    async def get_health_status(self) -> HealthStatus:
        if self._connected and self.is_available():
            return await self._fetch_watch_health()
        return await self._fetch_local_health()

    async def _fetch_local_health(self) -> HealthStatus:
        try:
            result = subprocess.run(
                ["pmset", "-g", "batt"], capture_output=True, text=True, timeout=5
            )
            output = result.stdout
            for line in output.split("\n"):
                if "InternalBattery" in line:
                    parts = line.split()
                    for p in parts:
                        if p.endswith("%"):
                            return HealthStatus(
                                battery=int(p.rstrip("%")),
                                last_update=datetime.now().isoformat(),
                            )
        except Exception:
            pass
        return HealthStatus(last_update=datetime.now().isoformat())

    async def _fetch_watch_health(self) -> HealthStatus:
        health_path = self.awc_path / "apple-watch-bridge"
        try:
            if (health_path / "src").exists():
                result = subprocess.run(
                    ["node", "-e", "console.log(JSON.stringify({}))"],
                    capture_output=True, text=True, timeout=10,
                    cwd=str(self.awc_path),
                )
                data = json.loads(result.stdout) if result.stdout else {}
                return HealthStatus(
                    battery=data.get("battery"),
                    heart_rate=data.get("heart_rate"),
                    active_energy=data.get("active_energy"),
                    last_update=datetime.now().isoformat(),
                )
        except Exception as exc:
            logger.debug(f"Watch health fetch failed: {exc}")
        return await self._fetch_local_health()

    async def send_notification(self, title: str, body: str) -> bool:
        if self._connected:
            logger.info(f"Would send to Watch: {title} - {body}")
            return True
        logger.info(f"Local notification: {title} - {body}")
        return True


class HealthMonitor:
    """Polls health data and triggers recovery actions."""

    def __init__(self, watch: WatchBridge) -> None:
        self.watch = watch
        self.threshold_battery = 20
        self._running = False
        self._last_health: Optional[HealthStatus] = None

    async def start(self) -> None:
        self._running = True
        while self._running:
            health = await self.watch.get_health_status()
            self._last_health = health
            if health.battery is not None and health.battery < self.threshold_battery:
                logger.warning(f"Battery low: {health.battery}%, consider stopping heavy tasks")
            await asyncio.sleep(60)

    def stop(self) -> None:
        self._running = False


class AutonomousAgent:
    """Main autonomous agent coordinator.
    
    Coordinates Insomnia (sleep prevention) + Apple Watch (health/notifications)
    to enable long-running autonomous ARIA background sessions.
    """

    def __init__(self) -> None:
        self.insomnia = InsomniaManager()
        self.watch = WatchBridge()
        self.health = HealthMonitor(self.watch)
        self._active_sessions: Dict[str, SessionConfig] = {}

    async def start_session(self, config: SessionConfig) -> bool:
        logger.info(f"Starting autonomous session: {config.name}")
        self._active_sessions[config.name] = config

        success = True
        if config.keep_awake:
            if self.insomnia.prevent_sleep(config.duration_minutes):
                logger.info("Sleep prevention active")
            else:
                success = False
                logger.warning("Could not prevent sleep")

        if config.freeze_distractions:
            for app in ["Slack", "Discord", "WhatsApp"]:
                self.insomnia.freeze_app(app)

        if config.tmux_pane:
            await self.watch.send_notification(
                "ARIA Autonomous Session",
                f"Started: {config.name} ({config.duration_minutes} min)",
            )

        await self.watch.connect()
        asyncio.create_task(self.health.start())

        return success

    async def end_session(self, name: str) -> None:
        if name not in self._active_sessions:
            logger.warning(f"Session {name} not found")
            return

        config = self._active_sessions.pop(name)
        self.health.stop()

        self.insomnia.restore()
        await self.watch.send_notification(
            "ARIA Session Complete",
            f"Session {name} finished successfully",
        )
        logger.info(f"Session {name} completed")

    def get_status(self) -> Dict[str, Any]:
        return {
            "active_sessions": list(self._active_sessions.keys()),
            "sleep_prevented": self.insomnia._sleep_prevented,
            "watch_connected": self.watch._connected,
            "insomnia_available": self.insomnia.is_available(),
            "watch_available": self.watch.is_available(),
            "health": self.health._last_health.__dict__ if self.health._last_health else None,
        }


autonomous_agent = AutonomousAgent()
