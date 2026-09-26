"""Update Manager - Sistema de actualizaciones automáticas."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional


class UpdatePatch:
    def __init__(
        self,
        version: str,
        timestamp: str,
        changes: List[str],
        files_changed: List[str],
        size_bytes: int,
        checksum: str,
        required: bool = False,
    ) -> None:
        self.version = version
        self.timestamp = timestamp
        self.changes = changes
        self.files_changed = files_changed
        self.size_bytes = size_bytes
        self.checksum = checksum
        self.required = required

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "timestamp": self.timestamp,
            "changes": self.changes,
            "files_changed": self.files_changed,
            "size_bytes": self.size_bytes,
            "checksum": self.checksum,
            "required": self.required,
        }


class UpdateManager:
    def __init__(self, storage_path: str = "updates/") -> None:
        self.storage_path = storage_path
        self.current_version = "3.1.0"
        os.makedirs(storage_path, exist_ok=True)
        self.version_history: Dict[str, Dict[str, Any]] = {
            "3.1.0": {
                "date": "2026-08-16",
                "features": ["Initial release"],
                "breaking_changes": [],
                "checksum": "abc123",
            },
            "3.1.1": {
                "date": "2026-08-17",
                "features": ["Fix narrative clichés", "Better routing"],
                "breaking_changes": [],
                "checksum": "def456",
            },
        }

    def get_latest_version(self) -> str:
        versions = sorted(self.version_history.keys())
        return versions[-1] if versions else self.current_version

    def create_patch(
        self,
        new_version: str,
        changes: List[str],
        files_changed: List[str],
        checksum: str,
        required: bool = False,
    ) -> UpdatePatch:
        size = 0
        for file in files_changed:
            try:
                size += os.path.getsize(file)
            except Exception:
                size += 1024

        patch = UpdatePatch(
            version=new_version,
            timestamp=datetime.now().isoformat(),
            changes=changes,
            files_changed=files_changed,
            size_bytes=size,
            checksum=checksum,
            required=required,
        )
        self.version_history[new_version] = {
            "date": datetime.now().date().isoformat(),
            "features": changes,
            "breaking_changes": [],
            "checksum": checksum,
        }
        return patch

    def check_for_updates(self, client_version: str) -> Dict[str, Any]:
        latest = self.get_latest_version()
        if client_version == latest:
            return {
                "update_available": False,
                "message": "Ya tienes la última versión",
                "current_version": client_version,
                "latest_version": latest,
            }

        patches = self._get_patches_between(client_version, latest)
        return {
            "update_available": True,
            "current_version": client_version,
            "latest_version": latest,
            "patches": [p.to_dict() for p in patches],
            "total_size_bytes": sum(p.size_bytes for p in patches),
            "total_size_mb": round(sum(p.size_bytes for p in patches) / (1024 * 1024), 2),
            "changelog": self._generate_changelog(client_version, latest),
        }

    def _get_patches_between(self, from_version: str, to_version: str) -> List[UpdatePatch]:
        versions = sorted(self.version_history.keys())
        if from_version not in versions or to_version not in versions:
            return []
        start_idx = versions.index(from_version)
        end_idx = versions.index(to_version)
        patches = []
        for version in versions[start_idx + 1 : end_idx + 1]:
            info = self.version_history[version]
            patches.append(
                UpdatePatch(
                    version=version,
                    timestamp=info.get("date", ""),
                    changes=info.get("features", []),
                    files_changed=[],
                    size_bytes=0,
                    checksum=info.get("checksum", ""),
                    required=False,
                )
            )
        return patches

    def _generate_changelog(self, from_version: str, to_version: str) -> str:
        changelog = f"Cambios desde v{from_version} a v{to_version}:\n\n"
        versions = sorted(self.version_history.keys())
        start_idx = versions.index(from_version) if from_version in versions else 0
        end_idx = versions.index(to_version) if to_version in versions else len(versions)
        for version in versions[start_idx + 1 : end_idx + 1]:
            info = self.version_history[version]
            changelog += f"\n**v{version}** ({info['date']})\n"
            if info.get("breaking_changes"):
                changelog += "⚠️ Breaking Changes:\n"
                for change in info["breaking_changes"]:
                    changelog += f"  - {change}\n"
            changelog += "✨ Features/Fixes:\n"
            for feature in info.get("features", []):
                changelog += f"  - {feature}\n"
        return changelog

    def validate_patch(self, patch: UpdatePatch, file_path: str) -> bool:
        try:
            with open(file_path, "rb") as f:
                file_checksum = hashlib.sha256(f.read()).hexdigest()
            is_valid = file_checksum == patch.checksum
            if is_valid:
                print(f"✅ Patch validado: {patch.version}")
            else:
                print(f"❌ Checksum mismatch para {patch.version}")
            return is_valid
        except Exception as e:
            print(f"❌ Error validando patch: {e}")
            return False

    def rollback_version(self, version: str) -> bool:
        backup_path = os.path.join(self.storage_path, "backups", version)
        if os.path.exists(backup_path):
            print(f"✅ Rollback a v{version} completado")
            return True
        print(f"❌ No hay backup para v{version}")
        return False

    def get_version_info(self, version: str) -> Optional[Dict[str, Any]]:
        return self.version_history.get(version)


class VersionTracker:
    def __init__(self, local_version_file: str = "updates/local_version.json") -> None:
        self.version_file = local_version_file
        os.makedirs(os.path.dirname(self.version_file), exist_ok=True)
        self.current_version = self._load_version()

    def _load_version(self) -> str:
        try:
            with open(self.version_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("version", "3.1.0")
        except Exception:
            return "3.1.0"

    def save_version(self, version: str) -> None:
        data = {
            "version": version,
            "updated_at": datetime.now().isoformat(),
            "installed_patches": self._get_installed_patches(),
        }
        with open(self.version_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self.current_version = version
        print(f"✅ Versión actualizada a {version}")

    def _get_installed_patches(self) -> List[str]:
        try:
            with open(self.version_file, "r", encoding="utf-8") as f:
                return json.load(f).get("installed_patches", [])
        except Exception:
            return []

    def add_installed_patch(self, patch_version: str) -> None:
        patches = self._get_installed_patches()
        if patch_version not in patches:
            patches.append(patch_version)
        data = {
            "version": self.current_version,
            "updated_at": datetime.now().isoformat(),
            "installed_patches": patches,
        }
        with open(self.version_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
