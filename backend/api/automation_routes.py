# -*- coding: utf-8 -*-
"""AURA OS — Automation API Routes."""
from __future__ import annotations

from fastapi import APIRouter, Body, Query
from typing import Any, Dict, List, Optional

router = APIRouter(prefix="/api/automation", tags=["automation"])


@router.get("/status")
async def automation_status() -> Dict[str, Any]:
    from backend.automation.workflow_templates import workflow_templates
    from backend.automation.trigger_engine import trigger_engine
    from backend.automation.recovery_automation import recovery_automation
    from backend.automation.browser_pool import browser_pool
    from backend.automation.rollercoin_scheduler import rollercoin_scheduler
    return {
        "workflows": workflow_templates.get_stats(),
        "triggers": trigger_engine.get_stats(),
        "recovery": recovery_automation.get_recovery_stats(),
        "browser_pool": browser_pool.get_pool_status(),
        "rollercoin": rollercoin_scheduler.get_mining_stats(),
    }


@router.post("/workflow/execute")
async def execute_workflow(template_id: str = Body(...),
                            context: Dict[str, Any] = None) -> Dict[str, Any]:
    from backend.automation.workflow_templates import workflow_templates
    try:
        execution = workflow_templates.execute_template(template_id, context=context)
        return execution.__dict__
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@router.post("/workflow/register")
async def register_workflow(name: str = Body(...), trigger: str = Body(...),
                             steps: List[Dict[str, Any]] = Body(...),
                             schedule: Optional[str] = None) -> Dict[str, Any]:
    from backend.automation.workflow_templates import workflow_templates
    template_id = f"WF-{name.lower().replace(' ', '-')}"
    template = workflow_templates.register_template(template_id, name, trigger, steps, schedule)
    return {"template_id": template_id, "template": template.__dict__}


@router.get("/workflow/templates")
async def list_templates(enabled_only: bool = Query(True)) -> Dict[str, Any]:
    from backend.automation.workflow_templates import workflow_templates
    templates = workflow_templates.list_templates(enabled_only=enabled_only)
    return {"templates": [t.__dict__ for t in templates]}


@router.post("/trigger/add")
async def add_trigger(condition_id: str = Body(...), name: str = Body(...),
                       metric: str = Body(...), operator: str = Body(...),
                       threshold: float = Body(...), action: str = Body(...)) -> Dict[str, Any]:
    from backend.automation.trigger_engine import trigger_engine
    condition = trigger_engine.add_condition(condition_id, name, metric, operator, threshold, action)
    return {"condition": condition.__dict__}


@router.post("/trigger/check")
async def check_triggers() -> Dict[str, Any]:
    from backend.automation.trigger_engine import trigger_engine
    events = trigger_engine.check_all()
    return {"events": [e.__dict__ for e in events]}


@router.get("/trigger/events")
async def trigger_events(limit: int = Query(20, ge=1, le=100)) -> Dict[str, Any]:
    from backend.automation.trigger_engine import trigger_engine
    return {"events": trigger_engine.get_triggered_events(limit)}


@router.post("/rollercoin/claim")
async def rollercoin_claim(session_id: str = None) -> Dict[str, Any]:
    from backend.automation.rollercoin_scheduler import rollercoin_scheduler
    return rollercoin_scheduler.claim(session_id=session_id)


@router.get("/rollercoin/stats")
async def rollercoin_stats() -> Dict[str, Any]:
    from backend.automation.rollercoin_scheduler import rollercoin_scheduler
    return rollercoin_scheduler.get_mining_stats()


@router.get("/rollercoin/schedule")
async def rollercoin_schedule() -> Dict[str, Any]:
    from backend.automation.rollercoin_scheduler import rollercoin_scheduler
    return {"schedule": rollercoin_scheduler.get_schedule()}


@router.post("/recovery/execute")
async def recovery_execute(action: str = Body(...),
                             policy_id: str = None,
                             context: Dict[str, Any] = None) -> Dict[str, Any]:
    from backend.automation.recovery_automation import recovery_automation
    return recovery_automation.execute_with_recovery(action, policy_id=policy_id, context=context)


@router.post("/recovery/rerun-failed")
async def recovery_rerun() -> Dict[str, Any]:
    from backend.automation.recovery_automation import recovery_automation
    return recovery_automation.rerun_failed()


@router.get("/browser/status")
async def browser_status() -> Dict[str, Any]:
    from backend.automation.browser_pool import browser_pool
    return browser_pool.get_pool_status()


@router.post("/browser/create")
async def browser_create(browser_type: str = "chromium") -> Dict[str, Any]:
    from backend.automation.browser_pool import browser_pool
    session = browser_pool.create_session(browser_type=browser_type)
    return {"session": session.__dict__}
