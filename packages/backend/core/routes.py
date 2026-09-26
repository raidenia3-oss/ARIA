"""AURA Master Diagnostics REST — BLOQUE 61.

Endpoints para el diagnostico maestro del ecosistema AURA:
- GET  /api/master/health         — snapshot completo (readiness + health daemon).
- GET  /api/master/readiness      — solo readiness para flujos E2E.
- GET  /api/master/ports          — estado de puertos criticos del ecosistema.
- GET  /api/master/modules        — modulos importables del backend.
- GET  /api/master/env            — presencia de variables de entorno (nunca valores).
- POST /api/master/snapshot/force — fuerza un snapshot fresco.

Autenticacion: local-first. Si AURA_API_KEY esta definida se exige X-API-Key.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException

from backend.core.diagnostics import (
    ECOSYSTEM_PORTS,
    _e2e_readiness,
    _env_status,
    _ecosystem_modules,
    master_health,
    master_readiness,
    master_snapshot,
)

router = APIRouter(prefix="/api/master", tags=["master-diagnostics"])


def _check_api_key(provided: Optional[str]) -> None:
    expected = os.getenv("AURA_API_KEY", "")
    if expected and provided != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


@router.get("/health")
async def master_health_endpoint(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Snapshot completo del diagnostico maestro."""
    _check_api_key(x_api_key)
    return master_health()


@router.get("/readiness")
async def master_readiness_endpoint(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Readiness para flujos E2E: puertos, modulos, env vars."""
    _check_api_key(x_api_key)
    return master_readiness()


@router.get("/ports")
async def master_ports_endpoint(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Estado de los puertos criticos del ecosistema AURA."""
    _check_api_key(x_api_key)
    readiness = _e2e_readiness()
    return {
        "ports": {
            k: readiness.get(f"{k}_port")
            for k in list(ECOSYSTEM_PORTS.keys())
        },
        "timestamp": readiness.get("timestamp"),
    }


@router.get("/modules")
async def master_modules_endpoint(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Modulos importables del backend (verificado en tiempo real)."""
    _check_api_key(x_api_key)
    return _ecosystem_modules()


@router.get("/env")
async def master_env_endpoint(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Presencia de variables de entorno criticas (sin exponer valores)."""
    _check_api_key(x_api_key)
    return _env_status()


@router.post("/snapshot/force")
async def master_force_snapshot(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Fuerza un snapshot fresco del diagnostico maestro."""
    _check_api_key(x_api_key)
    return master_snapshot()