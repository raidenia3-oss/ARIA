"""BLOQUE 81 - Comprehensive Diagnostics REST Endpoints (/api/diagnostics/omni).

Endpoints para ejecutar la suite omnidiagnóstica, auditar la salud de los
submódulos y exportar informes de conformidad soberana (100% offline).
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.diagnostics.omni import (
    DiagnosticConfig,
    OmniAuditor,
    get_omni_auditor,
    reset_omni_auditor,
)

router = APIRouter(prefix="/api/diagnostics/omni", tags=["omni-diagnostics"])


def _check_key(provided: Optional[str]) -> None:
    expected = os.getenv("AURA_API_KEY", "")
    if expected and provided != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


class RunRequest(BaseModel):
    only: Optional[List[str]] = None
    skip: Optional[List[str]] = None


@router.get("/status", response_model=Dict[str, Any])
async def omni_status(x_api_key: Optional[str] = None) -> Dict[str, Any]:
    """Estado del motor omnidiagnóstico (checks registrados, último reporte)."""
    _check_key(x_api_key)
    auditor = get_omni_auditor()
    return {
        "checks_registered": auditor.check_names(),
        "checks_total": len(auditor.check_names()),
        "last_report": auditor.last_report,
        "history_count": len(auditor.history()),
        "offline_only": True,
    }


@router.post("/run", response_model=Dict[str, Any])
async def omni_run(req: Optional[RunRequest] = None,
                   x_api_key: Optional[str] = None) -> Dict[str, Any]:
    """Ejecuta la suite completa de diagnóstico (o subconjunto con only/skip)."""
    _check_key(x_api_key)
    auditor = get_omni_auditor()
    only = req.only if req else None
    skip = req.skip if req else None
    return auditor.run_all(only=only, skip=skip)


@router.get("/checks", response_model=Dict[str, Any])
async def omni_checks(x_api_key: Optional[str] = None) -> Dict[str, Any]:
    """Lista los checks disponibles en el auditor."""
    _check_key(x_api_key)
    return {"checks": get_omni_auditor().check_names(), "offline_only": True}


@router.get("/history", response_model=Dict[str, Any])
async def omni_history(limit: Optional[int] = Query(None, ge=1, le=200),
                       x_api_key: Optional[str] = None) -> Dict[str, Any]:
    """Historial de reportes de diagnóstico."""
    _check_key(x_api_key)
    return {"history": get_omni_auditor().history(limit=limit), "offline_only": True}


@router.get("/export", response_model=Dict[str, Any])
async def omni_export(x_api_key: Optional[str] = None) -> Dict[str, Any]:
    """Exporta el último reporte (o ejecuta uno nuevo) a JSON local."""
    _check_key(x_api_key)
    auditor = get_omni_auditor()
    path = auditor.export_report()
    return {"exported": path, "report_id": (auditor.last_report or {}).get("report_id"),
            "offline_only": True}


@router.post("/reset", response_model=Dict[str, Any])
async def omni_reset(x_api_key: Optional[str] = None) -> Dict[str, Any]:
    """Reinicia el motor omnidiagnóstico (solo operador local)."""
    _check_key(x_api_key)
    reset_omni_auditor()
    auditor = get_omni_auditor()
    return {"reset": True, "checks_registered": auditor.check_names(), "offline_only": True}


@router.get("/health", response_model=Dict[str, Any])
async def omni_health(x_api_key: Optional[str] = None) -> Dict[str, Any]:
    """Salud rápida del motor de diagnóstico."""
    _check_key(x_api_key)
    auditor = get_omni_auditor()
    return {"ok": True, "checks_registered": len(auditor.check_names()),
            "last_report_id": (auditor.last_report or {}).get("report_id"),
            "offline_only": True}