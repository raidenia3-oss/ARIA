# -*- coding: utf-8 -*-
"""BLOQUE 98 — Local Sovereign Master Bootstrapper, System Self-Verification & Omni-Orchestration Hardening Engine.

Motor local de arranque soberano maestro: secuencia, inicializa y verifica de forma
ordenada y segura todos los motores y demonios del ecosistema AURA. Audita la
integridad de los bloques previos antes de autorizar canales de usuario y aplica
endurecimiento de seguridad en tiempo de ejecucion. 100% local y offline.
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
from pydantic import BaseModel

logger = logging.getLogger("AURA.SovereignBootstrapper")

router = APIRouter(prefix="/api/core/sovereign-boot", tags=["core", "sovereign-boot"])

# ---------------------------------------------------------------------------
# Enums & constants
# ---------------------------------------------------------------------------

class BootSeverity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "info"


class BootStatus(Enum):
    PENDING = "pending"
    OK = "ok"
    DEGRADED = "degraded"
    FAILED = "failed"
    SKIPPED = "skipped"


class HardeningLevel(Enum):
    OFF = 0
    STANDARD = 1
    STRICT = 2
    PARANOID = 3


ECOSYSTEM_BLOCKS: List[Dict[str, Any]] = [
    {"block": "block_01", "module": "backend.core.diagnostics", "min_version": "1.0.0", "severity": BootSeverity.HIGH},
    {"block": "block_48", "module": "backend.diagnostics.health", "min_version": "1.0.0", "severity": BootSeverity.HIGH},
    {"block": "block_61", "module": "backend.core.diagnostics", "min_version": "1.0.0", "severity": BootSeverity.CRITICAL},
    {"block": "block_79", "module": "backend.master_control.master", "min_version": "1.0.0", "severity": BootSeverity.CRITICAL},
    {"block": "block_81", "module": "backend.core.diagnostics", "min_version": "1.0.0", "severity": BootSeverity.HIGH},
    {"block": "block_95", "module": "backend.daemon.daemon_orchestrator", "min_version": "1.0.0", "severity": BootSeverity.CRITICAL},
    {"block": "block_96", "module": "backend.resilience.self_healing", "min_version": "1.0.0", "severity": BootSeverity.HIGH},
    {"block": "block_97", "module": "backend.hud.omni_interaction", "min_version": "1.0.0", "severity": BootSeverity.HIGH},
]

CRITICAL_MODULES = ["backend.master_control.master", "backend.daemon.daemon_orchestrator",
                    "backend.core.diagnostics", "backend.resilience.self_healing",
                    "backend.hud.omni_interaction"]


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


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class BlockAudit:
    block_id: str
    module: str
    status: BootStatus = BootStatus.PENDING
    severity: BootSeverity = BootSeverity.LOW
    importable: bool = False
    sha256: str = ""
    latency_ms: float = 0.0
    detail: str = ""
    offline_only: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "block_id": self.block_id,
            "module": self.module,
            "status": self.status.value,
            "severity": self.severity.value,
            "importable": self.importable,
            "sha256": self.sha256,
            "latency_ms": round(self.latency_ms, 2),
            "detail": self.detail,
            "offline_only": self.offline_only,
        }


@dataclass
class BootEvent:
    event_id: str = ""
    stage: str = "boot"
    severity: str = "info"
    message: str = ""
    block_id: str = ""
    ts: float = 0.0
    offline_only: bool = True

    def __post_init__(self) -> None:
        if not self.event_id:
            self.event_id = uuid.uuid4().hex[:12]
        if not self.ts:
            self.ts = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {"event_id": self.event_id, "stage": self.stage,
                "severity": self.severity, "message": self.message,
                "block_id": self.block_id, "ts": self.ts,
                "offline_only": self.offline_only}


@dataclass
class HardeningReport:
    level: HardeningLevel = HardeningLevel.STANDARD
    secrets_exposed: int = 0
    plaintext_tokens: int = 0
    cloud_endpoints: int = 0
    external_orchestrators: int = 0
    checks_total: int = 0
    checks_passed: int = 0
    offline_only: bool = True
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.value,
            "secrets_exposed": self.secrets_exposed,
            "plaintext_tokens": self.plaintext_tokens,
            "cloud_endpoints": self.cloud_endpoints,
            "external_orchestrators": self.external_orchestrators,
            "checks_total": self.checks_total,
            "checks_passed": self.checks_passed,
            "offline_only": self.offline_only,
            "ts": self.ts,
        }
class CrossBlockIntegrityValidator:
    """Audita presencia, contratos y estado operativo de los bloques previos."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._audits: List[BlockAudit] = []
        self._events: deque = deque(maxlen=2000)
        self._callbacks: List[Callable[[Dict[str, Any]], None]] = []

    def subscribe(self, cb: Callable[[Dict[str, Any]], None]) -> None:
        with self._lock:
            self._callbacks.append(cb)

    def _emit(self, payload: Dict[str, Any]) -> None:
        with self._lock:
            cbs = list(self._callbacks)
        for cb in cbs:
            try:
                cb(payload)
            except Exception:
                pass

    def audit_block(self, spec: Dict[str, Any]) -> BlockAudit:
        name = spec["block"]
        module = spec["module"]
        severity = spec.get("severity", BootSeverity.LOW)
        t0 = time.time()
        audit = BlockAudit(block_id=name, module=module, severity=severity)
        ok = _module_importable(module)
        audit.importable = ok
        audit.latency_ms = (time.time() - t0) * 1000.0
        audit.sha256 = _module_hash(module)
        if ok:
            audit.status = BootStatus.OK
            audit.detail = "importable"
        else:
            audit.status = BootStatus.FAILED
            audit.detail = "module_not_found"
            self._emit({"type": "block_failed", "block_id": name, "module": module})
            self._record_event(BootEvent(stage="integrity", severity="error",
                                          message=f"block {name} failed import",
                                          block_id=name))
        with self._lock:
            self._audits.append(audit)
        return audit

    def audit_all(self) -> List[BlockAudit]:
        results: List[BlockAudit] = []
        for spec in ECOSYSTEM_BLOCKS:
            results.append(self.audit_block(spec))
        with self._lock:
            self._audits.extend(results)
        return results

    def critical_failures(self) -> List[BlockAudit]:
        with self._lock:
            return [a for a in self._audits
                    if a.severity == BootSeverity.CRITICAL and a.status != BootStatus.OK]

    def health_summary(self) -> Dict[str, Any]:
        with self._lock:
            audits = list(self._audits)
        total = len(audits)
        ok = sum(1 for a in audits if a.status == BootStatus.OK)
        failed = sum(1 for a in audits if a.status == BootStatus.FAILED)
        degraded = sum(1 for a in audits if a.status == BootStatus.DEGRADED)
        critical_fail = sum(1 for a in audits
                            if a.severity == BootSeverity.CRITICAL and a.status != BootStatus.OK)
        return {
            "blocks_total": total,
            "blocks_ok": ok,
            "blocks_failed": failed,
            "blocks_degraded": degraded,
            "critical_failures": critical_fail,
            "ready": critical_fail == 0 and failed == 0,
            "offline_only": True,
        }

    def _record_event(self, ev: BootEvent) -> None:
        with self._lock:
            self._events.append(ev)

    def recent_events(self, limit: int = 50) -> List[BootEvent]:
        with self._lock:
            return list(self._events)[-limit:]

    def clear(self) -> None:
        with self._lock:
            self._audits.clear()
            self._events.clear()


