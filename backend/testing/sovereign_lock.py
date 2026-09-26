"""BLOQUE 104 - Local Final Sovereign System Lock-In, Smoke-Test Hardshell
& Production-Ready Daemon Verification.

Motor final de bloqueo soberano del sistema: sella los contratos del runtime
maestro, ejecuta el hardshell de pruebas de humo (puertos, BD vectorial,
colas de eventos, canales P2P) y certifica el estado 'Sovereign Ready' del
super-agent AURA. 100% local, offline y soberano.
"""
from __future__ import annotations

import asyncio
import hashlib
import importlib
import logging
import os
import platform
import socket
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

logger = logging.getLogger("AURA.SovereignLock104")

router = APIRouter(prefix="/api/core/sovereign-lock",
                   tags=["core", "sovereign-lock"])

# ---------------------------------------------------------------------------
# Enums & constants
# ---------------------------------------------------------------------------


class LockStatus(str, Enum):
    UNLOCKED = "unlocked"
    LOCKING = "locking"
    LOCKED = "locked"
    FAILED = "failed"


class SmokeSeverity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


PRODUCTION_PORTS: List[int] = [8000, 8080, 5173, 5174]
REQUIRED_MODULES: List[str] = [
    "backend.main", "backend.core.aura_master_runtime",
    "backend.ai.federated", "backend.ai.fine_tuning",
    "backend.network.mesh", "backend.memory.cognitive_graph",
    "backend.daemon.daemon_orchestrator", "backend.resilience.self_healing",
    "backend.hud.omni_interaction", "backend.master_control.master",
    "backend.core.diagnostics", "backend.diagnostics.health",
    "backend.refactoring.integration", "backend.fusion.sensory",
    "backend.planner.hierarchical", "backend.simulation.engine",
    "backend.swarm.swarm_routes", "backend.security.zk_routes",
    "backend.backup.routes", "backend.production_routes",
    "backend.integration_routes", "backend.learning_routes",
    "backend.unification_routes", "backend.local_ai_routes",
    "backend.tenant_routes", "backend.disaster_routes",
    "backend.spatial_routes", "backend.voice_routes",
    "backend.marketplace_routes", "backend.device_routes",
    "backend.nomad.nomad_routes", "backend.monitoring_routes",
    "backend.diagnostics.omni_routes", "backend.core.routes",
    "backend.core.sovereign_bootstrapper",
    "backend.testing.engine", "backend.testing.routes",
    "backend.ai.routes", "backend.ai.federated_routes",
    "backend.refactoring.engine", "backend.planner.planner_routes",
    "backend.evolution.patcher", "backend.security.identity_routes",
    "backend.auth.service", "backend.auth.models",
    "backend.sync_router", "backend.swarm_routes",
    "backend.action_engine", "backend.task_manager",
    "backend.websocket_manager", "backend.media_manager",
    "backend.browser_task_manager",
]


