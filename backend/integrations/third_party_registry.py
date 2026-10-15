# -*- coding: utf-8 -*-
"""AURA OS - Third-party integrations registry.

Tracks external repositories integrated into the project for
reference, updates, and cross-linking. Each entry documents
the source repo, local path, license, and why it is relevant.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

REPO_ROOT = Path(__file__).resolve().parents[2]
INTEGRATIONS_DIR = REPO_ROOT / "integrations"


@dataclass
class Integration:
    name: str
    repo: str
    local_path: str
    license: str
    purpose: str
    tags: list[str] = field(default_factory=list)

    @property
    def full_path(self) -> Path:
        return INTEGRATIONS_DIR / self.local_path

    @property
    def available(self) -> bool:
        return self.full_path.exists()

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "repo": self.repo,
            "local_path": str(self.local_path),
            "license": self.license,
            "purpose": self.purpose,
            "tags": self.tags,
            "available": self.available,
            "full_path": str(self.full_path),
        }


INTEGRATIONS: Dict[str, Integration] = {
    "insomnia": Integration(
        name="Insomnia",
        repo="krishhgg/Insomnia",
        local_path="Insomnia",
        license="MIT",
        purpose=(
            "macOS menu-bar app that keeps a MacBook awake with the lid closed "
            "for timed agent sessions. Provides sleep-prevention, app freezing, "
            "audio mute control, Low Power Mode management, and iPhone hotspot "
            "handoff via caffeinate/pmset. Relevant to ARIA autonomous background "
            "operation and the aria_mobile_communication_channel decision."
        ),
        tags=["macos", "sleep-management", "power-management", "autonomous-operation"],
    ),
    "apple_watch_connector": Integration(
        name="Apple Watch Connector",
        repo="LordixDemon/apple_watch_connector",
        local_path="apple_watch_connector",
        license="MIT",
        purpose=(
            "Native Bluetooth/IDS bridge between macOS/Linux/Windows and Apple "
            "Watch. Implements pairing, activation, face management, Health sync, "
            "and notifications via Rust + Java protocol layers. Relevant to the "
            "aria_mobile_communication_channel decision and ARIA's mobile "
            "communication channel via Bluetooth."
        ),
        tags=["apple-watch", "bluetooth", "ids", "pairing", "mobile-channel"],
    ),
}


def get_integration(name: str) -> Integration | None:
    return INTEGRATIONS.get(name)


def list_integrations() -> list[Dict]:
    return [v.to_dict() for v in INTEGRATIONS.values()]


integrations_registry = INTEGRATIONS
