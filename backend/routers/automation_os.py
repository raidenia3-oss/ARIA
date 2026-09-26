"""Automation OS router for AURA - REST endpoints for OS-level automation."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.automation.os_controller import (
    OSAction,
    OSActionType,
    OSController,
    RiskLevel,
    SafetyFilter,
    os_controller,
)

logger = logging.getLogger("AURAOSAutomation")

router = APIRouter(prefix="/api/automation", tags=["Automation OS"])


class ExecuteActionRequest(BaseModel):
    action_type: str
    coordinates: Optional[List[float]] = None
    text: Optional[str] = None
    key: Optional[str] = None
    key_combination: Optional[List[str]] = None
    scroll_amount: int = 0
    duration: float = 0.0
    delay: float = 0.0
    window_title: Optional[str] = None
    command: Optional[str] = None
    app_name: Optional[str] = None
    app_args: Optional[List[str]] = None
    require_confirmation: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ValidateCommandRequest(BaseModel):
    command: str


class ConfirmCommandRequest(BaseModel):
    command: str
    approved: bool


class SafetyFilterStatusResponse(BaseModel):
    dangerous_patterns_count: int
    dangerous_commands_count: int
    allowed_commands_count: int
    require_confirmation_for_count: int


def _build_action(req: ExecuteActionRequest) -> OSAction:
    try:
        atype = OSActionType(req.action_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid action_type: {req.action_type}")

    coords = None
    if req.coordinates and len(req.coordinates) >= 2:
        coords = (float(req.coordinates[0]), float(req.coordinates[1]))

    return OSAction(
        action_type=atype,
        coordinates=coords,
        text=req.text,
        key=req.key,
        key_combination=req.key_combination,
        scroll_amount=req.scroll_amount,
        duration=req.duration,
        delay=req.delay,
        window_title=req.window_title,
        command=req.command,
        app_name=req.app_name,
        app_args=req.app_args,
        require_confirmation=req.require_confirmation,
        metadata=req.metadata,
    )


@router.get("/os/status")
async def os_status() -> Dict[str, Any]:
    return os_controller.get_status()


@router.post("/os/execute")
async def execute_os_action(req: ExecuteActionRequest) -> Dict[str, Any]:
    action = _build_action(req)
    result = await os_controller.execute_action(action)
    status_code = 200 if result.success else 400
    if result.requires_confirmation and not result.success:
        status_code = 403
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=status_code, content=result.to_dict())


@router.post("/os/validate-command")
async def validate_command(req: ValidateCommandRequest) -> Dict[str, Any]:
    validation = os_controller._safety.validate_command(req.command)
    return validation.to_dict()


@router.post("/os/confirm-command")
async def confirm_command(req: ConfirmCommandRequest) -> Dict[str, Any]:
    os_controller.confirm_action(req.command, req.approved)
    return {"confirmed": req.approved, "command": req.command}


@router.get("/os/safety-status")
async def safety_status() -> Dict[str, Any]:
    return {
        "dangerous_patterns_count": len(SafetyFilter.DANGEROUS_PATTERNS),
        "dangerous_commands_count": len(SafetyFilter.DANGEROUS_COMMANDS),
        "allowed_commands_count": len(os_controller._safety._allowed_commands),
        "require_confirmation_for_count": len(os_controller._safety._require_confirmation_for),
    }


@router.get("/os/history")
async def get_history(limit: int = 50) -> Dict[str, Any]:
    return {"history": os_controller.get_history(limit)}


@router.delete("/os/history")
async def clear_history() -> Dict[str, Any]:
    os_controller.clear_history()
    return {"cleared": True}


@router.get("/os/tools")
async def list_os_tools() -> Dict[str, Any]:
    tools = []
    for atype in OSActionType:
        tools.append({
            "name": atype.value,
            "description": f"Execute {atype.value} action on the OS",
            "risk_level": "safe",
        })
    return {"count": len(tools), "tools": tools}


__all__ = ["router"]