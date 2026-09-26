"""Analytics engine for AURA Advanced Usage Analytics, SLA Tracking & Cost Intelligence."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


class UsageTracker:
    """Registra métricas de uso."""

    def __init__(self) -> None:
        self.events: List[Dict[str, Any]] = []

    def record(self, event: Dict[str, Any]) -> Dict[str, Any]:
        event.setdefault("timestamp", datetime.utcnow().isoformat() + "Z")
        self.events.append(event)
        if len(self.events) > 500:
            self.events = self.events[-500:]
        return event

    def summary(self, limit: int = 100) -> Dict[str, Any]:
        return {"count": len(self.events[-limit:]), "events": self.events[-limit:]}


class SLACalculator:
    """Cálculo de SLA."""

    def __init__(self) -> None:
        self.checks: List[Dict[str, Any]] = []

    def evaluate(self, availability: float, latency_ms: float, error_rate: float) -> Dict[str, Any]:
        sla = {
            "availability": availability,
            "latency_ms": latency_ms,
            "error_rate": error_rate,
            "status": "healthy",
        }
        if availability < 0.99 or error_rate > 0.05:
            sla["status"] = "critical"
        elif availability < 0.995 or error_rate > 0.02 or latency_ms > 500:
            sla["status"] = "warning"
        self.checks.append(sla)
        return sla

    def latest(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.checks[-limit:]


class PerformanceMetrics:
    """Métricas de rendimiento."""

    def __init__(self) -> None:
        self.samples: List[Dict[str, Any]] = []

    def snapshot(self, cpu: float, ram: float, disk: float, latency_ms: float, throughput: float) -> Dict[str, Any]:
        sample = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "cpu": cpu,
            "ram": ram,
            "disk": disk,
            "latency_ms": latency_ms,
            "throughput": throughput,
        }
        self.samples.append(sample)
        if len(self.samples) > 200:
            self.samples = self.samples[-200:]
        return sample

    def history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.samples[-limit:]


class AnalyticsEngine:
    """Motor central de analítica."""

    def __init__(self) -> None:
        self.usage = UsageTracker()
        self.sla = SLACalculator()
        self.metrics = PerformanceMetrics()

    def record_usage(self, event: Dict[str, Any]) -> Dict[str, Any]:
        return self.usage.record(event)

    def evaluate_sla(self, availability: float, latency_ms: float, error_rate: float) -> Dict[str, Any]:
        return self.sla.evaluate(availability, latency_ms, error_rate)

    def snapshot_performance(self, cpu: float, ram: float, disk: float, latency_ms: float, throughput: float) -> Dict[str, Any]:
        return self.metrics.snapshot(cpu, ram, disk, latency_ms, throughput)

    def usage_summary(self, limit: int = 100) -> Dict[str, Any]:
        return self.usage.summary(limit=limit)

    def sla_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.sla.latest(limit=limit)

    def performance_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.metrics.history(limit=limit)
