# -*- coding: utf-8 -*-
"""AURA OS — Trigger Engine.

Monitors conditions and triggers automations
when thresholds are met or schedules fire.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("AURA.Triggers")


@dataclass
class TriggerCondition:
    condition_id: str
    name: str
    metric: str
    operator: str
    threshold: float
    action: str
    active: bool = True
    last_checked: float = 0.0
    triggered_count: int = 0


@dataclass
class TriggerEvent:
    event_id: str
    condition_id: str
    metric_value: float
    threshold: float
    triggered_at: float = field(default_factory=time.time)
    action: str = ""


class TriggerEngine:
    """Evaluates conditions and fires automations when met."""

    STORAGE_FILE = Path("data/learning/triggers.json")
    CHECK_INTERVAL = 60

    def __init__(self) -> None:
        self.conditions: Dict[str, TriggerCondition] = {}
        self.events: List[TriggerEvent] = []
        self._monitored_values: Dict[str, float] = {}
        self._action_callbacks: Dict[str, Callable] = {}
        self.STORAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def add_condition(self, condition_id: str, name: str, metric: str,
                      operator: str, threshold: float, action: str) -> TriggerCondition:
        condition = TriggerCondition(
            condition_id=condition_id,
            name=name,
            metric=metric,
            operator=operator,
            threshold=threshold,
            action=action,
        )
        self.conditions[condition_id] = condition
        self._save()
        logger.info("Condition added: %s (%s %s %s)", metric, operator, threshold, action)
        return condition

    def remove_condition(self, condition_id: str) -> bool:
        if condition_id in self.conditions:
            del self.conditions[condition_id]
            self._save()
            return True
        return False

    def set_value(self, metric: str, value: float) -> None:
        self._monitored_values[metric] = value

    def register_action(self, action_name: str, callback: Callable) -> None:
        self._action_callbacks[action_name] = callback

    def evaluate(self, condition: TriggerCondition) -> bool:
        value = self._monitored_values.get(condition.metric)
        if value is None:
            return False

        triggered = False
        if condition.operator == ">":
            triggered = value > condition.threshold
        elif condition.operator == ">=":
            triggered = value >= condition.threshold
        elif condition.operator == "<":
            triggered = value < condition.threshold
        elif condition.operator == "<=":
            triggered = value <= condition.threshold
        elif condition.operator == "==":
            triggered = value == condition.threshold
        elif condition.operator == "!=":
            triggered = value != condition.threshold

        if triggered and condition.active:
            condition.triggered_count += 1
            condition.last_checked = time.time()
            event = TriggerEvent(
                event_id=f"TRG-{int(time.time())}",
                condition_id=condition.condition_id,
                metric_value=value,
                threshold=condition.threshold,
                action=condition.action,
            )
            self.events.append(event)
            logger.info("Trigger fired: %s (%.4f %s %.4f)", condition.name, value, condition.operator, condition.threshold)
            if condition.action in self._action_callbacks:
                try:
                    self._action_callbacks[condition.action]()
                except Exception as exc:
                    logger.error("Action %s failed: %s", condition.action, exc)
            self._save()
        return triggered

    def check_all(self) -> List[TriggerEvent]:
        new_events = []
        for condition in self.conditions.values():
            if self.evaluate(condition):
                new_events.append(self.events[-1])
        return new_events

    def get_active_conditions(self) -> List[TriggerCondition]:
        return [c for c in self.conditions.values() if c.active]

    def get_triggered_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        return [e.__dict__ for e in self.events[-limit:]]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_conditions": len(self.conditions),
            "active": sum(1 for c in self.conditions.values() if c.active),
            "total_events": len(self.events),
            "recent_events": len(self.events),
            "monitored_metrics": len(self._monitored_values),
        }

    def _save(self) -> None:
        try:
            data = {
                "conditions": [
                    {
                        "condition_id": c.condition_id,
                        "name": c.name,
                        "metric": c.metric,
                        "operator": c.operator,
                        "threshold": c.threshold,
                        "action": c.action,
                        "active": c.active,
                        "triggered_count": c.triggered_count,
                    }
                    for c in self.conditions.values()
                ],
                "events": [e.__dict__ for e in self.events[-50:]],
            }
            self.STORAGE_FILE.write_text(json.dumps(data, indent=2, default=str))
        except Exception:
            pass

    def _load(self) -> None:
        try:
            if self.STORAGE_FILE.exists():
                data = json.loads(self.STORAGE_FILE.read_text())
                for c in data.get("conditions", []):
                    condition = TriggerCondition(
                        condition_id=c["condition_id"],
                        name=c["name"],
                        metric=c["metric"],
                        operator=c["operator"],
                        threshold=c["threshold"],
                        action=c["action"],
                        active=c.get("active", True),
                        triggered_count=c.get("triggered_count", 0),
                    )
                    self.conditions[condition.condition_id] = condition
        except Exception:
            pass


trigger_engine = TriggerEngine()
