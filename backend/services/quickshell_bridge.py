"""Quickshell / end4-pC bridge for AURA NUCLEUS OS.

Polls backend telemetry and exposes it in formats friendly to
Quickshell widgets:
- JSON file: ``~/.local/share/quickshell/aura_telemetry.json``
- Optional local HTTP server on ``http://127.0.0.1:9457/telemetry``
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests

BACKEND_URL = os.getenv("AURA_BACKEND_URL", "http://127.0.0.1:8000")
TELEMETRY_PATH = "/api/system/telemetry"
POLL_INTERVAL_SEC = 2.0

QUICKSHELL_STATE_DIR = Path.home() / ".local" / "share" / "quickshell"
QUICKSHELL_STATE_FILE = QUICKSHELL_STATE_DIR / "aura_telemetry.json"

HTTP_HOST = "127.0.0.1"
HTTP_PORT = 9457


class QuickshellBridge:
    def __init__(self, backend_url: str = BACKEND_URL) -> None:
        self.backend_url = backend_url.rstrip("/")
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_payload: Dict[str, Any] = {}

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def _loop(self) -> None:
        while self._running:
            try:
                payload = self._fetch_telemetry()
                if payload is not None:
                    self._last_payload = payload
                    self._write_json(payload)
            except Exception:
                pass
            time.sleep(POLL_INTERVAL_SEC)

    def _fetch_telemetry(self) -> Optional[Dict[str, Any]]:
        try:
            resp = requests.get(
                f"{self.backend_url}{TELEMETRY_PATH}",
                timeout=5,
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            return {
                "timestamp": time.time(),
                "cpu": float(data.get("cpu", 0.0)),
                "memory": {
                    "percent": float(data.get("memory", {}).get("percent", 0.0)),
                    "used": int(data.get("memory", {}).get("used", 0)),
                    "total": int(data.get("memory", {}).get("total", 0)),
                },
                "disk": float(data.get("disk", 0.0)),
                "network": {
                    "bytes_sent": int(data.get("network", {}).get("bytes_sent", 0)),
                    "bytes_recv": int(data.get("network", {}).get("bytes_recv", 0)),
                    "packets_sent": int(data.get("network", {}).get("packets_sent", 0)),
                    "packets_recv": int(data.get("network", {}).get("packets_recv", 0)),
                },
                "swarm": self._extract_swarm(data),
            }
        except Exception:
            return None

    def _extract_swarm(self, data: Dict[str, Any]) -> Dict[str, Any]:
        swarm = data.get("swarm", {})
        if isinstance(swarm, dict):
            return {
                "active_agents": int(swarm.get("active_agents", 0)),
                "active_tasks": int(swarm.get("active_tasks", 0)),
                "health": float(swarm.get("health", 0.0)),
            }
        return {"active_agents": 0, "active_tasks": 0, "health": 0.0}

    def _write_json(self, payload: Dict[str, Any]) -> None:
        try:
            QUICKSHELL_STATE_DIR.mkdir(parents=True, exist_ok=True)
            tmp = QUICKSHELL_STATE_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            tmp.replace(QUICKSHELL_STATE_FILE)
        except Exception:
            pass

    def get_last_payload(self) -> Dict[str, Any]:
        return dict(self._last_payload)


bridge = QuickshellBridge()


def start_bridge() -> None:
    bridge.start()


def stop_bridge() -> None:
    bridge.stop()


def get_telemetry() -> Dict[str, Any]:
    return bridge.get_last_payload()
