"""AURA Local Backup & Snapshot Engine (BLOQUE 49)."""

from backend.backup.snapshot import (
    LocalSnapshotEngine,
    SnapshotManifest,
    get_backup_engine,
    reset_backup_engine,
)
from backend.backup.routes import router as backup_router

__all__ = [
    "LocalSnapshotEngine",
    "SnapshotManifest",
    "get_backup_engine",
    "reset_backup_engine",
    "backup_router",
]

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
