"""Permission engine for AURA agent tools.

Adopted from tama96 (MIT) and coucou (MIT, Mochi character excluded):
- Kill switch maestro (allow_all toggle)
- allow/deny por herramienta
- risk tiers con prompt obligatorio
- fail-closed: sin config, todo deny
- config en ~/.aura/permissions.json
"""

from .engine import (
    PermissionEngine,
    PermissionConfig,
    ToolPermission,
    get_permission_engine,
    reset_permission_engine,
)

__all__ = [
    "PermissionEngine",
    "PermissionConfig",
    "ToolPermission",
    "get_permission_engine",
    "reset_permission_engine",
]