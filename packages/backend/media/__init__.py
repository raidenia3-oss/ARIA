"""AURA Local Media Gallery Manager (Bloque 47)."""

from backend.media.manager import (
    AssetKind,
    MediaAsset,
    MediaManager,
    get_media_manager,
    reset_media_manager,
)
from backend.media.routes import router as media_router

__all__ = [
    "AssetKind",
    "MediaAsset",
    "MediaManager",
    "get_media_manager",
    "reset_media_manager",
    "media_router",
]

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
