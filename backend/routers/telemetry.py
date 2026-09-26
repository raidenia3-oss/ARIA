"""Telemetry router for AURA - Real-time system metrics via WebSocket."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

try:
    import psutil
except ImportError:
    psutil = None

try:
    import GPUtil
except ImportError:
    GPUtil = None

try:
    from backend.orchestrator import orchestrator, NODE_PC, NODE_SERVER, NODE_MOBILE
except Exception:
    orchestrator = None
    NODE_PC = NODE_SERVER = NODE_MOBILE = "unknown"

try:
    from backend.services.quickshell_bridge import quickshell_bridge
except Exception:  # pragma: no cover - optional bridge
    quickshell_bridge = None

try:
    from backend.cache.redis_client import redis_cache
except Exception:  # pragma: no cover - optional cache
    redis_cache = None

router = APIRouter()
logger = logging.getLogger("AURATelemetry")


class TelemetryPayload(BaseModel):
    timestamp: float
    cpu_percent: float
    ram_percent: float
    ram_used_gb: float
    ram_total_gb: float
    gpu_percent: Optional[float] = None
    gpu_memory_used_mb: Optional[float] = None
    gpu_memory_total_mb: Optional[float] = None
    swarm_agents: List[Dict[str, Any]] = []
    alerts: List[Dict[str, Any]] = []


def _get_cpu_ram() -> Dict[str, Any]:
    if psutil is None:
        return {
            "cpu_percent": 0.0,
            "ram_percent": 0.0,
            "ram_used_gb": 0.0,
            "ram_total_gb": 0.0,
        }
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    return {
        "cpu_percent": round(cpu, 1),
        "ram_percent": round(mem.percent, 1),
        "ram_used_gb": round(mem.used / (1024 ** 3), 2),
        "ram_total_gb": round(mem.total / (1024 ** 3), 2),
    }


def _get_gpu() -> Dict[str, Any]:
    if GPUtil is None:
        return {
            "gpu_percent": None,
            "gpu_memory_used_mb": None,
            "gpu_memory_total_mb": None,
        }
    try:
        gpus = GPUtil.getGPUs()
        if not gpus:
            return {
                "gpu_percent": 0.0,
                "gpu_memory_used_mb": 0.0,
                "gpu_memory_total_mb": 0.0,
            }
        gpu = gpus[0]
        return {
            "gpu_percent": round(gpu.load * 100, 1),
            "gpu_memory_used_mb": round(getattr(gpu, "memoryUsed", 0.0), 1),
            "gpu_memory_total_mb": round(getattr(gpu, "memoryTotal", 0.0), 1),
        }
    except Exception:
        return {
            "gpu_percent": None,
            "gpu_memory_used_mb": None,
            "gpu_memory_total_mb": None,
        }


def _get_swarm_agents() -> List[Dict[str, Any]]:
    agents: List[Dict[str, Any]] = []
    if orchestrator is None:
        return agents
    try:
        nodes = getattr(orchestrator, "nodes", [])
        for node in nodes:
            agents.append({
                "id": getattr(node, "node_id", str(id(node))),
                "role": getattr(node, "role", "unknown"),
                "status": getattr(node, "status", "inactive"),
                "last_seen": getattr(node, "last_seen", None),
            })
    except Exception:
        pass
    return agents


def _get_alerts() -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []
    try:
        from backend.production_routes import _latest_recommendations
        for rec in (_latest_recommendations or [])[-5:]:
            alerts.append({
                "level": rec.get("level", "info"),
                "message": rec.get("message", ""),
                "timestamp": rec.get("timestamp"),
            })
    except Exception:
        pass
    return alerts


def _build_payload() -> Dict[str, Any]:
    cpu_ram = _get_cpu_ram()
    gpu = _get_gpu()
    payload = {
        "timestamp": time.time(),
        "cpu_percent": cpu_ram["cpu_percent"],
        "ram_percent": cpu_ram["ram_percent"],
        "ram_used_gb": cpu_ram["ram_used_gb"],
        "ram_total_gb": cpu_ram["ram_total_gb"],
        "gpu_percent": gpu["gpu_percent"],
        "gpu_memory_used_mb": gpu["gpu_memory_used_mb"],
        "gpu_memory_total_mb": gpu["gpu_memory_total_mb"],
        "swarm_agents": _get_swarm_agents(),
        "alerts": _get_alerts(),
    }
    return payload


@router.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket) -> None:
    await websocket.accept()
    logger.info("Telemetry WebSocket connected")
    try:
        while True:
            payload = _build_payload()
            if redis_cache is not None:
                try:
                    await redis_cache.set("telemetry:latest", payload, ttl=1)
                except Exception:
                    pass
            if quickshell_bridge is not None:
                try:
                    await quickshell_bridge.emit_telemetry(payload)
                except Exception:
                    pass
            await websocket.send_json(payload)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        logger.info("Telemetry WebSocket disconnected")
    except Exception as exc:
        logger.error(f"Telemetry WebSocket error: {exc}")
        try:
            await websocket.close()
        except Exception:
            pass
