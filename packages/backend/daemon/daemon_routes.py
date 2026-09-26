"""BLOQUE 80 - Daemon Lifecycle Management REST Endpoints (/api/daemon)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from backend.daemon.bootstrapper import get_daemon_controller
from backend.daemon.aura_daemon import get_daemon

router = APIRouter(prefix="/api/daemon", tags=["daemon"])


class ConfigRequest(BaseModel):
    autostart_enabled: Optional[bool] = None
    restart_on_failure: Optional[bool] = None
    max_restarts: Optional[int] = None


class ExecuteRequest(BaseModel):
    execute: bool = False


@router.get("/status", response_model=Dict[str, Any])
async def daemon_status():
    ctl = get_daemon_controller()
    st = ctl.state()
    st["bootstrapper"] = ctl.bootstrapper.status()
    return st


@router.get("/config", response_model=Dict[str, Any])
async def daemon_config():
    return get_daemon_controller().bootstrapper.status()


@router.post("/config", response_model=Dict[str, Any])
async def daemon_configure(req: ConfigRequest):
    cfg = get_daemon_controller().bootstrapper.configure(
        autostart_enabled=req.autostart_enabled,
        restart_on_failure=req.restart_on_failure,
        max_restarts=req.max_restarts,
    )
    return {"ok": True, "config": cfg.to_dict()}


@router.post("/install", response_model=Dict[str, Any])
async def daemon_install(req: Optional[ExecuteRequest] = None):
    execute = req.execute if req else False
    return get_daemon_controller().bootstrapper.install(execute=execute)


@router.post("/uninstall", response_model=Dict[str, Any])
async def daemon_uninstall(req: Optional[ExecuteRequest] = None):
    execute = req.execute if req else False
    return get_daemon_controller().bootstrapper.uninstall(execute=execute)


@router.get("/artifacts", response_model=Dict[str, Any])
async def daemon_artifacts():
    ctl = get_daemon_controller()
    return {"artifacts": ctl.bootstrapper.artifacts()}


@router.post("/start", response_model=Dict[str, Any])
async def daemon_start():
    return get_daemon_controller().start()


@router.post("/stop", response_model=Dict[str, Any])
async def daemon_stop():
    return get_daemon_controller().stop()


@router.post("/restart", response_model=Dict[str, Any])
async def daemon_restart():
    return get_daemon_controller().restart()


@router.get("/health", response_model=Dict[str, Any])
async def daemon_health():
    return get_daemon_controller().health()


# ── OPCION A: Revenue Endpoints ──────────────────────────────────────

@router.get("/revenue/today", response_model=Dict[str, Any])
async def revenue_today():
    """Retorna ingresos del dia actual (USD)."""
    daemon = get_daemon()
    return {
        "total_earned_usd": daemon.total_revenue,
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/revenue/log", response_model=Dict[str, Any])
async def revenue_log(limit: int = 20):
    """Retorna historial de ingresos (ultimos N ciclos)."""
    daemon = get_daemon()
    log = daemon.revenue_aggregator.revenue_log
    return {
        "revenue_log": log[-limit:] if limit > 0 else log,
        "total_entries": len(log),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/revenue/status", response_model=Dict[str, Any])
async def revenue_status():
    """Estado completo del sistema de revenue."""
    daemon = get_daemon()
    return {
        "daemon_active": daemon.active,
        "total_revenue_usd": round(daemon.total_revenue, 2),
        "revenue_log_entries": len(daemon.revenue_aggregator.revenue_log),
        "last_cycle": daemon.revenue_aggregator.revenue_log[-1] if daemon.revenue_aggregator.revenue_log else None,
        "timestamp": datetime.now().isoformat(),
    }