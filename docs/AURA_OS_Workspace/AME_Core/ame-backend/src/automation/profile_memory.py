"""
Profile memory loader for AME backend.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional


class ProfileMemory:
    def __init__(
        self,
        profile_path: str | Path = "ame-backend/src/automation/golden_profile.json",
        external_profile_path: Optional[str | Path] = None,
    ) -> None:
        self._path = Path(profile_path)
        self._external_path = Path(external_profile_path) if external_profile_path else None
        self._profile: Dict[str, Any] = {}
        self.reload()

    def reload(self) -> None:
        if self._path.exists():
            self._profile = json.loads(self._path.read_text(encoding="utf-8"))
        elif self._external_path and self._external_path.exists():
            self._profile = json.loads(self._external_path.read_text(encoding="utf-8"))
            self._path.write_text(
                json.dumps(self._profile, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        else:
            self._profile = {}

    def save(self) -> None:
        self._path.write_text(
            json.dumps(self._profile, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def get_active_profile_file(self) -> str:
        if self._external_path and self._external_path.exists():
            return str(self._external_path)
        return str(self._path)

    def load_external_profile(self, external_path: str | Path) -> Dict[str, Any]:
        self._external_path = Path(external_path)
        if not self._external_path.exists():
            raise FileNotFoundError(f"Perfil externo no encontrado: {self._external_path}")
        self._profile = json.loads(self._external_path.read_text(encoding="utf-8"))
        self.save()
        return self._profile

    def update_field(self, field: str, value: Any) -> None:
        self._profile[field] = value
        self.save()

    def branch_for_platform(self, platform: str) -> Dict[str, Any]:
        variant_key = f"{platform}_variant"
        if variant_key not in self._profile:
            base_profile = dict(self._profile)
            self._profile[variant_key] = base_profile
            self.save()
        return self._profile.get(variant_key, {})

    @property
    def profile(self) -> Dict[str, Any]:
        return self._profile

    def get_section(self, section: str) -> Dict[str, Any]:
        return self._profile.get(section, {})

    def get(self, key: str, default: Any = None) -> Any:
        return self._profile.get(key, default)