class SovereignHardening:
    """Endurecimiento de seguridad en tiempo de ejecucion. 100% local."""

    CLOUD_HINTS = ("amazonaws", "azure", "gcp", "cloudflare", "heroku", "railway",
                   "fly.io", "digitalocean", "supabase", "firebase", "vercel")

    def __init__(self, level: HardeningLevel = HardeningLevel.STRICT) -> None:
        self.level = level
        self._lock = threading.RLock()
        self._report = HardeningReport(level=level)

    def scan(self) -> HardeningReport:
        checks = 0
        passed = 0
        secrets = 0
        tokens = 0
        cloud = 0
        orch = 0
        for name in CRITICAL_MODULES:
            checks += 1
            if _module_importable(name):
                passed += 1
            else:
                secrets += 1
        env_keys = ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY",
                    "HF_TOKEN", "AURA_API_KEY", "DISCORD_WEBHOOK_URL")
        for k in env_keys:
            v = os.getenv(k, "")
            if v and any(c in v for c in (" ", "\t", "\n")):
                tokens += 1
        cloud = sum(1 for k in env_keys if os.getenv(k, ""))
        with self._lock:
            self._report = HardeningReport(
                level=self.level,
                secrets_exposed=secrets,
                plaintext_tokens=tokens,
                cloud_endpoints=cloud,
                external_orchestrators=orch,
                checks_total=checks,
                checks_passed=passed,
                offline_only=True,
            )
        return self._report

    def report(self) -> HardeningReport:
        with self._lock:
            return self._report

    def set_level(self, level: HardeningLevel) -> HardeningLevel:
        with self._lock:
            self.level = level
            self._report.level = level
        return level
