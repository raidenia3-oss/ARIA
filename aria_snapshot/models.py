"""Snapshot data model."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class Snapshot:
    """A complete ARIA state snapshot for rollback."""

    name: str
    timestamp: datetime
    aria_version: str
    db_hash: str
    env_hash: str
    git_tag: str
    plugins: list = field(default_factory=list)
    description: str = ""
    state_files: dict[str, str] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "timestamp": self.timestamp.isoformat(),
            "aria_version": self.aria_version,
            "db_hash": self.db_hash,
            "env_hash": self.env_hash,
            "git_tag": self.git_tag,
            "plugins": self.plugins,
            "description": self.description,
            "state_files": self.state_files,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Snapshot":
        return cls(
            name=data["name"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            aria_version=data["aria_version"],
            db_hash=data["db_hash"],
            env_hash=data["env_hash"],
            git_tag=data["git_tag"],
            plugins=data.get("plugins", []),
            description=data.get("description", ""),
            state_files=data.get("state_files", {}),
        )

    @classmethod
    def from_file(cls, path: Path) -> "Snapshot":
        return cls.from_json(json.loads(path.read_text()))


class SnapshotManager:
    """Manages snapshot lifecycle: create, list, delete, restore."""

    def __init__(self, aria_home: Path) -> None:
        self.aria_home = Path(aria_home)
        self.snapshots_dir = self.aria_home / "snapshots"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

    def list_snapshots(self) -> list[Snapshot]:
        """List all snapshots, newest first."""
        snapshots = []
        for f in self.snapshots_dir.glob("*.json"):
            try:
                snapshots.append(Snapshot.from_file(f))
            except Exception:
                continue
        return sorted(snapshots, key=lambda s: s.timestamp, reverse=True)

    def get_snapshot(self, name: str) -> Snapshot | None:
        """Get snapshot by name."""
        for snap in self.list_snapshots():
            if snap.name == name:
                return snap
        return None

    def delete_snapshot(self, name: str) -> bool:
        """Delete a snapshot (JSON + git tag)."""
        snap = self.get_snapshot(name)
        if snap is None:
            return False

        json_path = self.snapshots_dir / f"{name}.json"
        if json_path.exists():
            json_path.unlink()

        # Remove git tag
        import subprocess
        try:
            subprocess.run(
                ["git", "tag", "-d", snap.git_tag],
                capture_output=True, timeout=10,
            )
        except Exception:
            pass

        return True

    def cleanup_old_snapshots(self, keep: int = 5) -> int:
        """Keep only the latest N snapshots. Returns count deleted."""
        snapshots = self.list_snapshots()
        deleted = 0
        for snap in snapshots[keep:]:
            if self.delete_snapshot(snap.name):
                deleted += 1
        return deleted