"""Alert system for AURA Advanced Monitoring & Alerting."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class AlertRule:
    rule_id: str
    name: str
    metric: str
    field: str
    operator: str
    threshold: float
    severity: AlertSeverity
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


@dataclass
class Alert:
    alert_id: str
    rule_id: str
    metric: str
    field: str
    value: float
    threshold: float
    severity: AlertSeverity
    message: str
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    acknowledged: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)


class AlertEvaluator:
    """Evalúa reglas contra snapshots de métricas."""

    def __init__(self, rules: Optional[List[AlertRule]] = None) -> None:
        self.rules = rules or []

    def evaluate(self, snapshot: Dict[str, Any]) -> List[Alert]:
        alerts: List[Alert] = []
        for rule in self.rules:
            if not rule.enabled:
                continue
            metric = snapshot.get(rule.metric, {})
            value = metric.get(rule.field)
            if value is None:
                continue
            triggered = self._compare(value, rule.operator, rule.threshold)
            if triggered:
                alerts.append(self._build_alert(rule, value))
        return alerts

    def add_rule(self, rule: AlertRule) -> None:
        self.rules.append(rule)

    def _compare(self, value: float, operator: str, threshold: float) -> bool:
        if operator == ">":
            return value > threshold
        if operator == ">=":
            return value >= threshold
        if operator == "<":
            return value < threshold
        if operator == "<=":
            return value <= threshold
        if operator == "==":
            return value == threshold
        return False

    def _build_alert(self, rule: AlertRule, value: float) -> Alert:
        return Alert(
            alert_id=f"alert-{int(time.time() * 1000)}",
            rule_id=rule.rule_id,
            metric=rule.metric,
            field=rule.field,
            value=value,
            threshold=rule.threshold,
            severity=rule.severity,
            message=f"{rule.name}: {rule.metric}.{rule.field}={value} {rule.operator} {rule.threshold}",
        )


class NotificationDispatcher:
    """Despacha alertas a sinks configurados."""

    def __init__(self) -> None:
        self.sinks: List[Callable[[Alert], None]] = []
        self.logger = logging.getLogger("AURA.alerts")

    def register_sink(self, sink: Callable[[Alert], None]) -> None:
        self.sinks.append(sink)

    def dispatch(self, alert: Alert) -> None:
        for sink in self.sinks:
            try:
                sink(alert)
            except Exception as exc:
                self.logger.exception("Notification sink failed: %s", exc)
        self.logger.warning("Alert dispatched: %s", alert.message)


class AlertManager:
    """Gestor central de alertas."""

    def __init__(self) -> None:
        self.evaluator = AlertEvaluator()
        self.dispatcher = NotificationDispatcher()
        self.history: List[Alert] = []

    def configure_rules(self, rules: List[AlertRule]) -> None:
        self.evaluator = AlertEvaluator(rules=rules)

    def process_snapshot(self, snapshot: Dict[str, Any]) -> List[Alert]:
        alerts = self.evaluator.evaluate(snapshot)
        for alert in alerts:
            self.dispatcher.dispatch(alert)
            self.history.append(alert)
        if len(self.history) > 500:
            self.history = self.history[-500:]
        return alerts

    def latest_alerts(self, limit: int = 50) -> List[Alert]:
        return self.history[-limit:]
