"""AURA P2P Sync & Conflict Resolution Engine (BLOQUE 50)."""

from backend.sync.engine import (
    P2PSyncEngine,
    DocumentVersion,
    ConflictRecord,
    get_p2p_sync_engine,
    reset_p2p_sync_engine,
    router as p2p_sync_router,
)

__all__ = [
    "P2PSyncEngine",
    "DocumentVersion",
    "ConflictRecord",
    "get_p2p_sync_engine",
    "reset_p2p_sync_engine",
    "p2p_sync_router",
]

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
