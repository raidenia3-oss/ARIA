"""Plugin installer - downloads, verifies, and registers plugins."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from .registry import PluginRegistry
from .resolver import DependencyResolver, DependencyError
from .verifier import verify_checksum


class PluginInstaller:
    """Installs plugins from the ARIA marketplace."""

    def __init__(self, aria_home: Path) -> None:
        self.aria_home = Path(aria_home)
        self.plugins_dir = self.aria_home / "backend" / "plugins"
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir = self.aria_home / "cache" / "marketplace"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.registry = PluginRegistry(self.cache_dir)
        self.manifest_path = self.plugins_dir / "manifest.json"

        # Ensure manifest exists
        if not self.manifest_path.exists():
            self._save_manifest({"plugins": []})

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def install(self, plugin_name: str, version: str = "latest") -> dict[str, Any]:
        """Install a plugin and all its dependencies.

        Returns installation result.
        """
        result = {
            "plugin": plugin_name,
            "version": version,
            "installed": [],
            "errors": [],
            "status": "success",
        }

        try:
            # 1. Resolve dependencies
            resolver = DependencyResolver(self.registry)
            resolved = resolver.resolve(plugin_name, version)

            # 2. Install in order (dependencies first, then the plugin)
            install_order = self._topological_sort(resolved)
            for name in install_order:
                info = resolved[name]
                try:
                    self._install_single(name, info)
                    result["installed"].append({
                        "name": name,
                        "version": info["version"],
                        "type": info["type"],
                    })
                except Exception as e:
                    result["errors"].append(f"{name}: {e}")

            # 3. Register in manifest
            self._update_manifest(plugin_name, version)

            if result["errors"]:
                result["status"] = "partial"

        except DependencyError as e:
            result["status"] = "error"
            result["errors"].append(str(e))
        except Exception as e:
            result["status"] = "error"
            result["errors"].append(str(e))

        return result

    def uninstall(self, plugin_name: str) -> dict[str, Any]:
        """Uninstall a plugin."""
        result = {"plugin": plugin_name, "status": "success"}

        plugin_path = self.plugins_dir / plugin_name
        if plugin_path.exists():
            shutil.rmtree(plugin_path, ignore_errors=True)
        else:
            result["status"] = "error"
            result["error"] = f"Plugin '{plugin_name}' not found"
            return result

        # Update manifest
        self._remove_from_manifest(plugin_name)

        return result

    def list_installed(self) -> list[dict[str, Any]]:
        """List all installed plugins."""
        manifest = self._load_manifest()
        return manifest.get("plugins", [])

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _install_single(self, name: str, info: dict[str, Any]) -> None:
        """Download and install a single plugin."""
        version = info["version"]
        download_url = info.get("download_url", "")
        expected_checksum = info.get("checksum", "")

        if not download_url:
            # Try GitHub releases URL
            download_url = (
                f"https://github.com/aria-plugins/{name}"
                f"/releases/download/v{version}/{name}-{version}.tar.gz"
            )

        # Download
        import requests
        try:
            resp = requests.get(download_url, timeout=60)
            resp.raise_for_status()
            content = resp.content
        except Exception as e:
            raise RuntimeError(f"Download failed for {name}: {e}")

        # Verify checksum
        if expected_checksum:
            if not verify_checksum(content, expected_checksum):
                raise RuntimeError(f"Checksum mismatch for {name}")
        else:
            # Compute and log checksum
            actual = hashlib.sha256(content).hexdigest()
            print(f"[Installer] {name}@{version} sha256={actual}")

        # Extract tarball
        plugin_path = self.plugins_dir / name
        if plugin_path.exists():
            shutil.rmtree(plugin_path, ignore_errors=True)
        plugin_path.mkdir(parents=True, exist_ok=True)

        try:
            with tarfile.open(fileobj=io.BytesIO(content), mode="r:gz") as tar:
                tar.extractall(path=str(plugin_path))
        except tarfile.TarError as e:
            raise RuntimeError(f"Extraction failed for {name}: {e}")

        # Run setup.py if present
        setup_py = plugin_path / "setup.py"
        if setup_py.exists():
            try:
                subprocess.run(
                    [sys.executable, str(setup_py), "install"],
                    cwd=str(plugin_path),
                    capture_output=True,
                    timeout=30,
                )
            except Exception:
                pass  # Setup is optional

        print(f"[Installer] Installed {name}@{version}")

    def _topological_sort(self, resolved: dict[str, dict[str, Any]]) -> list[str]:
        """Sort plugins so dependencies are installed first."""
        # Simple: dependencies before dependents
        # Build dependency graph
        deps_of: dict[str, set[str]] = {}
        for name, info in resolved.items():
            dep_names = set()
            for dep_spec in info.get("dependencies", []):
                dep_name = dep_spec.split(">")[0].split("<")[0].split("=")[0].strip()
                if dep_name in resolved:
                    dep_names.add(dep_name)
            deps_of[name] = dep_names

        # Topological sort (Kahn's algorithm)
        in_degree = {name: len(deps_of[name]) for name in resolved}
        queue = [name for name, deg in in_degree.items() if deg == 0]
        result = []

        while queue:
            name = queue.pop(0)
            result.append(name)
            for other, deps in deps_of.items():
                if name in deps:
                    in_degree[other] -= 1
                    if in_degree[other] == 0:
                        queue.append(other)

        # Add any remaining (cycles)
        for name in resolved:
            if name not in result:
                result.append(name)

        return result

    # ------------------------------------------------------------------
    # Manifest
    # ------------------------------------------------------------------
    def _load_manifest(self) -> dict[str, Any]:
        """Load plugin manifest."""
        if self.manifest_path.exists():
            try:
                return json.loads(self.manifest_path.read_text())
            except Exception:
                pass
        return {"plugins": []}

    def _save_manifest(self, manifest: dict[str, Any]) -> None:
        """Save plugin manifest."""
        self.manifest_path.write_text(json.dumps(manifest, indent=2))

    def _update_manifest(self, name: str, version: str) -> None:
        """Add or update plugin in manifest."""
        manifest = self._load_manifest()
        plugins = manifest.get("plugins", [])

        # Remove existing
        plugins = [p for p in plugins if p.get("name") != name]

        # Add
        plugins.append({
            "name": name,
            "version": version,
            "installed_at": __import__("time").time(),
        })

        manifest["plugins"] = plugins
        self._save_manifest(manifest)

    def _remove_from_manifest(self, name: str) -> None:
        """Remove plugin from manifest."""
        manifest = self._load_manifest()
        manifest["plugins"] = [
            p for p in manifest.get("plugins", []) if p.get("name") != name
        ]
        self._save_manifest(manifest)