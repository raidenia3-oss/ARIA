"""AURA Local Diagnostics & System Health — endpoints REST (Bloque 48).

- GET  /api/system/health           — snapshot completo (host + servicios + Jan).
- GET  /api/system/health/host      — solo métricas del host.
- GET  /api/system/health/services  — estado de puertos/daemons locales (check_all).
- GET  /api/system/health/services/status  — estado resumido + historial de cambios.
- GET  /api/system/health/services/history — historial de transiciones up/down.
- GET  /api/system/health/jan       — estado del motor local Jan/Ollama.
- POST /api/system/health/jan/check — fuerza comprobación inmediata de Jan.

Autenticación: si AURA_API_KEY está definida se exige X-API-Key
(local-first: sin key configurada, el endpoint queda abierto en red local).
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import JSONResponse

from backend.diagnostics.health import (
    get_health_daemon,
    get_system_resources,
    probe_service_status,
)

router = APIRouter(prefix="/api/system/health", tags=["system-health"])


def _check_api_key(provided: Optional[str]) -> None:
    expected = os.getenv("AURA_API_KEY", "")
    if expected and provided != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


@router.get("")
async def health_snapshot(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Snapshot completo de salud del ecosistema AURA local."""
    _check_api_key(x_api_key)
    return get_health_daemon().snapshot()


@router.get("/host")
async def health_host(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Métricas de recursos del host (CPU, RAM, disco, red, uptime)."""
    _check_api_key(x_api_key)
    return get_system_resources()


@router.get("/services")
async def health_services(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Estado de los servicios/daemons locales por puerto TCP."""
    _check_api_key(x_api_key)
    return get_health_daemon().service_watchdog.check_all()


@router.get("/services/status")
async def health_services_status(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Estado resumido + historial de cambios de los servicios."""
    _check_api_key(x_api_key)
    return get_health_daemon().service_watchdog.get_status()


@router.get("/services/history")
async def health_services_history(
    key: Optional[str] = Query(None, description="Filtrar por clave de servicio"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Historial de transiciones up/down de los servicios vigilados."""
    _check_api_key(x_api_key)
    return get_health_daemon().service_watchdog.get_history(key)


@router.get("/jan")
async def health_jan(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Estado del motor local Jan/Ollama (modelos disponibles, endpoint)."""
    _check_api_key(x_api_key)
    return get_health_daemon().jan_watchdog.get_last() or get_health_daemon().jan_watchdog.check()


@router.post("/jan/check")
async def health_jan_check(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Fuerza una comprobación inmediata del motor local Jan/Ollama."""
    _check_api_key(x_api_key)
    return get_health_daemon().jan_watchdog.check()