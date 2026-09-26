"""BLOQUE 100 - AURA Local Sovereign Omni-Agent Master Super-Agent Ecosystem
Finalization, Unified Runtime Launch & Immersive Omni-Orchestration Core.

Runtime maestro 100% local y soberano que unifica los 100 bloques del ecosistema
en un unico super-agent: pasarela unificada REST/WS (/api/aura/master), registro
de motores especializados y secuencia de lanzamiento resiliente. Sin cloud.
"""
from __future__ import annotations

import asyncio
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

LIFECYCLE_STATES = ("cold", "initializing", "ready", "degraded", "shutting_down", "stopped")
TOTAL_BLOCKS = 100


def _probe_block99_simulation() -> Dict[str, Any]:
    from backend.simulation.engine import get_engine
    eng = get_engine()
    return {"engine": "simulation", "block": 99, "ok": True, **eng.status()}


def _probe_block91_refactoring() -> Dict[str, Any]:
    from backend.refactoring.engine import get_engine
    e = get_engine()
    return {"engine": "refactoring", "block": 91, "ok": True,
            "patches": len(e.list_patches()), "metrics": e.get_metrics()}


def _probe_block92_planner() -> Dict[str, Any]:
    from backend.planner.hierarchical import get_planner
    return {"engine": "planner", "block": 92, "ok": True, **get_planner().status()}


def _probe_block98_bootstrapper() -> Dict[str, Any]:
    from backend.core.sovereign_bootstrapper import SovereignBootstrapper
    b = SovereignBootstrapper()
    return {"engine": "sovereign_bootstrapper", "block": 98, "ok": True,
            "health_report": b.run_bootstrapping()}


ENGINE_PROBES: List[Callable[[], Dict[str, Any]]] = [
    _probe_block91_refactoring,
    _probe_block92_planner,
    _probe_block98_bootstrapper,
    _probe_block99_simulation,
]


class MasterRuntimeEngine:
    """Runtime maestro del super-agent. Thread-safe, 100% offline."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.state = "cold"
        self.session_id: Optional[str] = None
        self.started_at: Optional[str] = None
        self.launch_log: List[Dict[str, Any]] = []
        self.custom_engines: Dict[str, Callable[[], Dict[str, Any]]] = {}
        self.heartbeat_count = 0

    def register_engine(self, name: str, probe: Callable[[], Dict[str, Any]]) -> None:
        with self._lock:
            self.custom_engines[name] = probe

    def probe_engines(self) -> Dict[str, Any]:
        """Ejecuta todos los probes registrados tolerando fallos individuales."""
        engines: List[Dict[str, Any]] = []
        for probe in list(ENGINE_PROBES) + list(self.custom_engines.values()):
            try:
                engines.append(probe())
            except Exception as exc:
                engines.append({"engine": probe.__name__, "ok": False, "error": str(exc)})
        return {"engines": engines,
                "engines_total": len(engines),
                "engines_ok": sum(1 for e in engines if e.get("ok"))}

    def launch(self) -> Dict[str, Any]:
        """Secuencia de lanzamiento soberana: valida motores y activa el runtime."""
        with self._lock:
            if self.state == "ready":
                return {"launched": True, "already": True, "session_id": self.session_id,
                        "state": self.state}
            self.state = "initializing"
            self.session_id = f"msr_{uuid.uuid4().hex[:12]}"
            self.launch_log = []
        probes = self.probe_engines()
        with self._lock:
            self.launch_log = probes["engines"]
            total, ok = probes["engines_total"], probes["engines_ok"]
            if total and ok == total:
                self.state = "ready"
            elif ok > 0:
                self.state = "degraded"
            else:
                self.state = "cold"
            self.started_at = time.strftime("%Y-%m-%dT%H:%M:%S")
            return {"launched": self.state in ("ready", "degraded"),
                    "state": self.state, "session_id": self.session_id,
                    "engines_total": total, "engines_ok": ok,
                    "total_blocks": TOTAL_BLOCKS, "offline_only": True}

    def shutdown(self) -> Dict[str, Any]:
        with self._lock:
            self.state = "shutting_down"
            self.state = "stopped"
            sid = self.session_id
            self.session_id = None
            return {"shutdown": True, "session_id": sid, "state": self.state,
                    "offline_only": True}

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "state": self.state,
                "session_id": self.session_id,
                "started_at": self.started_at,
                "heartbeat_count": self.heartbeat_count,
                "total_blocks": TOTAL_BLOCKS,
                "engines_registered": len(ENGINE_PROBES) + len(self.custom_engines),
                "offline_only": True,
            }

    def heartbeat(self) -> Dict[str, Any]:
        with self._lock:
            self.heartbeat_count += 1
            return {"event": "master_heartbeat", "state": self.state,
                    "session_id": self.session_id,
                    "beat": self.heartbeat_count, "offline_only": True}

    def reset(self) -> None:
        with self._lock:
            self.state = "cold"
            self.session_id = None
            self.started_at = None
            self.launch_log = []
            self.heartbeat_count = 0


_global: Optional[MasterRuntimeEngine] = None


def get_master_runtime() -> MasterRuntimeEngine:
    global _global
    if _global is None:
        _global = MasterRuntimeEngine()
    return _global


def reset_master_runtime() -> None:
    global _global
    if _global is not None:
        _global.reset()
    _global = None


# ─── Unified Omni-API Gateway (/api/aura/master) ──────────────────────────────

router = APIRouter(prefix="/api/aura/master", tags=["aura-master"])


@router.get("/status")
async def master_status() -> Dict[str, Any]:
    return get_master_runtime().status()


@router.post("/launch")
async def master_launch() -> Dict[str, Any]:
    return get_master_runtime().launch()


@router.post("/shutdown")
async def master_shutdown() -> Dict[str, Any]:
    return get_master_runtime().shutdown()


@router.get("/ecosystem")
async def master_ecosystem() -> Dict[str, Any]:
    """Probes de los motores consolidados del ecosistema (pasarela unificada)."""
    p = get_master_runtime().probe_engines()
    return {**p, "total_blocks": TOTAL_BLOCKS, "offline_only": True}


@router.get("/metrics")
async def master_metrics() -> Dict[str, Any]:
    rt = get_master_runtime()
    probes = rt.probe_engines()
    return {**rt.status(), "engines_total": probes["engines_total"],
            "engines_ok": probes["engines_ok"], "offline_only": True}


@router.post("/reset")
async def master_reset() -> Dict[str, Any]:
    reset_master_runtime()
    return {"reset": True, "offline_only": True}


class _WSConn:
    def __init__(self) -> None:
        self.active: set = set()


_ws = _WSConn()


@router.websocket("/ws")
async def master_ws(websocket: WebSocket) -> None:
    """Canal WebSocket maestro: heartbeat del super-agent al panel de control."""
    await websocket.accept()
    _ws.active.add(websocket)
    try:
        while True:
            await websocket.send_json(get_master_runtime().heartbeat())
            await asyncio.sleep(2.0)
    except (WebSocketDisconnect, Exception):
        _ws.active.discard(websocket)
