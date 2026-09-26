"""Unification routes for AURA - Module 26.

Endpoints REST para el reporte de salud global, auto-recuperación y
orquestación unificada del ecosistema AURA.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query

from backend.self_healing import SelfHealingRuntime, CircuitState
from backend.system_unifier import CoreSystemRegistry, SystemOrchestrator
from backend.event_bus import EventBus

router = APIRouter(prefix="/api/system", tags=["system"])

self_healing = SelfHealingRuntime()
registry = CoreSystemRegistry()
event_bus = EventBus()
orchestrator = SystemOrchestrator(registry, event_bus)


@router.get("/status/full")
async def full_system_status() -> Dict[str, Any]:
    """Reporte consolidado de salud de los 26 módulos del sistema."""
    health = self_healing.health_report()
    unified = orchestrator.get_unified_status()
    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "total_modules": len(self_healing.module_names),
        "system_health": {
            "total": health["total_modules"],
            "healthy": health["healthy"],
            "degraded": health["degraded"],
            "critical": health["critical"],
        },
        "modules": self_healing.module_names,
        "circuit_breakers": [
            {
                "module": name,
                "state": cb.state.value,
                "failure_count": cb.failure_count,
            }
            for name, cb in self_healing.circuit_breakers.items()
        ],
        "unified_systems": unified["systems"],
        "recent_anomalies": health["anomalies"],
        "recent_recoveries": health["recoveries"],
    }


@router.post("/self-heal/trigger")
async def trigger_self_heal(
    payload: Dict[str, Any] = Body(
        ...,
        json_schema_extra={
            "example": {
                "module": "monitoring",
                "reason": "manual_trigger",
                "simulate": False,
                "metric": "error_rate",
                "value": 0.5,
            }
        },
    ),
) -> Dict[str, Any]:
    """Disparo manual o simulado de auto-recuperación."""
    reason = str(payload.get("reason", "manual_trigger"))
    module = str(payload.get("module", ""))
    simulate = bool(payload.get("simulate", False))

    if simulate:
        target_module = module or "monitoring"
        metric = str(payload.get("metric", "error_rate"))
        value = float(payload.get("value", 0.5))
        extra_metrics: Dict[str, float] = {}
        for k, v in (payload.get("params") or {}).items():
            try:
                extra_metrics[k] = float(v)
            except (TypeError, ValueError):
                pass
        simulated: Dict[str, float] = {metric: value, **extra_metrics}
        self_healing.health_metrics[target_module] = simulated
        monitor_result = await self_healing.monitor({target_module: simulated})

        breaker = self_healing.circuit_breakers.get(target_module)
        if breaker and breaker.state != CircuitState.CLOSED:
            heal_result = await self_healing.heal(target_module, f"simulation:{reason}")
        else:
            heal_result = {"skipped": True, "reason": "circuit_closed_no_anomaly"}

        return {
            "simulation": True,
            "module": target_module,
            "monitor": monitor_result,
            "healing": heal_result,
        }

    if module:
        if module not in self_healing.module_names:
            raise HTTPException(status_code=404, detail=f"Unknown module: {module}")
        result = await self_healing.heal(module, reason)
        return {"simulation": False, "result": result}

    healed: List[Dict[str, Any]] = []
    for name in self_healing.module_names:
        breaker = self_healing.circuit_breakers.get(name)
        if breaker and breaker.state != CircuitState.CLOSED:
            result = await self_healing.heal(name, f"{reason}_auto")
            healed.append({"module": name, "result": result})

    return {
        "simulation": False,
        "modules_checked": len(self_healing.module_names),
        "modules_healed": len(healed),
        "results": healed,
    }


@router.post("/orchestrate")
async def orchestrate(
    payload: Dict[str, Any] = Body(
        ...,
        json_schema_extra={
            "example": {
                "command": "status",
                "target": "monitoring",
                "params": {"detail": "full"},
            }
        },
    ),
) -> Dict[str, Any]:
    """Despacho de comandos unificados a través de todo el ecosistema AURA."""
    command = str(payload.get("command", "ping"))
    target = str(payload.get("target", ""))
    params = payload.get("params") or {}
    plan = payload.get("plan")

    if plan and isinstance(plan, list):
        results = await orchestrator.orchestrate_plan(plan)
        await orchestrator.event_bridge.publish_system_event(
            "orchestration_complete",
            {"steps": len(results), "successful": sum(1 for r in results if r["status"] == "success")},
            module="system_unification",
        )
        return {
            "status": "plan_executed",
            "steps": len(results),
            "results": results,
        }

    if not target:
        raise HTTPException(status_code=400, detail="target is required when not using a plan")

    result = await orchestrator.dispatch_command(command, target, params)
    return result
