"""Cost manager for AURA - Module 22: Cost Intelligence & Budget Alerts.

Provides operational cost estimation, budget threshold management and
billing intelligence aggregation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


class CostEstimator:
    """Estima costos operacionales basados en consumo de recursos."""

    DEFAULT_RATES: Dict[str, float] = {
        "cpu_hour": 0.05,
        "ram_gb_hour": 0.01,
        "disk_gb_month": 0.10,
        "api_call": 0.0002,
        "bandwidth_gb": 0.09,
    }

    def __init__(
        self,
        session_factory: Optional[Any] = None,
        rates: Optional[Dict[str, float]] = None,
    ) -> None:
        self.session_factory = session_factory
        self.rates: Dict[str, float] = dict(self.DEFAULT_RATES)
        if rates:
            self.rates.update(rates)
        self.cost_history: List[Dict[str, Any]] = []

    def estimate(self, usage: Dict[str, Any]) -> Dict[str, Any]:
        cpu_hours = float(usage.get("cpu_hours", 0.0))
        ram_gb_hours = float(usage.get("ram_gb_hours", 0.0))
        disk_gb = float(usage.get("disk_gb", 0.0))
        api_calls = float(usage.get("api_calls", 0.0))
        bandwidth_gb = float(usage.get("bandwidth_gb", 0.0))

        breakdown: Dict[str, float] = {
            "cpu": cpu_hours * self.rates["cpu_hour"],
            "ram": ram_gb_hours * self.rates["ram_gb_hour"],
            "disk": disk_gb * self.rates["disk_gb_month"],
            "api_calls": api_calls * self.rates["api_call"],
            "bandwidth": bandwidth_gb * self.rates["bandwidth_gb"],
        }
        total = sum(breakdown.values())

        record: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "usage": usage,
            "cost_breakdown": breakdown,
            "total_cost": round(total, 4),
            "currency": "USD",
        }
        self.cost_history.append(record)
        if len(self.cost_history) > 500:
            self.cost_history = self.cost_history[-500:]
        return record

    def history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.cost_history[-limit:]


class BudgetAlertManager:
    """Gestiona umbrales presupuestarios y genera alertas de gasto."""

    def __init__(self) -> None:
        self.budgets: Dict[str, Dict[str, Any]] = {}
        self.alerts: List[Dict[str, Any]] = []

    def set_budget(
        self,
        resource: str,
        monthly_budget: float,
        thresholds: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        self.budgets[resource] = {
            "monthly_budget": monthly_budget,
            "thresholds": thresholds or {"warning": 0.7, "critical": 0.9},
        }
        return self.budgets[resource]

    def check_budget(self, resource: str, current_cost: float) -> Dict[str, Any]:
        budget = self.budgets.get(resource)
        if not budget:
            return {
                "resource": resource,
                "status": "no_budget_configured",
                "current_cost": round(current_cost, 4),
            }
        monthly_budget = budget["monthly_budget"]
        ratio = current_cost / monthly_budget if monthly_budget > 0 else 0.0
        thresholds = budget["thresholds"]

        if ratio >= thresholds["critical"]:
            status = "critical"
        elif ratio >= thresholds["warning"]:
            status = "warning"
        else:
            status = "ok"

        alert: Dict[str, Any] = {
            "resource": resource,
            "current_cost": round(current_cost, 4),
            "monthly_budget": monthly_budget,
            "usage_ratio": round(ratio, 4),
            "status": status,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        if status in ("warning", "critical"):
            self.alerts.append(alert)
            if len(self.alerts) > 200:
                self.alerts = self.alerts[-200:]
        return alert

    def latest_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.alerts[-limit:]

    def get_budgets(self) -> Dict[str, Any]:
        return self.budgets


class BillingIntelligence:
    """Motor central de inteligencia de facturación."""

    def __init__(self, session_factory: Optional[Any] = None) -> None:
        self.cost_estimator = CostEstimator(session_factory)
        self.budget_manager = BudgetAlertManager()

    def estimate_cost(self, usage: Dict[str, Any]) -> Dict[str, Any]:
        estimate = self.cost_estimator.estimate(usage)
        breakdown = estimate.get("cost_breakdown", {})
        for resource, cost in breakdown.items():
            if resource in self.budget_manager.budgets:
                self.budget_manager.check_budget(resource, cost)
        estimate["budget_alerts"] = self.budget_manager.latest_alerts()
        return estimate

    def get_costs(self, limit: int = 50) -> Dict[str, Any]:
        costs = self.cost_estimator.history(limit=limit)
        return {"count": len(costs), "costs": costs}

    def get_budget_alerts(self, limit: int = 50) -> Dict[str, Any]:
        alerts = self.budget_manager.latest_alerts(limit=limit)
        return {"count": len(alerts), "alerts": alerts}

    def set_budget(
        self,
        resource: str,
        monthly_budget: float,
        thresholds: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        return self.budget_manager.set_budget(resource, monthly_budget, thresholds)
