"""Tenant manager for AURA Enterprise Multi-Tenancy & Workspace Isolation."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class TenantStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


@dataclass
class Tenant:
    tenant_id: str
    name: str
    domain: str
    status: TenantStatus = TenantStatus.ACTIVE
    plan: str = "standard"
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


@dataclass
class Workspace:
    workspace_id: str
    tenant_id: str
    name: str
    description: str
    settings: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


@dataclass
class QuotaUsage:
    tenant_id: str
    workspace_id: str
    api_calls: int = 0
    storage_mb: float = 0.0
    ai_tokens: int = 0
    active_users: int = 0
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class QuotaManager:
    """Control de cuotas por tenant/workspace."""

    def __init__(self) -> None:
        self.usages: Dict[str, QuotaUsage] = {}

    def usage(self, tenant_id: str, workspace_id: Optional[str] = None) -> QuotaUsage:
        key = f"{tenant_id}:{workspace_id or '__global__'}"
        if key not in self.usages:
            self.usages[key] = QuotaUsage(tenant_id=tenant_id, workspace_id=workspace_id or "__global__")
        return self.usages[key]

    def increment(self, tenant_id: str, workspace_id: Optional[str], api_calls: int = 0, storage_mb: float = 0.0, ai_tokens: int = 0, active_users: int = 0) -> QuotaUsage:
        usage = self.usage(tenant_id, workspace_id)
        usage.api_calls += api_calls
        usage.storage_mb += storage_mb
        usage.ai_tokens += ai_tokens
        usage.active_users = max(usage.active_users, active_users)
        usage.updated_at = datetime.utcnow().isoformat() + "Z"
        return usage

    def snapshot(self, tenant_id: str, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        usage = self.usage(tenant_id, workspace_id)
        return usage.__dict__


class TenantContext:
    """Contexto de tenant para requests."""

    def __init__(self, tenant: Tenant, workspace: Optional[Workspace] = None) -> None:
        self.tenant = tenant
        self.workspace = workspace
        self.quota = QuotaManager()

    def current(self) -> Tenant:
        return self.tenant

    def current_workspace(self) -> Optional[Workspace]:
        return self.workspace


class TenantManager:
    """Gestor central de multi-tenancy."""

    def __init__(self) -> None:
        self.tenants: Dict[str, Tenant] = {}
        self.workspaces: Dict[str, Workspace] = {}
        self.quota = QuotaManager()
        self.contexts: Dict[str, TenantContext] = {}

    def create_tenant(self, tenant: Tenant) -> Tenant:
        self.tenants[tenant.tenant_id] = tenant
        self.contexts[tenant.tenant_id] = TenantContext(tenant=tenant)
        return tenant

    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        return self.tenants.get(tenant_id)

    def create_workspace(self, workspace: Workspace) -> Workspace:
        if workspace.tenant_id not in self.tenants:
            raise ValueError("Tenant not found")
        self.workspaces[workspace.workspace_id] = workspace
        return workspace

    def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        return self.workspaces.get(workspace_id)

    def list_workspaces(self, tenant_id: str) -> List[Workspace]:
        return [w for w in self.workspaces.values() if w.tenant_id == tenant_id]

    def context_for(self, tenant_id: str, workspace_id: Optional[str] = None) -> Optional[TenantContext]:
        ctx = self.contexts.get(tenant_id)
        if not ctx:
            return None
        if workspace_id:
            ws = self.workspaces.get(workspace_id)
            if ws and ws.tenant_id == tenant_id:
                ctx.workspace = ws
            else:
                ctx.workspace = None
        return ctx
