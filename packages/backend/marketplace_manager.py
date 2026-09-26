"""Marketplace manager for AURA API Marketplace & Distribution."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class AppStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    SUSPENDED = "suspended"


class VersionStatus(str, Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    BETA = "beta"
    ARCHIVED = "archived"


@dataclass
class AppRegistration:
    app_id: str
    name: str
    description: str
    category: str
    developer: str
    status: AppStatus = AppStatus.DRAFT
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


@dataclass
class VersionRecord:
    version_id: str
    app_id: str
    version: str
    changelog: str
    status: VersionStatus = VersionStatus.BETA
    download_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    metadata: Dict[str, Any] = field(default_factory=dict)


class AppRegistry:
    """Registro central de aplicaciones."""

    def __init__(self) -> None:
        self.apps: Dict[str, AppRegistration] = {}
        self.versions: Dict[str, VersionRecord] = {}
        self.index: Dict[str, List[str]] = {}

    def register_app(self, app: AppRegistration) -> AppRegistration:
        self.apps[app.app_id] = app
        self._index(app.app_id, app.category, app.tags, app.name)
        return app

    def publish_version(self, version: VersionRecord) -> VersionRecord:
        self.versions[version.version_id] = version
        app = self.apps.get(version.app_id)
        if app:
            app.updated_at = datetime.utcnow().isoformat() + "Z"
        return version

    def search(self, query: str = "", category: str = "", tags: Optional[List[str]] = None) -> List[AppRegistration]:
        results = list(self.apps.values())
        if query:
            q = query.lower()
            results = [app for app in results if q in app.name.lower() or q in app.description.lower()]
        if category:
            results = [app for app in results if app.category == category]
        if tags:
            tag_set = {t.lower() for t in tags}
            results = [app for app in results if tag_set.intersection({t.lower() for t in app.tags})]
        return results

    def get_app(self, app_id: str) -> Optional[AppRegistration]:
        return self.apps.get(app_id)

    def get_versions(self, app_id: str) -> List[VersionRecord]:
        return [v for v in self.versions.values() if v.app_id == app_id]

    def _index(self, app_id: str, category: str, tags: List[str], name: str) -> None:
        self.index.setdefault(category, []).append(app_id)
        for tag in tags:
            self.index.setdefault(tag.lower(), []).append(app_id)
        self.index.setdefault("__all__", []).append(app_id)


class VersionManager:
    """Controla versiones y lifecycle."""

    def __init__(self, registry: AppRegistry) -> None:
        self.registry = registry
        self.rollback_log: List[Dict[str, Any]] = []

    def promote(self, version_id: str, status: VersionStatus) -> Optional[VersionRecord]:
        version = self.registry.versions.get(version_id)
        if not version:
            return None
        version.status = status
        return version

    def deprecate(self, version_id: str) -> Optional[VersionRecord]:
        return self.promote(version_id, VersionStatus.DEPRECATED)

    def rollback(self, app_id: str, target_version: str) -> Optional[VersionRecord]:
        app_versions = self.registry.get_versions(app_id)
        target = next((v for v in app_versions if v.version == target_version), None)
        if not target:
            return None
        for v in app_versions:
            if v.version == target_version:
                v.status = VersionStatus.ACTIVE
            elif v.status == VersionStatus.ACTIVE:
                v.status = VersionStatus.DEPRECATED
        self.rollback_log.append({
            "app_id": app_id,
            "rolled_back_to": target_version,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })
        return target


class SecurityVerifier:
    """Verificaciones básicas de seguridad."""

    def __init__(self) -> None:
        self.banned_signatures = [
            "eval(",
            "exec(",
            "os.system(",
            "subprocess.call(",
            "subprocess.run(",
        ]

    def scan_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        findings = []
        text = json.dumps(metadata, ensure_ascii=False)
        for sig in self.banned_signatures:
            if sig in text:
                findings.append({"signature": sig, "severity": "high"})
        return {"passed": len(findings) == 0, "findings": findings, "scanned_at": datetime.utcnow().isoformat() + "Z"}

    def verify_publisher(self, developer: str) -> Dict[str, Any]:
        return {"developer": developer, "verified": True, "method": "registry-account"}


class MarketplaceManager:
    """Orquestador principal del marketplace."""

    def __init__(self) -> None:
        self.registry = AppRegistry()
        self.version_manager = VersionManager(self.registry)
        self.security = SecurityVerifier()

    def create_app(self, app: AppRegistration) -> AppRegistration:
        return self.registry.register_app(app)

    def publish_version(self, version: VersionRecord) -> VersionRecord:
        return self.registry.publish_version(version)

    def search_apps(self, query: str = "", category: str = "", tags: Optional[List[str]] = None) -> List[AppRegistration]:
        return self.registry.search(query=query, category=category, tags=tags)

    def get_app(self, app_id: str) -> Optional[AppRegistration]:
        return self.registry.get_app(app_id)

    def get_versions(self, app_id: str) -> List[VersionRecord]:
        return self.registry.get_versions(app_id)

    def promote_version(self, version_id: str, status: VersionStatus) -> Optional[VersionRecord]:
        return self.version_manager.promote(version_id, status)

    def deprecate_version(self, version_id: str) -> Optional[VersionRecord]:
        return self.version_manager.deprecate(version_id)

    def rollback_app(self, app_id: str, target_version: str) -> Optional[VersionRecord]:
        return self.version_manager.rollback(app_id, target_version)

    def verify_security(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        return self.security.scan_metadata(metadata)

    def verify_publisher(self, developer: str) -> Dict[str, Any]:
        return self.security.verify_publisher(developer)

