"""Actions router for AURA - Tool registry and execution endpoints."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from backend.services.action_engine import ActionEngine

router = APIRouter()
logger = logging.getLogger("AURAActions")

try:
    from backend.orchestrator import orchestrator
except Exception:
    orchestrator = None

action_engine = ActionEngine(orchestrator=orchestrator)


@router.on_event("startup")
async def _on_startup() -> None:
    logger.info("Action Engine ready with %d tools", len(action_engine.list_tools()))


@router.get("/actions/tools")
async def list_tools() -> Dict[str, Any]:
    return {"count": len(action_engine.list_tools()), "tools": action_engine.list_tools()}


@router.post("/actions/execute")
async def execute_action(payload: Dict[str, Any]) -> Dict[str, Any]:
    tool_name = str(payload.get("tool", "")).strip()
    params = payload.get("params", {})
    if not tool_name:
        raise HTTPException(status_code=400, detail="tool is required")
    result = action_engine.execute(tool_name, params)
    status_code = 200 if result.success else 400
    if result.requires_confirmation and not result.success:
        status_code = 403
    return JSONResponse(status_code=status_code, content=result.to_dict())


@router.get("/actions/status")
async def actions_status() -> Dict[str, Any]:
    return action_engine.get_status()