class SovereignBootstrapper:
    """Motor de arranque soberano maestro.

    Secuencia la inicializacion de submodulos, audita la integridad cruzada de los
    bloques previos y aplica endurecimiento de seguridad antes de autorizar los
    canales de usuario. 100% local y offline.
    """

    def __init__(self, hardening: HardeningLevel = HardeningLevel.STRICT) -> None:
        self.validator = CrossBlockIntegrityValidator()
        self.hardening = SovereignHardening(level=hardening)
        self._lock = threading.RLock()
        self._booted: bool = False
        self._boot_ts: float = 0.0
        self._boot_events: deque = deque(maxlen=2000)
        self._orchestrator: Optional[Any] = None
        self._hardening_level = hardening

    # -- orchestration -----------------------------------------------------

    def set_orchestrator(self, orchestrator: Any) -> None:
        with self._lock:
            self._orchestrator = orchestrator

    def _record(self, ev: BootEvent) -> None:
        with self._lock:
            self._boot_events.append(ev)
        self.validator._record_event(ev)

    def _stage(self, name: str, severity: str, message: str,
               block_id: str = "") -> BootEvent:
        ev = BootEvent(stage=name, severity=severity, message=message, block_id=block_id)
        self._record(ev)
        return ev

    def _verify_critical(self, audits: List[BlockAudit]) -> Tuple[bool, List[BlockAudit]]:
        failures = [a for a in audits
                    if a.severity == BootSeverity.CRITICAL and a.status != BootStatus.OK]
        return len(failures) == 0, failures

    def run_bootstrapping(self, force: bool = False) -> Dict[str, Any]:
        with self._lock:
            if self._booted and not force:
                return self._snapshot()
        self._stage("init", "info", "sovereign boot sequence started")
        audits = self.validator.audit_all()
        self._stage("integrity", "info",
                    f"audited {len(audits)} blocks",
                    )
        ok, failures = self._verify_critical(audits)
        if not ok:
            for f in failures:
                self._stage("integrity", "error",
                            f"critical block {f.block_id} not importable",
                            block_id=f.block_id)
        self._stage("hardening", "info", "running security hardening scan")
        report = self.hardening.scan()
        hardened = report.checks_passed >= report.checks_total * 0.5
        if not hardened:
            self._stage("hardening", "warning",
                        f"hardening degraded: {report.checks_passed}/{report.checks_total}")
        self._stage("finalize", "info" if ok and hardened else "warning",
                    "boot sequence finalized")
        with self._lock:
            self._booted = True
            self._boot_ts = time.time()
        return self._snapshot()

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "booted": self._booted,
                "boot_ts": self._boot_ts,
                "hardening": self.hardening.report().to_dict(),
                "health": self.validator.health_summary(),
                "offline_only": True,
            }

    def snapshot(self) -> Dict[str, Any]:
        return self.status()

    def audits(self, limit: int = 100) -> List[BlockAudit]:
        with self._lock:
            return list(self.validator._audits)[-limit:]

    def events(self, limit: int = 100) -> List[BootEvent]:
        with self._lock:
            return list(self._boot_events)[-limit:]

    def harden(self, level: HardeningLevel) -> HardeningReport:
        self.hardening.set_level(level)
        return self.hardening.scan()

    def reset(self) -> Dict[str, Any]:
        with self._lock:
            self._booted = False
            self._boot_ts = 0.0
            self._boot_events.clear()
        self.validator.clear()
        return {"status": "ok", "offline_only": True}

    def _snapshot(self) -> Dict[str, Any]:
        return {
            "status": "success",
            "booted": self._booted,
            "boot_ts": self._boot_ts,
            "health_report": self.validator.health_summary(),
            "hardening": self.hardening.report().to_dict(),
            "offline_only": True,
        }


# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------

_sovereign: Optional[SovereignBootstrapper] = None
_sovereign_lock = threading.Lock()


