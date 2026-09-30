"""ARIA Plugin Marketplace - F-Droid 2.0 model.

Provides:
- Registry client (fetch + cache + signature verification)
- Dependency resolver (BFS with semver)
- Plugin installer (download + checksum + register)
- CLI: aria plugin search|install|list|remove
"""

from .registry import PluginRegistry, PluginMetadata
from .resolver import DependencyResolver, DependencyError
from .installer import PluginInstaller
from .verifier import verify_checksum, verify_signature

__all__ = [
    "PluginRegistry",
    "PluginMetadata",
    "DependencyResolver",
    "DependencyError",
    "PluginInstaller",
    "verify_checksum",
    "verify_signature",
]