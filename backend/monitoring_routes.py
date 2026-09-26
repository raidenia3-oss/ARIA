"""Monitoring routes for AURA observability."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.alert_system import AlertManager, AlertRule, AlertSeverity
from backend.monitoring_manager import MonitoringManager

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])
monitoring_manager = MonitoringManager()
alert_manager = AlertManager()


@router.get("/health")
async def monitoring_health() -> Dict[str, Any]:
    return {"status": "ok", "service": "monitoring"}


@router.get("/status")
async def monitoring_status() -> Dict[str, Any]:
    return monitoring_manager.get_status()


@router.get("/metrics")
async def monitoring_metrics(limit: int = 50) -> Dict[str, Any]:
    return monitoring_manager.get_metrics(limit=limit)


@router.get("/alerts")
async def monitoring_alerts(limit: int = 20) -> Dict[str, Any]:
    return monitoring_manager.get_alerts(limit=limit)


@router.get("/snapshot")
async def monitoring_snapshot() -> Dict[str, Any]:
    data = monitoring_manager.collect()
    monitoring_manager.save_snapshot()
    return data


@router.post("/rules")
async def monitoring_rules(payload: Dict[str, Any]) -> Dict[str, Any]:
    rules_payload = payload.get("rules", [])
    rules: list[AlertRule] = []
    for item in rules_payload:
        rules.append(AlertRule(
            rule_id=str(item.get("rule_id", f"rule-{len(rules)+1}")),
            name=str(item.get("name", "Unnamed Rule")),
            metric=str(item.get("metric", "cpu")),
            field=str(item.get("field", "usage_percent")),
            operator=str(item.get("operator", ">=")),
            threshold=float(item.get("threshold", 90)),
            severity=AlertSeverity(str(item.get("severity", "warning"))),
            enabled=bool(item.get("enabled", True)),
        ))
    alert_manager.configure_rules(rules)
    return {"configured_rules": len(rules)}


@router.get("/rules")
async def monitoring_rules_list() -> Dict[str, Any]:
    rules = getattr(alert_manager.evaluator, "rules", [])
    return {
        "count": len(rules),
        "rules": [
            {
                "rule_id": r.rule_id,
                "name": r.name,
                "metric": r.metric,
                "field": r.field,
                "operator": r.operator,
                "threshold": r.threshold,
                "severity": r.severity.value,
                "enabled": r.enabled,
            }
            for r in rules
        ],
    }
