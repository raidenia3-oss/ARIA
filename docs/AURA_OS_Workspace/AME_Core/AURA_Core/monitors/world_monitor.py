"""AURA World Monitor — Motor de agregación geoespacial."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
OUTPUT = BASE / "data" / "world_live.json"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)


def _now() -> float:
    return time.time()


async def run() -> None:
    while True:
        snapshot = {
            "timestamp": _now(),
            "network_cables": [
                {
                    "id": "backbone-1",
                    "lat": 40.4168,
                    "lon": -3.7038,
                    "status": "ok",
                    "latency_ms": 120,
                },
                {
                    "id": "backbone-2",
                    "lat": 51.5074,
                    "lon": -0.1278,
                    "status": "ok",
                    "latency_ms": 145,
                },
                {
                    "id": "backbone-3",
                    "lat": 35.6762,
                    "lon": 139.6503,
                    "status": "degraded",
                    "latency_ms": 312,
                },
            ],
            "cyber_threats": [
                {
                    "id": "threat-1",
                    "type": "anomaly",
                    "origin": "unknown",
                    "level": "low",
                    "timestamp": _now(),
                },
            ],
            "node_connections": [
                {"node": "AME_ANDROID_01", "lat": -12.0464, "lon": -77.0428, "status": "active"},
                {"id": "server-remote-01", "lat": 37.7749, "lon": -122.4194, "status": "active"},
            ],
        }
        try:
            OUTPUT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        await asyncio.sleep(5)


def start() -> asyncio.Task:
    return asyncio.ensure_future(run())
