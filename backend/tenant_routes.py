"""Tenant routes for AURA Enterprise Multi-Tenancy & Disaster Recovery."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.tenant_manager import TenantManager, TenantStatus, Workspace, Tenant
from backend.disaster_recovery import DisasterRecoveryManager

router = APIRouter(prefix="/api/tenants", tags=["tenants"])
tenant_manager = TenantManager()
dr_manager = DisasterRecoveryManager()


@router.post("/")
async def create_tenant(payload: Dict[str, Any]) -> Dict[str, Any]:
    required = ["tenant_id", "name", "domain"]
    missing = [field for field in required if not payload.get(field)]
    if missing:
        return JSONResponse(status_code=400, content={"detail": f"Missing fields: {', '.join(missing)}"})

    tenant = tenant_manager.create_tenant(Tenant(
        tenant_id=str(payload["tenant_id"]),
        name=str(payload["name"]),
        domain=str(payload["domain"]),
        status=TenantStatus(str(payload.get("status", "active"))),
        plan=str(payload.get("plan", "standard")),
        metadata=payload.get("metadata", {}),
    ))
    return tenant.__dict__


@router.get("/")
async def list_tenants() -> Dict[str, Any]:
    tenants = list(tenant_manager.tenants.values())
    return {"count": len(tenants), "tenants": [t.__dict__ for t in tenants]}


@router.get("/{tenant_id}")
async def get_tenant(tenant_id: str) -> Dict[str, Any]:
    tenant = tenant_manager.get_tenant(tenant_id)
    if not tenant:
        return JSONResponse(status_code=404, content={"detail": "Tenant not found"})
    return tenant.__dict__


@router.post("/{tenant_id}/workspaces")
async def create_workspace(tenant_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not tenant_manager.get_tenant(tenant_id):
        return JSONResponse(status_code=404, content={"detail": "Tenant not found"})
    required = ["workspace_id", "name"]
    missing = [field for field in required if not payload.get(field)]
    if missing:
        return JSONResponse(status_code=400, content={"detail": f"Missing fields: {', '.join(missing)}"})

    workspace = tenant_manager.create_workspace(Workspace(
        workspace_id=str(payload["workspace_id"]),
        tenant_id=tenant_id,
        name=str(payload["name"]),
        description=str(payload.get("description", "")),
        settings=payload.get("settings", {}),
    ))
    return workspace.__dict__


@router.get("/{tenant_id}/workspaces")
async def list_workspaces(tenant_id: str) -> Dict[str, Any]:
    if not tenant_manager.get_tenant(tenant_id):
        return JSONResponse(status_code=404, content={"detail": "Tenant not found"})
    workspaces = tenant_manager.list_workspaces(tenant_id)
    return {"tenant_id": tenant_id, "count": len(workspaces), "workspaces": [w.__dict__ for w in workspaces]}