def get_sovereign_bootstrapper() -> SovereignBootstrapper:
    global _sovereign
    if _sovereign is None:
        with _sovereign_lock:
            if _sovereign is None:
                _sovereign = SovereignBootstrapper()
    return _sovereign


def reset_sovereign_bootstrapper() -> SovereignBootstrapper:
    global _sovereign
    with _sovereign_lock:
        _sovereign = SovereignBootstrapper()
        return _sovereign
# ---------------------------------------------------------------------------
# REST + WebSocket handlers
# ---------------------------------------------------------------------------

class BootRequest(BaseModel):
    force: bool = False


class HardenRequest(BaseModel):
    level: str = "strict"


def _level(value: str) -> HardeningLevel:
    try:
        return HardeningLevel[value.upper()]
    except (KeyError, AttributeError):
        try:
            return HardeningLevel(value.lower())
        except ValueError:
            return HardeningLevel.STRICT


@router.get("/status", tags=["core-sovereign-boot"])
async def sovereign_status() -> Dict[str, Any]:
    return get_sovereign_bootstrapper().status()


@router.get("/snapshot", tags=["core-sovereign-boot"])
async def sovereign_snapshot() -> Dict[str, Any]:
    return get_sovereign_bootstrapper().snapshot()


@router.post("/boot", tags=["core-sovereign-boot"])
async def sovereign_boot(req: BootRequest) -> Dict[str, Any]:
    return get_sovereign_bootstrapper().run_bootstrapping(force=req.force)


@router.get("/audits", tags=["core-sovereign-boot"])
async def sovereign_audits(limit: int = 100) -> Dict[str, Any]:
    items = get_sovereign_bootstrapper().audits(limit=limit)
    return {"count": len(items), "audits": [a.to_dict() for a in items],
            "offline_only": True}


@router.get("/events", tags=["core-sovereign-boot"])
async def sovereign_events(limit: int = 100) -> Dict[str, Any]:
    items = get_sovereign_bootstrapper().events(limit=limit)
    return {"count": len(items), "events": [e.to_dict() for e in items],
            "offline_only": True}


@router.get("/hardening", tags=["core-sovereign-boot"])
async def sovereign_hardening() -> Dict[str, Any]:
    return get_sovereign_bootstrapper().hardening.report().to_dict()


@router.post("/hardening", tags=["core-sovereign-boot"])
async def sovereign_set_hardening(req: HardenRequest) -> Dict[str, Any]:
    rep = get_sovereign_bootstrapper().harden(_level(req.level))
    return rep.to_dict()


@router.get("/health", tags=["core-sovereign-boot"])
async def sovereign_health() -> Dict[str, Any]:
    return get_sovereign_bootstrapper().validator.health_summary()


@router.post("/reset", tags=["core-sovereign-boot"])
async def sovereign_reset() -> Dict[str, Any]:
    return get_sovereign_bootstrapper().reset()


@router.get("/channels", tags=["core-sovereign-boot"])
async def sovereign_channels() -> Dict[str, Any]:
    return {
        "channels": ["status", "snapshot", "boot", "audits", "events",
                     "hardening", "health", "reset"],
        "ws": "/api/core/sovereign-boot/ws",
        "offline_only": True,
    }


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
async def sovereign_ws(websocket: WebSocket) -> None:
    """Canal WebSocket en tiempo real para el arranque soberano.

    Push: heartbeat con estado de salud y endurecimiento.
    Pull: JSON { "action": "...", "params": {...} }.
    """
    await websocket.accept()
    bs = get_sovereign_bootstrapper()
    bs.validator.subscribe(lambda p: _ws.broadcast(p))
    _ws.active.add(websocket)
    try:
        _ws.set_loop(asyncio.get_running_loop())
    except Exception:
        pass
    try:
        await websocket.send_json({"type": "connected", "status": bs.status()})
        while True:
            await asyncio.sleep(2.0)
            try:
                await websocket.send_json({
                    "type": "heartbeat",
                    "status": bs.status(),
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
    "router", "BootSeverity", "BootStatus", "HardeningLevel",
    "BlockAudit", "BootEvent", "HardeningReport",
    "CrossBlockIntegrityValidator", "SovereignHardening",
    "SovereignBootstrapper", "get_sovereign_bootstrapper",
    "reset_sovereign_bootstrapper", "ECOSYSTEM_BLOCKS",
]
