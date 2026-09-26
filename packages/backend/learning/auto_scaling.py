# -*- coding: utf-8 -*-
"""AURA OS — Auto Scaler.

Identifies bottlenecks in parallel execution,
distributes load across available cores,
and auto-adjusts concurrency levels.
"""
from __future__ import annotations

import logging
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURA.AutoScaler")


@dataclass
class Bottleneck:
    bottleneck_id: str
    component: str
    metric: str
    value: float
    threshold: float
    severity: str
    detected_at: float = field(default_factory=time.time)


@dataclass
class ScaleDecision:
    decision_id: str
    component: str
    action: str
    current_parallel: int
    new_parallel: int
    reason: str
    applied: bool = False


class AutoScaler:
    """Monitors and auto-scales AURA's parallel execution."""

    METRICS_FILE = Path("data/learning/metrics.json")
    MAX_PARALLEL = 8
    MIN_PARALLEL = 1

    def __init__(self, default_parallel: int = 4) -> None:
        self.default_parallel = default_parallel
        self.bottlenecks: List[Bottleneck] = []
        self.decisions: List[ScaleDecision] = []
        self.metrics: Dict[str, float] = {
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "task_queue_depth": 0,
            "avg_task_duration": 0.0,
            "success_rate": 1.0,
        }
        self._start_times: Dict[str, float] = {}
        self._task_counts: Dict[str, int] = {}
        self._success_counts: Dict[str, int] = {}
        self.METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def record_task_start(self, component: str) -> None:
        self._start_times[component] = time.time()

    def record_task_end(self, component: str, success: bool) -> float:
        start = self._start_times.pop(component, time.time())
        duration = time.time() - start
        self._task_counts[component] = self._task_counts.get(component, 0) + 1
        if success:
            self._success_counts[component] = self._success_counts.get(component, 0) + 1
        self.metrics[f"{component}_avg_duration"] = duration
        self.metrics["task_queue_depth"] = len(self._start_times)
        return duration

    def update_system_metrics(self, cpu: float, memory: float) -> None:
        self.metrics["cpu_usage"] = cpu
        self.metrics["memory_usage"] = memory
        self._detect_bottlenecks()

    def get_parallelism(self, component: str) -> int:
        base = self.default_parallel
        bottleneck = next((b for b in self.bottlenecks if b.component == component), None)
        if bottleneck:
            if bottleneck.severity == "critical":
                return max(self.MIN_PARALLEL, base // 2)
            elif bottleneck.severity == "high":
                return max(self.MIN_PARALLEL, base - 1)
        if self.metrics["cpu_usage"] > 0.8:
            return max(self.MIN_PARALLEL, self.default_parallel - 2)
        if self.metrics["cpu_usage"] < 0.3 and self.metrics["memory_usage"] < 0.5:
            if self.metrics["cpu_usage"] == 0.0 and self.metrics["memory_usage"] == 0.0:
                return base
            return min(self.MAX_PARALLEL, self.default_parallel + 2)
        return base

    def _detect_bottlenecks(self) -> None:
        cpu = self.metrics.get("cpu_usage", 0)
        memory = self.metrics.get("memory_usage", 0)
        duration = self.metrics.get("avg_task_duration", 0)
        if cpu > 0.9:
            self._add_bottleneck("cpu", "cpu_usage", cpu, 0.85, "critical")
        elif cpu > 0.75:
            self._add_bottleneck("cpu", "cpu_usage", cpu, 0.75, "high")
        if memory > 0.85:
            self._add_bottleneck("memory", "memory_usage", memory, 0.80, "critical")
        elif memory > 0.70:
            self._add_bottleneck("memory", "memory_usage", memory, 0.70, "high")
        if duration > 30:
            self._add_bottleneck("tasks", "avg_task_duration", duration, 30, "high")
        self.bottlenecks = [b for b in self.bottlenecks if time.time() - b.detected_at < 300]

    def _add_bottleneck(self, component: str, metric: str, value: float, threshold: float, severity: str) -> None:
        existing = next((b for b in self.bottlenecks if b.component == component and time.time() - b.detected_at < 60), None)
        if existing:
            existing.value = value
            existing.severity = severity
            return
        bid = f"BNK-{int(time.time())}-{len(self.bottlenecks)}"
        self.bottlenecks.append(Bottleneck(
            bottleneck_id=bid, component=component, metric=metric,
            value=round(value, 4), threshold=threshold, severity=severity,
        ))
        logger.warning("Bottleneck: %s=%.3f (threshold %.2f)", component, value, threshold)

    def scale(self, component: str, reason: str = "") -> ScaleDecision:
        current = self.get_parallelism(component)
        new_parallel = self.get_parallelism(component)
        if current == new_parallel and not reason:
            return ScaleDecision(
                decision_id=f"SCD-{int(time.time())}",
                component=component,
                action="maintain",
                current_parallel=current,
                new_parallel=new_parallel,
                reason="No change needed",
            )
        action = "scale_up" if new_parallel > current else "scale_down"
        decision = ScaleDecision(
            decision_id=f"SCD-{int(time.time())}",
            component=component,
            action=action,
            current_parallel=current,
            new_parallel=new_parallel,
            reason=reason or f"Auto-scaled {component}",
        )
        self.decisions.append(decision)
        self._save()
        return decision

    def get_bottlenecks_report(self) -> Dict[str, Any]:
        return {
            "active_bottlenecks": [b.__dict__ for b in self.bottlenecks],
            "total_detected": len(self.bottlenecks),
            "decisions": len(self.decisions),
            "last_decisions": [d.__dict__ for d in self.decisions[-5:]],
        }

    def get_perf_report(self) -> Dict[str, Any]:
        return {
            "metrics": self.metrics,
            "task_counts": self._task_counts,
            "success_rates": {
                comp: self._success_counts.get(comp, 0) / max(1, self._task_counts.get(comp, 1))
                for comp in self._task_counts
            },
        }

    def _load(self) -> None:
        try:
            if self.METRICS_FILE.exists():
                data = json.loads(self.METRICS_FILE.read_text())
                self.metrics.update(data.get("metrics", {}))
        except Exception:
            pass

    def _save(self) -> None:
        try:
            data = {
                "metrics": self.metrics,
                "bottlenecks": [b.__dict__ for b in self.bottlenecks],
                "decisions": [d.__dict__ for d in self.decisions],
            }
            self.METRICS_FILE.write_text(json.dumps(data, indent=2, default=str))
        except Exception:
            pass


auto_scaler = AutoScaler()