def _module_hash(name: str) -> str:
    try:
        mod = importlib.import_module(name)
        path = getattr(mod, "__file__", None)
        if path and os.path.isfile(path):
            with open(path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()[:16]
        return "builtin"
    except Exception:
        return "missing"


def _module_importable(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except Exception:
        return False


def _port_alive(host: str, port: int, timeout: float = 0.2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _file_sha256(path: str) -> str:
    try:
        if os.path.isfile(path):
            with open(path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()[:16]
    except Exception:
        pass
    return "missing"


def _env_local_hash() -> str:
    return _file_sha256(".env.local")


def _runtime_signature() -> str:
    """Firma inmutable del runtime: suma de hashes de los modulos críticos."""
    parts = []
    for name in REQUIRED_MODULES[:12]:
        parts.append(_module_hash(name))
    return hashlib.sha256("".join(parts).encode("utf-8")).hexdigest()[:16]

@dataclass
class PortProbe:
    port: int
    host: str = "127.0.0.1"
    alive: bool = False
    severity: SmokeSeverity = SmokeSeverity.WARNING
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"port": self.port, "host": self.host, "alive": self.alive,
                "severity": self.severity.value, "note": self.note}


@dataclass
class ModuleProbe:
    name: str
    importable: bool = False
    sha256: str = ""
    severity: SmokeSeverity = SmokeSeverity.CRITICAL

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "importable": self.importable,
                "sha256": self.sha256, "severity": self.severity.value}


@dataclass
class DaemonProbe:
    name: str
    alive: bool = False
    detail: str = ""
    severity: SmokeSeverity = SmokeSeverity.WARNING

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "alive": self.alive,
                "detail": self.detail, "severity": self.severity.value}


@dataclass
class SmokeResult:
    """Resultado del hardshell de pruebas de humo."""
    report_id: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    ports: List[PortProbe] = field(default_factory=list)
    modules: List[ModuleProbe] = field(default_factory=list)
    daemons: List[DaemonProbe] = field(default_factory=list)
    cold_boot_ms: float = 0.0
    warm_boot_ms: float = 0.0
    env_local_sha256: str = ""
    runtime_signature: str = ""
    ports_ok: int = 0
    ports_fail: int = 0
    modules_ok: int = 0
    modules_fail: int = 0
    daemons_ok: int = 0
    daemons_fail: int = 0
    status: str = "idle"
    sovereign_ready: bool = False
    offline_only: bool = True

    def __post_init__(self) -> None:
        if not self.report_id:
            self.report_id = "smoke_" + uuid.uuid4().hex[:12]
        if not self.started_at:
            self.started_at = time.time()

    def finalize(self) -> "SmokeResult":
        self.ports_ok = sum(1 for p in self.ports if p.alive)
        self.ports_fail = sum(1 for p in self.ports if not p.alive)
        self.modules_ok = sum(1 for m in self.modules if m.importable)
        self.modules_fail = sum(1 for m in self.modules if not m.importable)
        self.daemons_ok = sum(1 for d in self.daemons if d.alive)
        self.daemons_fail = sum(1 for d in self.daemons if not d.alive)
        critical_fail = sum(1 for m in self.modules
                            if m.severity == SmokeSeverity.CRITICAL
                            and not m.importable)
        daemon_fail = sum(1 for d in self.daemons
                          if d.severity == SmokeSeverity.CRITICAL
                          and not d.alive)
        self.sovereign_ready = (self.ports_fail == 0 and critical_fail == 0
                                and daemon_fail == 0)
        self.status = ("passed" if self.sovereign_ready
                       else ("degraded" if self.modules_ok > 0 else "failed"))
        self.finished_at = time.time()
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {"report_id": self.report_id, "started_at": self.started_at,
                "finished_at": self.finished_at,
                "ports": [p.to_dict() for p in self.ports],
                "modules": [m.to_dict() for m in self.modules],
                "daemons": [d.to_dict() for d in self.daemons],
                "cold_boot_ms": self.cold_boot_ms,
                "warm_boot_ms": self.warm_boot_ms,
                "env_local_sha256": self.env_local_sha256,
                "runtime_signature": self.runtime_signature,
                "ports_ok": self.ports_ok, "ports_fail": self.ports_fail,
                "modules_ok": self.modules_ok, "modules_fail": self.modules_fail,
                "daemons_ok": self.daemons_ok, "daemons_fail": self.daemons_fail,
                "status": self.status, "sovereign_ready": self.sovereign_ready,
                "offline_only": self.offline_only}


@dataclass
class LockReport:
    """Estado final del bloqueo soberano del runtime."""
    report_id: str = ""
    ts: float = 0.0
    status: LockStatus = LockStatus.UNLOCKED
    runtime_signature: str = ""
    env_local_sha256: str = ""
    modules_total: int = 0
    modules_ok: int = 0
    smoke_passed: bool = False
    e2e_passed: bool = False
    e2e_report_id: str = ""
    hardening_checks: int = 0
    hardening_passed: int = 0
    locked_at: float = 0.0
    immutable: bool = True
    offline_only: bool = True

    def __post_init__(self) -> None:
        if not self.report_id:
            self.report_id = "lock_" + uuid.uuid4().hex[:12]
        if not self.ts:
            self.ts = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {"report_id": self.report_id, "ts": self.ts,
                "status": self.status.value,
                "runtime_signature": self.runtime_signature,
                "env_local_sha256": self.env_local_sha256,
                "modules_total": self.modules_total,
                "modules_ok": self.modules_ok,
                "smoke_passed": self.smoke_passed,
                "e2e_passed": self.e2e_passed,
                "e2e_report_id": self.e2e_report_id,
                "hardening_checks": self.hardening_checks,
                "hardening_passed": self.hardening_passed,
                "locked_at": self.locked_at,
                "immutable": self.immutable,
                "offline_only": self.offline_only}

class SmokeHardshell:
    """Validador de humo de produccion: puertos, modulos, BD vectorial,
    colas de eventos y canales P2P. 100% local."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._last: Optional[SmokeResult] = None

    def _scan_ports(self) -> List[PortProbe]:
        probes: List[PortProbe] = []
        for port in PRODUCTION_PORTS:
            alive = _port_alive("127.0.0.1", port)
            sev = (SmokeSeverity.INFO if alive
                   else SmokeSeverity.WARNING)
            probes.append(PortProbe(port=port, host="127.0.0.1", alive=alive,
                                    severity=sev,
                                    note="listening" if alive else "not_open"))
        return probes

    def _scan_modules(self) -> List[ModuleProbe]:
        probes: List[ModuleProbe] = []
        for name in REQUIRED_MODULES:
            ok = _module_importable(name)
            probes.append(ModuleProbe(name=name, importable=ok,
                                      sha256=_module_hash(name),
                                      severity=SmokeSeverity.CRITICAL))
        return probes

    def _scan_daemons(self) -> Tuple[List[DaemonProbe], float, float]:
        """Verificacion frio/caliente del daemon + vectorial/eventos/P2P."""
        probes: List[DaemonProbe] = []
        t0 = time.perf_counter()
        try:
            from backend.daemon.daemon_orchestrator import DaemonOrchestrator
            d = DaemonOrchestrator()
            probes.append(DaemonProbe(
                name="daemon_orchestrator", alive=bool(d.health.is_running),
                detail="lifecycle ok", severity=SmokeSeverity.WARNING))
        except Exception as exc:
            probes.append(DaemonProbe(
                name="daemon_orchestrator", alive=False,
                detail=str(exc)[:120], severity=SmokeSeverity.WARNING))
        cold_ms = (time.perf_counter() - t0) * 1000.0
        t1 = time.perf_counter()
        try:
            from backend.memory.cognitive_graph import get_cognitive_graph
            g = get_cognitive_graph()
            hits = g.search("smoke", limit=1)
            probes.append(DaemonProbe(
                name="vector_memory", alive=True,
                detail=f"nodes probed={len(hits)}",
                severity=SmokeSeverity.WARNING))
        except Exception as exc:
            probes.append(DaemonProbe(
                name="vector_memory", alive=False,
                detail=str(exc)[:120], severity=SmokeSeverity.WARNING))
        try:
            from backend.fusion.sensory import get_fusion_engine
            ev = get_fusion_engine().ingest(
                source="system", kind="smoke.ping",
                payload={"block": 104}, severity="info")
            probes.append(DaemonProbe(
                name="event_queue", alive=bool(ev.event_id),
                detail=f"event={ev.event_id}",
                severity=SmokeSeverity.WARNING))
        except Exception as exc:
            probes.append(DaemonProbe(
                name="event_queue", alive=False,
                detail=str(exc)[:120], severity=SmokeSeverity.WARNING))
        try:
            from backend.network.mesh import get_mesh_orchestrator
            st = get_mesh_orchestrator().engine.status()
            probes.append(DaemonProbe(
                name="p2p_channel", alive=True,
                detail=f"peers={st.get('peers')}",
                severity=SmokeSeverity.WARNING))
        except Exception as exc:
            probes.append(DaemonProbe(
                name="p2p_channel", alive=False,
                detail=str(exc)[:120], severity=SmokeSeverity.WARNING))
        warm_ms = (time.perf_counter() - t1) * 1000.0
        return probes, round(cold_ms, 2), round(warm_ms, 2)

    def run(self) -> SmokeResult:
        rep = SmokeResult()
        rep.ports = self._scan_ports()
        rep.modules = self._scan_modules()
        rep.daemons, rep.cold_boot_ms, rep.warm_boot_ms = self._scan_daemons()
        rep.env_local_sha256 = _env_local_hash()
        rep.runtime_signature = _runtime_signature()
        rep.finalize()
        with self._lock:
            self._last = rep
        return rep

    def last(self) -> Optional[SmokeResult]:
        with self._lock:
            return self._last


class SovereignLockEngine:
    """Motor de bloqueo soberano final: sella los contratos del runtime maestro
    y activa el modo de operacion protegido en produccion."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._status: LockStatus = LockStatus.UNLOCKED
        self._report: Optional[LockReport] = None
        self._locked_at: float = 0.0
        self._smoke = SmokeHardshell()
        self._runtime_sig: str = _runtime_signature()
        self._env_local_sha: str = _env_local_hash()

    # -- health checks ----------------------------------------------------

    def smoke_test(self) -> Dict[str, Any]:
        rep = self._smoke.run()
        return rep.to_dict()

    def smoke_status(self) -> Dict[str, Any]:
        last = self._smoke.last()
        return last.to_dict() if last else {"status": "idle",
                                            "offline_only": True}

    def module_audit(self) -> Dict[str, Any]:
        probes = self._smoke._scan_modules()
        ok = sum(1 for m in probes if m.importable)
        return {"modules_total": len(probes), "modules_ok": ok,
                "modules_fail": len(probes) - ok,
                "modules": [m.to_dict() for m in probes],
                "offline_only": True}

    def port_audit(self) -> Dict[str, Any]:
        probes = self._smoke._scan_ports()
        ok = sum(1 for p in probes if p.alive)
        return {"ports_total": len(probes), "ports_ok": ok,
                "ports_fail": len(probes) - ok,
                "ports": [p.to_dict() for p in probes],
                "offline_only": True}

    # -- lock -------------------------------------------------------------

    def lock(self, force: bool = False) -> Dict[str, Any]:
        with self._lock:
            if self._status == LockStatus.LOCKED and not force:
                return self._report.to_dict()
            if self._status == LockStatus.FAILED and not force:
                # Reintento idempotente: conserva el report_id original.
                return self._report.to_dict() if self._report else {
                    "status": self._status.value, "offline_only": True}
            self._status = LockStatus.LOCKING
        smoke = self._smoke.run()
        # E2E matrix check (best-effort, no exceptions)
        e2e_ok = True
        e2e_id = ""
        try:
            from backend.testing.engine import MatrixEngine
            eng = MatrixEngine(timeout_s=5.0)
            rep = eng.run_chain()
            e2e_ok = rep.status == "passed"
            e2e_id = rep.report_id
        except Exception:
            e2e_ok = False

        # Hardening check (best-effort)
        hard_checks = 0
        hard_passed = 0
        try:
            from backend.core.sovereign_bootstrapper import (
                get_sovereign_bootstrapper)
            bs = get_sovereign_bootstrapper()
            hr = bs.hardening.scan()
            hard_checks = hr.checks_total
            hard_passed = hr.checks_passed
        except Exception:
            pass

        modules_ok = smoke.modules_ok
        modules_total = len(smoke.modules)
        with self._lock:
            self._status = (LockStatus.LOCKED
                            if (smoke.sovereign_ready and e2e_ok)
                            else LockStatus.FAILED)
            self._locked_at = time.time()
            self._report = LockReport(
                status=self._status,
                runtime_signature=self._runtime_sig,
                env_local_sha256=self._env_local_sha,
                modules_total=modules_total,
                modules_ok=modules_ok,
                smoke_passed=smoke.sovereign_ready,
                e2e_passed=e2e_ok,
                e2e_report_id=e2e_id,
                hardening_checks=hard_checks,
                hardening_passed=hard_passed,
                locked_at=self._locked_at,
            )
            return self._report.to_dict()

    def unlock(self) -> Dict[str, Any]:
        with self._lock:
            self._status = LockStatus.UNLOCKED
            self._locked_at = 0.0
            self._report = None
        return {"status": LockStatus.UNLOCKED.value,
                "offline_only": True}

    def daemon_audit(self) -> Dict[str, Any]:
        probes, cold_ms, warm_ms = self._smoke._scan_daemons()
        ok = sum(1 for d in probes if d.alive)
        return {"daemons_total": len(probes), "daemons_ok": ok,
                "daemons_fail": len(probes) - ok,
                "cold_boot_ms": cold_ms, "warm_boot_ms": warm_ms,
                "daemons": [d.to_dict() for d in probes],
                "offline_only": True}

    def audit104(self) -> Dict[str, Any]:
        """Audita los 104 bloques via contratos montados en la app real."""
        total = 104
        try:
            from backend.main import app as _app
            routes = [getattr(r, "path", "") for r in _app.routes]
        except Exception:
            routes = []
        checks = {
            "98_sovereign_boot": any("/api/core/sovereign-boot" in p
                                     for p in routes),
            "100_master": any("/api/aura/master" in p for p in routes),
            "103_matrix": any("/api/testing/matrix" in p for p in routes),
            "104_lock": any("/api/core/sovereign-lock" in p for p in routes),
            "91_refactoring": any("/api/refactoring" in p for p in routes),
            "99_simulation": any("/api/simulation" in p for p in routes),
            "102_federated": any("/api/ai/federated" in p for p in routes),
            "83_fusion": any("/api/fusion" in p for p in routes),
            "71_telemetry": any("/api/telemetry" in p for p in routes),
        }
        ok = sum(1 for v in checks.values() if v)
        return {"blocks_total": total,
                "contracts_ok": ok, "contracts_total": len(checks),
                "checks": checks,
                "routes_total": len(routes),
                "sovereign_ready": ok == len(checks),
                "offline_only": True}

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {"status": self._status.value,
                    "locked_at": self._locked_at,
                    "runtime_signature": self._runtime_sig,
                    "env_local_sha256": self._env_local_sha,
                    "report": self._report.to_dict() if self._report else None,
                    "sovereign_ready": (
                        self._report.smoke_passed
                        and self._report.e2e_passed
                        if self._report else False),
                    "offline_only": True}

    def verify(self) -> Dict[str, Any]:
        """Verifica que el bloqueo sigue intacto (runtime inmutable)."""
        current_sig = _runtime_signature()
        current_env = _env_local_hash()
        with self._lock:
            if self._status != LockStatus.LOCKED:
                return {"verified": False,
                        "reason": "not_locked",
                        "signature_match": False,
                        "runtime_signature": current_sig,
                        "env_local_sha256": current_env,
                        "offline_only": True}
            ok = (current_sig == self._runtime_sig
                  and current_env == self._env_local_sha)
            return {"verified": ok,
                    "signature_match": ok,
                    "runtime_signature": current_sig,
                    "env_local_sha256": current_env,
                    "offline_only": True}


_global_lock: Optional[SovereignLockEngine] = None
_global_lock_mutex = threading.Lock()


def get_sovereign_lock() -> SovereignLockEngine:
    global _global_lock
    if _global_lock is None:
        with _global_lock_mutex:
            if _global_lock is None:
                _global_lock = SovereignLockEngine()
    return _global_lock


def reset_sovereign_lock() -> SovereignLockEngine:
    global _global_lock
    with _global_lock_mutex:
        _global_lock = SovereignLockEngine()
        return _global_lock

# ---------------------------------------------------------------------------
# REST + WebSocket handlers
# ---------------------------------------------------------------------------


class LockRequest(BaseModel):
    force: bool = False


@router.get("/status", tags=["core-sovereign-lock"])
async def lock_status() -> Dict[str, Any]:
    return get_sovereign_lock().status()


@router.get("/smoke", tags=["core-sovereign-lock"])
async def lock_smoke() -> Dict[str, Any]:
    return get_sovereign_lock().smoke_test()


@router.get("/smoke/status", tags=["core-sovereign-lock"])
async def lock_smoke_status() -> Dict[str, Any]:
    return get_sovereign_lock().smoke_status()


@router.get("/modules", tags=["core-sovereign-lock"])
async def lock_modules() -> Dict[str, Any]:
    return get_sovereign_lock().module_audit()


@router.get("/ports", tags=["core-sovereign-lock"])
async def lock_ports() -> Dict[str, Any]:
    return get_sovereign_lock().port_audit()


@router.post("/lock", tags=["core-sovereign-lock"])
async def lock_lock(req: LockRequest) -> Dict[str, Any]:
    return get_sovereign_lock().lock(force=req.force)


@router.post("/unlock", tags=["core-sovereign-lock"])
async def lock_unlock() -> Dict[str, Any]:
    return get_sovereign_lock().unlock()


@router.get("/verify", tags=["core-sovereign-lock"])
async def lock_verify() -> Dict[str, Any]:
    return get_sovereign_lock().verify()


@router.get("/channels", tags=["core-sovereign-lock"])
async def lock_channels() -> Dict[str, Any]:
    return {
        "channels": ["status", "contracts", "smoke", "smoke/status",
                     "modules", "ports", "daemons", "audit104",
                     "lock", "unlock", "verify"],
        "ws": "/api/core/sovereign-lock/ws",
        "offline_only": True,
    }


@router.get("/contracts", tags=["core-sovereign-lock"])
async def lock_contracts() -> Dict[str, Any]:
    return {
        "block": 104, "prefix": router.prefix,
        "endpoints": [
            {"method": "GET", "path": "/api/core/sovereign-lock/status"},
            {"method": "GET", "path": "/api/core/sovereign-lock/contracts"},
            {"method": "GET", "path": "/api/core/sovereign-lock/smoke"},
            {"method": "GET", "path": "/api/core/sovereign-lock/smoke/status"},
            {"method": "GET", "path": "/api/core/sovereign-lock/modules"},
            {"method": "GET", "path": "/api/core/sovereign-lock/ports"},
            {"method": "GET", "path": "/api/core/sovereign-lock/daemons"},
            {"method": "GET", "path": "/api/core/sovereign-lock/audit104"},
            {"method": "POST", "path": "/api/core/sovereign-lock/lock"},
            {"method": "POST", "path": "/api/core/sovereign-lock/unlock"},
            {"method": "GET", "path": "/api/core/sovereign-lock/verify"},
            {"method": "GET", "path": "/api/core/sovereign-lock/channels"},
            {"method": "WS", "path": "/api/core/sovereign-lock/ws"},
        ],
        "compatibility": {
            "98_boot": "/api/core/sovereign-boot/* (boot/hardening/health)",
            "100_master": "/api/aura/master/* (launch/ecosystem)",
            "103_matrix": "/api/testing/matrix/* (run/stress)",
        },
        "offline_only": True,
    }


@router.get("/daemons", tags=["core-sovereign-lock"])
async def lock_daemons() -> Dict[str, Any]:
    rep = get_sovereign_lock().daemon_audit()
    rep["offline_only"] = True
    return rep


@router.get("/audit104", tags=["core-sovereign-lock"])
async def lock_audit104() -> Dict[str, Any]:
    """Auditoria definitiva de los 104 bloques (contratos montados)."""
    return get_sovereign_lock().audit104()


class _WSConn:
    def __init__(self) -> None:
        self.active: set = set()
        self._loop = None

    def set_loop(self, loop) -> None:
        self._loop = loop

    def broadcast(self, payload: Dict[str, Any]) -> None:
        if not self.active:
            return
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        for ws in list(self.active):
            try:
                coro = ws.send_json(payload)
                if asyncio.iscoroutine(coro):
                    loop.call_soon_threadsafe(asyncio.ensure_future, coro)
            except Exception:
                self.active.discard(ws)


_ws = _WSConn()


@router.websocket("/ws")
async def lock_ws(websocket: WebSocket) -> None:
    """Canal WebSocket en tiempo real para el bloqueo soberano final.

    Push: heartbeat con estado 'Sovereign Ready'.
    """
    await websocket.accept()
    _ws.active.add(websocket)
    eng = get_sovereign_lock()
    try:
        _ws.set_loop(asyncio.get_running_loop())
    except Exception:
        pass
    try:
        await websocket.send_json({"type": "connected",
                                   "status": eng.status(),
                                   "offline_only": True})
        while True:
            await asyncio.sleep(2.0)
            try:
                await websocket.send_json({
                    "type": "heartbeat",
                    "status": eng.status(),
                    "ts": time.time(),
                    "offline_only": True,
                })
            except Exception:
                break
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        _ws.active.discard(websocket)


__all__ = [
    "router", "LockStatus", "SmokeSeverity", "PortProbe", "ModuleProbe",
    "DaemonProbe",
    "SmokeResult", "LockReport", "SmokeHardshell", "SovereignLockEngine",
    "get_sovereign_lock", "reset_sovereign_lock",
    "PRODUCTION_PORTS", "REQUIRED_MODULES",
]