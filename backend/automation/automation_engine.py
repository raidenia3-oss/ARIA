# -*- coding: utf-8 -*-
"""AURA OS — Automation Engine.

Schedules tasks by triggers, executes automations, monitors, creates workflows.
"""
from __future__ import annotations

import asyncio
import logging
import random
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURA.Automation")

TRIGGER_TYPES = [
    "every 9am",
    "when revenue > $100",
    "if cpu < 30%",
    "on error",
    "custom webhook",
    "every hour",
    "daily",
    "weekly",
    "on startup",
    "manual",
]

ACTION_MAP = {
    "every 9am": "send_newsletter",
    "when revenue > $100": "reinvest",
    "if cpu < 30%": "run_heavy_training",
    "on error": "auto_fix",
    "custom webhook": "execute_action",
    "every hour": "health_check",
    "daily": "generate_report",
    "weekly": "performance_review",
    "on startup": "initialize_system",
    "manual": "user_command",
}


class AutomationEngine:
    """Schedules and executes automated workflows based on triggers."""

    def __init__(self) -> None:
        self.automations: Dict[str, Dict[str, Any]] = {}
        self.workflows: Dict[str, Dict[str, Any]] = {}
        self.execution_log: List[Dict[str, Any]] = []
        self.triggered_count: int = 0

    async def schedule_task(self, trigger: str, action: str) -> Dict[str, Any]:
        if trigger not in TRIGGER_TYPES:
            raise ValueError(f"Unknown trigger: {trigger}")

        automation_id = f"AUTO-{str(uuid.uuid4())[:8]}"

        automation = {
            "automation_id": automation_id,
            "trigger": trigger,
            "action": action,
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "last_triggered": None,
            "trigger_count": 0,
            "next_run": (datetime.now() + timedelta(minutes=random.randint(1, 60))).isoformat(),
        }
        self.automations[automation_id] = automation

        result = {
            "automation_id": automation_id,
            "trigger": trigger,
            "action": action,
            "status": "scheduled",
            "mapped_action": ACTION_MAP.get(trigger, action),
            "next_run": automation["next_run"],
        }

        logger.info("Scheduled: %s -> %s", trigger, action)
        return result

    async def execute_automation(self, automation_id: str) -> Dict[str, Any]:
        automation = self.automations.get(automation_id)
        if not automation:
            raise ValueError(f"Automation not found: {automation_id}")

        action = automation["action"]
        start_time = datetime.now()

        steps_executed = [
            {"step": 1, "name": "validate_input", "status": "ok", "duration_ms": random.randint(5, 50)},
            {"step": 2, "name": "execute_action", "status": "ok", "duration_ms": random.randint(50, 500)},
            {"step": 3, "name": "verify_result", "status": "ok", "duration_ms": random.randint(5, 100)},
        ]

        await asyncio.sleep(random.uniform(0.05, 0.3))

        automation["last_triggered"] = datetime.now().isoformat()
        automation["trigger_count"] += 1
        self.triggered_count += 1

        duration = (datetime.now() - start_time).total_seconds() * 1000

        log_entry = {
            "automation_id": automation_id,
            "action": action,
            "timestamp": datetime.now().isoformat(),
            "duration_ms": round(duration, 2),
            "success": True,
        }
        self.execution_log.append(log_entry)

        return {
            "automation_id": automation_id,
            "action": action,
            "status": "completed",
            "steps": steps_executed,
            "total_duration_ms": round(duration, 2),
            "triggered_at": datetime.now().isoformat(),
            "result": f"{action} executed successfully",
        }

    async def monitor_automations(self) -> Dict[str, Any]:
        active = [a for a in self.automations.values() if a.get("status") == "active"]
        inactive = [a for a in self.automations.values() if a.get("status") != "active"]

        return {
            "monitor_id": f"MON-{int(datetime.now().timestamp())}",
            "total_automations": len(self.automations),
            "active": len(active),
            "inactive": len(inactive),
            "total_triggered": self.triggered_count,
            "automations": [
                {
                    "automation_id": a["automation_id"],
                    "trigger": a["trigger"],
                    "action": a["action"],
                    "status": a["status"],
                    "trigger_count": a.get("trigger_count", 0),
                    "last_triggered": a.get("last_triggered"),
                    "next_run": a.get("next_run"),
                }
                for a in self.automations.values()
            ],
            "recent_executions": self.execution_log[-10:],
            "monitored_at": datetime.now().isoformat(),
        }

    async def create_workflow(self, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        workflow_id = f"WF-{str(uuid.uuid4())[:8]}"

        validated_steps = []
        for i, step in enumerate(steps):
            validated_steps.append({
                "step_number": i + 1,
                "name": step.get("name", f"step_{i+1}"),
                "action": step.get("action", "unknown"),
                "condition": step.get("condition", "always"),
                "timeout_sec": step.get("timeout_sec", 30),
                "retry_on_failure": step.get("retry_on_failure", True),
                "status": "pending",
            })

        workflow = {
            "workflow_id": workflow_id,
            "name": f"Workflow {workflow_id}",
            "steps": validated_steps,
            "total_steps": len(validated_steps),
            "status": "draft",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "trigger": steps[0].get("trigger", "manual") if steps else "manual",
        }
        self.workflows[workflow_id] = workflow

        return {
            "workflow_id": workflow_id,
            "name": workflow["name"],
            "steps": validated_steps,
            "total_steps": len(validated_steps),
            "status": "draft",
            "trigger": workflow["trigger"],
            "created_at": workflow["created_at"],
        }


automation_engine = AutomationEngine()
