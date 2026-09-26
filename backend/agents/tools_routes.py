"""AURA Specialized Skills & Tool-Registry — REST endpoints (Bloque 56).

- GET    /api/agent/tools            — lista herramientas activas del nucleo.
- GET    /api/agent/tools/schemas    — esquemas function-calling (Jan/Ollama).
- GET    /api/agent/tools/audit      — auditoria del registro (eventos recientes).
- GET    /api/agent/tools/{name}     — detalle de una herramienta registrada.
- POST   /api/agent/tools/execute    — ejecuta una herramienta en el sandbox.
- POST   /api/agent/tools/load       — carga y registra un modulo de skill local.
- POST   /api/agent/tools/unregister — retira una herramienta del registro.
- POST   /api/agent/tools/reset     — reinicia y re-escanea el registro local.

100% local: no expone callables arbitrarios via REST; solo se cargan modulos
validados dentro del directorio soberano de skills del agente.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.agents.tools_registry import get_tools_registry, reset_tools_registry

logger = logging.getLogger("AURA.Agent.Tools.Routes")

router = APIRouter(prefix="/api/agent/tools", tags=["agent-tools"])


def _check_api_key(provided: Optional[str]) -> None:
    expected = os.getenv("AURA_API_KEY", "")
    if expected and provided != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


class ExecuteToolRequest(BaseModel):
    tool: str = Field(..., min_length=1, max_length=200)
    params: Dict[str, Any] = Field(default_factory=dict)
    timeout: float = Field(default=30.0, ge=0.1, le=300.0)


class LoadSkillRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=260, description="Ruta relativa del modulo (.py) dentro del dir de skills")


class UnregisterToolRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


@router.get("")
async def list_tools(
    category: Optional[str] = None,
    x_api_key: Optional[str] = None,
) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    registry = get_tools_registry()
    tools = registry.list_tools()
    if category:
        tools = [t for t in tools if t["category"] == category]
    return {
        "tools_total": len(tools),
        "tools": tools,
        "categories": sorted({t.get("category", "general") for t in tools}),
        "scripts_dir": str(registry.scripts_dir),
    }


@router.get("/status")
async def registry_status(x_api_key: Optional[str] = None) -> Dict[str, Any]:
    """Live snapshot of the dynamic tool registry (used by the HUD)."""
    _check_api_key(x_api_key)
    registry = get_tools_registry()
    return {
        "tools_total": len(registry._entries),
        "categories": sorted({e.category for e in registry._entries.values()}),
        "audit_events": len(registry._audit),
        "scripts_dir": str(registry.scripts_dir),
        "timestamp": registry._audit[-1]["ts"] if registry._audit else None,
    }


@router.get("/schemas")
async def list_schemas(
    category: Optional[str] = None,
    x_api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Esquemas de function-calling listos para inyectar al modelo local."""
    _check_api_key(x_api_key)
    registry = get_tools_registry()
    schemas = registry.function_schemas(category=category)
    return {"schemas_total": len(schemas), "schemas": schemas}


@router.get("/audit")
async def registry_audit(x_api_key: Optional[str] = None) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    return get_tools_registry().audit()


@router.get("/{name}")
async def get_tool(name: str, x_api_key: Optional[str] = None) -> Dict[str, Any]:
    """Devuelve el detalle de una herramienta registrada por su nombre completo."""
    _check_api_key(x_api_key)
    entry = get_tools_registry().get(name)
    if not entry:
        raise HTTPException(status_code=404, detail=f"unknown tool: {name}")
    return entry.to_dict()


@router.post("/execute")
async def execute_tool(payload: ExecuteToolRequest, x_api_key: Optional[str] = None) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    registry = get_tools_registry()
    entry = registry.get(payload.tool)
    if not entry:
        raise HTTPException(status_code=404, detail=f"unknown tool: {payload.tool}")
    result = await registry.execute_tool(payload.tool, dict(payload.params or {}), timeout=payload.timeout)
    # El sandbox siempre devuelve un dict estructurado; el REST traduce el exito
    # a 200 y el fallo controlado a 400 sin perder el detalle en el body.
    return JSONResponse(status_code=200 if result.get("success") else 400, content=result)


@router.post("/load")
async def load_skill_module(payload: LoadSkillRequest, x_api_key: Optional[str] = None) -> Dict[str, Any]:
    """Carga y registra las herramientas de un modulo de skill local validado."""
    _check_api_key(x_api_key)
    registry = get_tools_registry()
    try:
        registered = registry.load_from_path(payload.path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"loaded": True, "path": payload.path, "registered": registered}


@router.post("/unregister")
async def unregister_tool(payload: UnregisterToolRequest, x_api_key: Optional[str] = None) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    if not get_tools_registry().unregister(payload.name):
        raise HTTPException(status_code=404, detail=f"unknown tool: {payload.name}")
    return {"unregistered": True, "name": payload.name}


@router.delete("/{name}")
async def delete_tool(name: str, x_api_key: Optional[str] = None) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    if not get_tools_registry().unregister(name):
        raise HTTPException(status_code=404, detail=f"unknown tool: {name}")
    return {"unregistered": True, "name": name}


@router.post("/reset")
async def reset_registry(x_api_key: Optional[str] = None) -> Dict[str, Any]:
    """Reinicia y re-escanea el registro desde el directorio de skills local."""
    _check_api_key(x_api_key)
    reset_tools_registry()
    registry = get_tools_registry()
    registry.scan()
    return {"reset": True, "tools_total": len(registry.list_tools())}
