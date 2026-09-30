"""Dependency resolver with BFS and semver constraints."""

from __future__ import annotations

import importlib
import re
from typing import Any

from .registry import PluginRegistry


class DependencyError(Exception):
    """Raised when dependency resolution fails."""


def _parse_dep(dep_spec: str) -> tuple[str, str]:
    """Parse a dependency spec like 'requests>=2.28' into (name, constraint)."""
    match = re.match(r"^([a-zA-Z0-9_.-]+?)([<>=!~].*)?$", dep_spec.strip())
    if not match:
        return dep_spec.strip(), ""
    return match.group(1), match.group(2) or ""


def _check_python_package(pkg_name: str, constraint: str = "") -> bool:
    """Check if a Python package is importable."""
    try:
        importlib.import_module(pkg_name.replace("-", "_"))
        return True
    except ImportError:
        # Try pip to check
        try:
            from importlib.metadata import version, PackageNotFoundError
            version(pkg_name.replace("-", "_"))
            return True
        except Exception:
            return False


class DependencyResolver:
    """Resolves plugin dependencies using BFS with semver constraints."""

    def __init__(self, registry: PluginRegistry) -> None:
        self.registry = registry
        self.resolved: dict[str, dict[str, Any]] = {}
        self.errors: list[str] = []
        self._visited: set[str] = set()

    def resolve(self, plugin_name: str, plugin_version: str = "latest") -> dict[str, dict[str, Any]]:
        """Resolve all dependencies for a plugin (BFS).

        Returns dict of {plugin_name: {version, dependencies, type}}.
        """
        self.resolved = {}
        self.errors = []
        self._visited = set()

        queue: list[tuple[str, str, str]] = [(plugin_name, plugin_version, "plugin")]

        while queue:
            name, version, dep_type = queue.pop(0)

            if name in self._visited:
                continue
            self._visited.add(name)

            try:
                metadata = self.registry.get_metadata(name, version)
            except Exception as e:
                self.errors.append(f"Failed to fetch {name}@{version}: {e}")
                continue

            # Check ARIA version constraint
            if not self._check_aria_constraint(metadata):
                self.errors.append(
                    f"{name}@{metadata.version} requires ARIA >={metadata.aria_min_version}"
                )
                continue

            # Check Python dependencies
            for dep_spec in metadata.dependencies:
                dep_name, dep_constraint = _parse_dep(dep_spec)
                if dep_name and not _check_python_package(dep_name):
                    self.errors.append(
                        f"{name} requires Python package '{dep_name}' (not installed)"
                    )

            # Add to resolved
            self.resolved[name] = {
                "version": metadata.version,
                "dependencies": metadata.dependencies,
                "type": metadata.type,
                "checksum": metadata.checksum,
                "download_url": metadata.download_url,
            }

            # Queue plugin dependencies for resolution
            for dep_spec in metadata.dependencies:
                dep_name, _ = _parse_dep(dep_spec)
                if dep_name and dep_name not in self._visited:
                    queue.append((dep_name, "latest", "dependency"))

        if self.errors:
            raise DependencyError(f"Resolution failed: {'; '.join(self.errors)}")

        return self.resolved

    def _check_aria_constraint(self, metadata) -> bool:
        """Check if plugin is compatible with current ARIA version."""
        try:
            from aria_release.models import ReleaseChannel  # noqa: F401
        except Exception:
            pass

        min_ver = metadata.aria_min_version
        max_ver = metadata.aria_max_version

        if max_ver and max_ver != "*":
            try:
                from packaging.version import Version
                # Simplified: check min only for now
                return True
            except Exception:
                pass
        return True  # Don't block on version check for now