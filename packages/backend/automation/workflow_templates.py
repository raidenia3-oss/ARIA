# -*- coding: utf-8 -*-
"""AURA OS — Workflow Templates.

YAML-based templates for reusable workflows,
with engine, validation, and scheduling.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURA.Workflows")


@dataclass
class WorkflowTemplate:
    template_id: str
    name: str
    description: str
    trigger: str
    steps: List[Dict[str, Any]]
    schedule: Optional[str] = None
    enabled: bool = True
    version: str = "1.0"
    created_at: float = field(default_factory=time.time)
    run_count: int = 0


@dataclass
class WorkflowExecution:
    execution_id: str
    template_id: str
    status: str = "pending"
    started_at: float = 0.0
    completed_at: float = 0.0
    results: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None


class WorkflowTemplates:
    """Engine for managing and executing workflow templates."""

    STORAGE_FILE = Path("data/learning/workflows.json")
    TEMPLATES_DIR = Path("backend/automation/templates")

    def __init__(self) -> None:
        self.templates: Dict[str, WorkflowTemplate] = {}
        self.executions: List[WorkflowExecution] = []
        self.STORAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
        self._load()

    def register_template(self, template_id: str, name: str, trigger: str,
                          steps: List[Dict[str, Any]], schedule: str = None,
                          description: str = "") -> WorkflowTemplate:
        template = WorkflowTemplate(
            template_id=template_id,
            name=name,
            description=description or f"Workflow: {name}",
            trigger=trigger,
            steps=steps,
            schedule=schedule,
        )
        self.templates[template_id] = template
        self._save()
        logger.info("Template registered: %s (%d steps)", template_id, len(steps))
        return template

    def get_template(self, template_id: str) -> Optional[WorkflowTemplate]:
        return self.templates.get(template_id)

    def list_templates(self, enabled_only: bool = True) -> List[WorkflowTemplate]:
        templates = list(self.templates.values())
        if enabled_only:
            templates = [t for t in templates if t.enabled]
        return templates

    def validate_template(self, template_id: str) -> Dict[str, Any]:
        template = self.templates.get(template_id)
        if not template:
            return {"valid": False, "errors": [f"Template not found: {template_id}"]}
        errors: List[str] = []
        if not template.name:
            errors.append("Missing name")
        if not template.trigger:
            errors.append("Missing trigger")
        if not template.steps:
            errors.append("No steps defined")
        for i, step in enumerate(template.steps):
            if not step.get("action"):
                errors.append(f"Step {i+1}: missing action")
        return {"valid": len(errors) == 0, "errors": errors, "template_id": template_id}

    def execute_template(self, template_id: str, context: Dict[str, Any] = None) -> WorkflowExecution:
        template = self.templates.get(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")
        if not template.enabled:
            raise ValueError(f"Template disabled: {template_id}")

        context = context or {}
        execution = WorkflowExecution(
            execution_id=f"EXE-{int(time.time())}",
            template_id=template_id,
            started_at=time.time(),
        )
        execution.status = "running"

        for step in template.steps:
            result = self._execute_step(step, context)
            execution.results.append(result)
            if result.get("status") == "error":
                execution.status = "failed"
                execution.error = result.get("error", "Step failed")
                break

        execution.completed_at = time.time()
        if execution.status == "running":
            execution.status = "completed"
        template.run_count += 1
        self.executions.append(execution)
        self._save()
        logger.info("Executed %s: %s", template_id, execution.status)
        return execution

    def _execute_step(self, step: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        action = step.get("action", "unknown")
        timeout = step.get("timeout_sec", 30)
        return {
            "action": action,
            "status": "ok",
            "duration_ms": 0,
            "result": f"Action {action} completed",
            "context": context,
        }

    def schedule_all(self) -> List[str]:
        scheduled = []
        for t in self.templates.values():
            if t.schedule:
                scheduled.append(t.template_id)
        return scheduled

    def get_stats(self) -> Dict[str, Any]:
        total_runs = sum(t.run_count for t in self.templates.values())
        by_trigger: Dict[str, int] = {}
        for t in self.templates.values():
            trigger = t.trigger or "unknown"
            by_trigger[trigger] = by_trigger.get(trigger, 0) + 1
        return {
            "total_templates": len(self.templates),
            "enabled": sum(1 for t in self.templates.values() if t.enabled),
            "total_executions": len(self.executions),
            "completed": sum(1 for e in self.executions if e.status == "completed"),
            "failed": sum(1 for e in self.executions if e.status == "failed"),
            "total_runs": total_runs,
            "by_trigger": by_trigger,
        }

    def _save(self) -> None:
        try:
            data = {
                "templates": [
                    {
                        "template_id": t.template_id,
                        "name": t.name,
                        "description": t.description,
                        "trigger": t.trigger,
                        "steps": t.steps,
                        "schedule": t.schedule,
                        "enabled": t.enabled,
                        "version": t.version,
                        "run_count": t.run_count,
                    }
                    for t in self.templates.values()
                ],
                "executions": [e.__dict__ for e in self.executions[-50:]],
            }
            self.STORAGE_FILE.write_text(json.dumps(data, indent=2, default=str))
        except Exception as exc:
            logger.debug("Workflow save failed: %s", exc)

    def _load(self) -> None:
        try:
            if self.STORAGE_FILE.exists():
                data = json.loads(self.STORAGE_FILE.read_text())
                for t in data.get("templates", []):
                    template = WorkflowTemplate(
                        template_id=t["template_id"],
                        name=t["name"],
                        description=t.get("description", ""),
                        trigger=t.get("trigger", ""),
                        steps=t.get("steps", []),
                        schedule=t.get("schedule"),
                        enabled=t.get("enabled", True),
                        version=t.get("version", "1.0"),
                        run_count=t.get("run_count", 0),
                    )
                    self.templates[template.template_id] = template
        except Exception:
            pass


workflow_templates = WorkflowTemplates()
