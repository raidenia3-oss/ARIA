# -*- coding: utf-8 -*-
"""AURA OS — Google Play Store Config.

Metadata para subir APK a Google Play Store.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger("AURA.PlayStore")


class PlayStoreConfig:
    """Configuracion para Google Play Store."""

    def __init__(self) -> None:
        self.package_name = "com.raiden.aura"
        self.app_name = "AURA OS"
        self.version_code = 2
        self.version_name = "2.0.0"
        self.min_sdk = 28
        self.target_sdk = 34
        self.category = "Productivity"
        self.content_rating = "Everyone"

    def get_metadata(self) -> Dict[str, Any]:
        """Retorna metadata completa para Play Store."""
        return {
            "package_name": self.package_name,
            "app_name": self.app_name,
            "short_description": "Advanced personal AI assistant with agents, marketplace, and netrunner",
            "full_description": (
                "AURA OS is an advanced personal AI assistant that runs locally on your device. "
                "Features include:\n\n"
                "- 10 AI agents (code review, data science, language tutor, fitness coach, etc.)\n"
                "- Multi-device sync via Firebase Cloud\n"
                "- Marketplace for buying/selling AI content\n"
                "- Netrunner security missions game\n"
                "- Voice commands and biometric unlock\n"
                "- Works offline with automatic cloud sync\n\n"
                "100% local operation. No cloud dependencies for core features."
            ),
            "category": self.category,
            "content_rating": self.content_rating,
            "version_code": self.version_code,
            "version_name": self.version_name,
            "min_sdk": self.min_sdk,
            "target_sdk": self.target_sdk,
            "privacy_policy_url": "https://aura-prod.railway.app/privacy",
            "support_url": "https://aura-prod.railway.app/support",
            "developer": "Raiden",
            "contact_email": "dev@aura-os.local",
            "screenshots": [
                {"image": "screenshot_1.png", "type": "phone", "description": "Chat interface"},
                {"image": "screenshot_2.png", "type": "phone", "description": "Agents overview"},
                {"image": "screenshot_3.png", "type": "phone", "description": "Netrunner game"},
                {"image": "screenshot_4.png", "type": "phone", "description": "Marketplace"},
                {"image": "screenshot_5.png", "type": "phone", "description": "Device sync"},
            ],
            "icon": "icon_512.png",
            "feature_graphic": "feature_graphic.png",
            "video": "trailer.mp4",
            "tags": ["AI", "assistant", "productivity", "chatbot", "local-AI"],
            "release_notes": "v2.0: UI refinements, Netrunner integration, biometric unlock, voice commands, offline-first",
        }

    def get_listing_resources(self) -> Dict[str, str]:
        """Retorna paths de recursos necesarios."""
        return {
            "icon_512.png": "8:8:PNG",
            "feature_graphic.png": "1024:500:PNG",
            "screenshot_1.png": "1080:1920:PNG",
            "screenshot_2.png": "1080:1920:PNG",
            "screenshot_3.png": "1080:1920:PNG",
            "screenshot_4.png": "1080:1920:PNG",
            "screenshot_5.png": "1080:1920:PNG",
            "trailer.mp4": "1080:1920:MP4",
            "privacy_policy.html": "text/html",
        }

    def validate(self) -> Dict[str, Any]:
        """Valida la configuracion."""
        metadata = self.get_metadata()
        errors = []
        if not metadata["app_name"]:
            errors.append("app_name required")
        if not metadata["package_name"]:
            errors.append("package_name required")
        if metadata["min_sdk"] < 21:
            errors.append("min_sdk must be >= 21")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": ["Consider adding video trailer"],
            "package": self.package_name,
            "version": self.version_name,
        }

    def generate_store_listing(self) -> str:
        """Genera listing JSON para Play Console."""
        return json.dumps(self.get_metadata(), indent=2, ensure_ascii=False)


play_store_config = PlayStoreConfig()
