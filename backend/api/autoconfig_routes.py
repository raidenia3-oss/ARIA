# -*- coding: utf-8 -*-
"""AURA OS — Auto-Config API Routes.

Endpoints para auto-configuracion de agentes.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel

from backend.agents.agent_autoconfigurator import (
    AgentAutoConfigurator,
    ImprovementPlan,
)

logger = logging.getLogger("AURA.API.AutoConfig")

router = APIRouter(prefix="/api/agents", tags=["agents"])

_autoconfig = AgentAutoConfigurator()
_IMPROVEMENT_HISTORY: List[Dict[str, Any]] = []


class AutoImproveRequest(BaseModel):
    force: bool = False
    agents: Optional[List[str]] = None


class ImprovementFilter(BaseModel):
    agent_name: Optional[str] = None
    since: Optional[str] = None
    status: Optional[str] = None


@router.get("/performance")
async def get_performance() -> Dict[str, Any]:
    """Retorna accuracy y speed de cada agente."""
    try:
        results: Dict[str, Any] = {}
        for name in ["fanfic", "general", "code", "research", "newsletter", "social", "analytics", "netrunner"]:
            try:
                perf = await _autoconfig.analyze_agent_performance(name)
                if "error" not in perf:
                    results[name] = {
                        "accuracy": perf["accuracy"],
                        "speed": perf["speed"],
                        "errors": perf["errors"],
                        "total_runs": perf["total_runs"],
                    }
            except Exception as exc:
                results[name] = {"error": str(exc)}

        logger.info("Performance check: %d agents", len(results))
        return {
            "timestamp": datetime.now().isoformat(),
            "agents": results,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/weaknesses")
async def get_weaknesses() -> Dict[str, Any]:
    """Identifica prioridades de mejora."""
    try:
        result = await _autoconfig.detect_weaknesses()
        return {
            "timestamp": datetime.now().isoformat(),
            "weak_agents": result.get("weak_agents", 0),
            "priorities": result.get("priorities", []),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/auto-improve")
async def auto_improve(request: AutoImproveRequest = Body(...)) -> Dict[str, Any]:
    """Ejecuta mejoras automaticas."""
    try:
        plan = await _autoconfig.propose_improvements()
        plan_id = plan.get("plan_id", "unknown")

        logger.info("Auto-improve started: plan %s", plan_id)

        result = await _autoconfig.apply_improvements(plan)

        _IMPROVEMENT_HISTORY.append({
            "plan_id": plan_id,
            "actions": plan.get("actions", []),
            "applied": result["applied"],
            "errors": result["errors"],
            "timestamp": datetime.now().isoformat(),
        })

        return {
            "status": "improving",
            "plan_id": plan_id,
            "eta": "30min",
            "applied": result["applied"],
            "errors": result["errors"],
            "details": result,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/improvement-history")
async def improvement_history(filter_req: ImprovementFilter = Body(None)) -> Dict[str, Any]:
    """Historial de auto-mejoras."""
    history = _IMPROVEMENT_HISTORY

    if filter_req.agent_name:
        history = [h for h in history if any(a["agent"] == filter_req.agent_name for a in h.get("actions", []))]
    if filter_req.since:
        history = [h for h in history if h.get("timestamp", "") >= filter_req.since]
    if filter_req.status:
        history = [h for h in history if h.get("status") == filter_req.status]

    return {
        "total": len(history),
        "history": history,
        "timestamp": datetime.now().isoformat(),
    }
