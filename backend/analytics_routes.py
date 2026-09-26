"""Analytics & billing routes for AURA.

Module 22: Advanced Usage Analytics, SLA Tracking & Cost Intelligence.

Endpoints:
  - GET  /api/analytics/usage          → usage summary
  - POST /api/analytics/usage          → record a usage event
  - GET  /api/analytics/sla           → SLA check history
  - POST /api/analytics/sla            → record an SLA evaluation
  - GET  /api/analytics/performance   → performance metric history
  - GET  /api/billing/costs            → cost estimation history
  - POST /api/billing/costs            → submit usage, get cost estimate
  - GET  /api/billing/budget-alerts    → budget alert history
  - POST /api/billing/budget-alerts    → configure a budget threshold
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Query

from backend.analytics_engine import AnalyticsEngine
from backend.cost_manager import BillingIntelligence

router = APIRouter(prefix="/api/analytics", tags=["analytics"])
billing_router = APIRouter(prefix="/api/billing", tags=["billing"])

_analytics: Optional[AnalyticsEngine] = None
_billing: Optional[BillingIntelligence] = None


def init_analytics(db_session_factory: Any = None) -> None:
    """Initialize analytics and billing engines (called from main.py startup)."""
    global _analytics, _billing
    _analytics = AnalyticsEngine()
    _billing = BillingIntelligence(db_session_factory)


def _get_analytics() -> AnalyticsEngine:
    if _analytics is None:
        raise HTTPException(status_code=500, detail="Analytics engine not initialized")
    return _analytics


def _get_billing() -> BillingIntelligence:
    if _billing is None:
        raise HTTPException(status_code=500, detail="Billing engine not initialized")
    return _billing


# --------------------------------------------------------------------------- #
#  Usage Analytics                                                             #
# --------------------------------------------------------------------------- #
@router.get("/usage")
async def get_usage(limit: int = Query(100, ge=1, le=500)) -> Dict[str, Any]:
    return _get_analytics().usage_summary(limit=limit)


@router.post("/usage")
async def record_usage(
    event: Dict[str, Any] = Body(..., json_schema_extra={"example": {"type": "narrative_generated", "module": "narrative"}}),
) -> Dict[str, Any]:
    return _get_analytics().record_usage(event)


# --------------------------------------------------------------------------- #
#  SLA Tracking                                                                #
# --------------------------------------------------------------------------- #
@router.get("/sla")
async def get_sla(limit: int = Query(20, ge=1, le=100)) -> Dict[str, Any]:
    checks = _get_analytics().sla_history(limit=limit)
    return {"count": len(checks), "checks": checks}


@router.post("/sla")
async def record_sla(
    payload: Dict[str, Any] = Body(..., json_schema_extra={"example": {"availability": 0.999, "latency_ms": 120, "error_rate": 0.01}}),
) -> Dict[str, Any]:
    return _get_analytics().evaluate_sla(
        availability=float(payload.get("availability", 1.0)),
        latency_ms=float(payload.get("latency_ms", 0.0)),
        error_rate=float(payload.get("error_rate", 0.0)),
    )


@router.get("/performance")
async def get_performance(limit: int = Query(50, ge=1, le=200)) -> Dict[str, Any]:
    metrics = _get_analytics().performance_history(limit=limit)
    return {"count": len(metrics), "metrics": metrics}


# --------------------------------------------------------------------------- #
#  Cost Intelligence                                                           #
# --------------------------------------------------------------------------- #
@billing_router.get("/costs")
async def get_costs(limit: int = Query(50, ge=1, le=200)) -> Dict[str, Any]:
    return _get_billing().get_costs(limit=limit)


@billing_router.post("/costs")
async def estimate_costs(
    usage: Dict[str, Any] = Body(
        ...,
        json_schema_extra={
            "example": {
                "cpu_hours": 10.5,
                "ram_gb_hours": 40.0,
                "disk_gb": 100,
                "api_calls": 50000,
                "bandwidth_gb": 25.0,
            }
        },
    ),
) -> Dict[str, Any]:
    return _get_billing().estimate_cost(usage)


# --------------------------------------------------------------------------- #
#  Budget Alerts                                                               #
# --------------------------------------------------------------------------- #
@billing_router.get("/budget-alerts")
async def get_budget_alerts(limit: int = Query(50, ge=1, le=200)) -> Dict[str, Any]:
    return _get_billing().get_budget_alerts(limit=limit)


@billing_router.post("/budget-alerts")
async def configure_budget(
    payload: Dict[str, Any] = Body(
        ...,
        json_schema_extra={"example": {"resource": "cpu", "monthly_budget": 500.0, "thresholds": {"warning": 0.7, "critical": 0.9}}},
    ),
) -> Dict[str, Any]:
    return _get_billing().set_budget(
        resource=payload.get("resource", "default"),
        monthly_budget=float(payload.get("monthly_budget", 0.0)),
        thresholds=payload.get("thresholds"),
    )
