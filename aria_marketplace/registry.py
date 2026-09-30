"""Plugin registry client with caching and signature verification."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests


@dataclass
class PluginMetadata:
    """Metadata for a single plugin version."""

    name: str
    version: str
    aria_min_version: str = "6.0.0"
    aria_max_version: str = "*"
    description: str = ""
    type: str = "skill"
    author: str = ""
    homepage: str = ""
    repository: str = ""
    documentation: str = ""
    license: str = "MIT"
    dependencies: list = field(default_factory=list)
    entry_point: dict = field(default_factory=dict)
    capabilities: list = field(default_factory=list)
    keywords: list = field(default_factory=list)
    anti_features: list = field(default_factory=list)
    checksum: str = ""
    download_url: str = ""
    downloads: int = 0
    rating: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PluginMetadata":
        return cls(
            name=data.get("name", ""),
            version=data.get("version", ""),
            aria_min_version=data.get("aria_min_version", "6.0.0"),
            aria_max_version=data.get("aria_max_version", "*"),
            description=data.get("description", ""),
            type=data.get("type", "skill"),
            author=data.get("author", ""),
            homepage=data.get("homepage", ""),
            repository=data.get("repository", ""),
            documentation=data.get("documentation", ""),
            license=data.get("license", "MIT"),
            dependencies=data.get("dependencies", []),
            entry_point=data.get("entry_point", {}),
            capabilities=data.get("capabilities", []),
            keywords=data.get("keywords", []),
            anti_features=data.get("anti_features", []),
            checksum=data.get("checksum", ""),
            download_url=data.get("download_url", ""),
            downloads=data.get("downloads", 0),
            rating=data.get("rating", 0.0),
        )


class PluginRegistry:
    """Client for the ARIA Plugin Registry (F-Droid 2.0 model)."""

    REGISTRY_URL = "https://raw.githubusercontent.com/aria-plugins/registry/main"
    CACHE_TTL = 3600  # 1 hour

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._index: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Index
    # ------------------------------------------------------------------
    def fetch_index(self) -> dict[str, Any]:
        """Fetch and cache the registry index."""
        cache_file = self.cache_dir / "index.json"

        # Check cache
        if cache_file.exists() and self._index is None:
            stat = cache_file.stat()
            age = time.time() - stat.st_mtime
            if age < self.CACHE_TTL:
                self._index = json.loads(cache_file.read_text())
                return self._index

        # Fetch from registry
        url = f"{self.REGISTRY_URL}/index.json"
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            # Return cached if available, even if stale
            if cache_file.exists():
                return json.loads(cache_file.read_text())
            raise

        # Verify signature if present
        sig_url = f"{self.REGISTRY_URL}/index.json.asc"
        try:
            sig_resp = requests.get(sig_url, timeout=10)
            if sig_resp.status_code == 200:
                from .verifier import verify_signature
                if not verify_signature(data, sig_resp.text.strip()):
                    raise RuntimeError("Registry signature verification failed")
        except RuntimeError:
            raise
        except Exception:
            pass  # Signature optional for now

        # Cache
        cache_file.write_text(json.dumps(data))
        self._index = data
        return data

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search plugins by name or keyword."""
        index = self.fetch_index()
        results = []
        query_lower = query.lower()
        for plugin in index.get("plugins", []):
            if query_lower in plugin.get("name", "").lower():
                results.append(plugin)
            elif any(query_lower in kw.lower() for kw in plugin.get("keywords", [])):
                results.append(plugin)
        return sorted(results, key=lambda x: x.get("downloads", 0), reverse=True)

    def list_all(self) -> list[dict[str, Any]]:
        """List all plugins in the registry."""
        index = self.fetch_index()
        return index.get("plugins", [])

    def get_plugin_info(self, name: str) -> dict[str, Any] | None:
        """Get plugin info from index."""
        index = self.fetch_index()
        for plugin in index.get("plugins", []):
            if plugin.get("name") == name:
                return plugin
        return None

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------
    def get_metadata(self, name: str, version: str = "latest") -> PluginMetadata:
        """Get full plugin metadata for a specific version."""
        url = f"{self.REGISTRY_URL}/entry/{name}.json"
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            raise RuntimeError(f"Failed to fetch metadata for {name}: {e}")

        if version == "latest":
            version = data.get("latest_version", data.get("versions", [{}])[0].get("version", "1.0.0"))

        versions = data.get("versions", {})
        if version not in versions:
            raise RuntimeError(f"Version {version} not found for {name}")

        plugin_data = versions[version]
        plugin_data.setdefault("name", name)
        plugin_data.setdefault("version", version)
        plugin_data.setdefault("download_url", f"https://github.com/aria-plugins/{name}/releases/download/v{version}/{name}-{version}.tar.gz")

        return PluginMetadata.from_dict(plugin_data)

    def get_versions(self, name: str) -> list[str]:
        """Get all available versions for a plugin."""
        url = f"{self.REGISTRY_URL}/entry/{name}.json"
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return list(data.get("versions", {}).keys())
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------
    def clear_cache(self) -> None:
        """Clear the registry cache."""
        for f in self.cache_dir.glob("*.json"):
            f.unlink()
        self._index = None

    def cache_path(self, name: str) -> Path:
        """Get cache file path for a plugin."""
        return self.cache_dir / f"{name}.json"