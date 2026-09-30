"""Release channel and metadata models."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ReleaseChannel(Enum):
    """ARIA release channels (Fedora-inspired)."""

    STABLE = "stable"
    TESTING = "testing"
    UNSTABLE = "unstable"

    @classmethod
    def from_string(cls, value: str) -> "ReleaseChannel":
        for ch in cls:
            if ch.value == value.lower():
                return ch
        raise ValueError(f"Unknown channel: {value}")


@dataclass
class Release:
    """A single ARIA release."""

    version: str
    channel: ReleaseChannel
    timestamp: datetime
    checksum: str
    download_url: str
    signature: str = ""
    changelog: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def release_path(self) -> str:
        return f"releases/{self.channel.value}/v{self.version}"

    @property
    def version_tuple(self) -> tuple[int, ...]:
        """Parse semver into tuple for comparison."""
        match = re.match(r"^(\d+)\.(\d+)\.(\d+)", self.version)
        if not match:
            return (0, 0, 0)
        return tuple(int(g) for g in match.groups())

    def __gt__(self, other: "Release") -> bool:
        return self.version_tuple > other.version_tuple

    def __ge__(self, other: "Release") -> bool:
        return self.version_tuple >= other.version_tuple

    def __lt__(self, other: "Release") -> bool:
        return self.version_tuple < other.version_tuple

    def __le__(self, other: "Release") -> bool:
        return self.version_tuple <= other.version_tuple

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "channel": self.channel.value,
            "timestamp": self.timestamp.isoformat(),
            "checksum": self.checksum,
            "download_url": self.download_url,
            "signature": self.signature,
            "changelog": self.changelog,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Release":
        return cls(
            version=data["version"],
            channel=ReleaseChannel.from_string(data["channel"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            checksum=data["checksum"],
            download_url=data["download_url"],
            signature=data.get("signature", ""),
            changelog=data.get("changelog", ""),
        )


@dataclass
class Metadata:
    """TUF-style signed metadata for a release."""

    root_key: str = ""
    targets: dict[str, str] = field(default_factory=dict)  # version -> sha256
    snapshot: dict[str, Any] = field(default_factory=dict)
    timestamp: dict[str, Any] = field(default_factory=dict)
    signatures: dict[str, str] = field(default_factory=dict)
    version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "root_key": self.root_key,
            "targets": self.targets,
            "snapshot": self.snapshot,
            "timestamp": self.timestamp,
            "signatures": self.signatures,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Metadata":
        return cls(
            version=data.get("version", 1),
            root_key=data.get("root_key", ""),
            targets=data.get("targets", {}),
            snapshot=data.get("snapshot", {}),
            timestamp=data.get("timestamp", {}),
            signatures=data.get("signatures", {}),
        )


# Backwards-compatible alias
Channel = ReleaseChannel