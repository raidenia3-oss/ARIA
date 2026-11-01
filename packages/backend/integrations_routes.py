"""API routes for third-party repository integrations."""
from __future__ import annotations

from fastapi import APIRouter
from backend.integrations import integrations_registry

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


@router.get("/")
def list_all_integrations():
    """List all third-party integrations with availability status."""
    return integrations_registry


@router.get("/{name}")
def get_integration(name: str):
    """Get details of a specific integration by name."""
    integration = integrations_registry.get(name)
    if not integration:
        return {"error": f"integration '{name}' not found"}
    return integration.to_dict()
