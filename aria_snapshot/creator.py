"""Snapshot creator - creates git tags and state snapshots."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path

from .models import Snapshot


def _hash_file(path: Path) -> str:
    """SHA256 hash of a file, returns empty string if missing."""
    if not path.exists():
        return ""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _get_aria_version() -> str:
    """Get current ARIA version from aria_release models or git."""
    try:
        from aria_release.models import ReleaseChannel  # noqa: F401
    except Exception:
        pass

    # Try git describe
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--always"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().lstrip("v")
    except Exception:
        pass

    return "unknown"


def _get_installed_plugins(aria_home: Path) -> list[str]:
    """List installed plugins from plugins directory."""
    plugins_dir = aria_home / "plugins"
    if not plugins_dir.exists():
        return []
    return sorted([
        p.name for p in plugins_dir.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    ])


def _save_state_files(aria_home: Path, snapshot_path: Path) -> dict[str, str]:
    """Save state files to snapshot and return {filename: hash}."""
    state_files = [
        "brain_state.json",
        "orchestrator_state.json",
        "router_state.json",
        "improvement_state.json",
    ]
    saved = {}
    for fname in state_files:
        src = aria_home.parent / fname
        if src.exists():
            try:
                dest = snapshot_path / fname
                dest.write_bytes(src.read_bytes())
                saved[fname] = _hash_file(dest)
            except Exception:
                pass
    return saved


class SnapshotCreator:
    """Creates ARIA state snapshots with git tags."""

    def __init__(self, aria_home: Path) -> None:
        self.aria_home = Path(aria_home)
        self.snapshots_dir = self.aria_home / "snapshots"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

    def create(
        self,
        name: str,
        description: str = "",
        aria_version: str | None = None,
    ) -> Snapshot:
        """Create a snapshot with git tag and state files."""
        if aria_version is None:
            aria_version = _get_aria_version()

        snapshot_path = self.snapshots_dir / name
        snapshot_path.mkdir(parents=True, exist_ok=True)

        # Save state files
        state_files = _save_state_files(self.aria_home, snapshot_path)

        # Compute hashes
        db_path = self.aria_home / "aura.db"
        env_path = self.aria_home / ".env"

        snapshot = Snapshot(
            name=name,
            timestamp=datetime.now(),
            aria_version=aria_version,
            db_hash=_hash_file(db_path),
            env_hash=_hash_file(env_path),
            git_tag=f"snapshot-{name}",
            plugins=_get_installed_plugins(self.aria_home),
            description=description,
            state_files=state_files,
        )

        # Create git tag
        try:
            subprocess.run(
                ["git", "tag", "-a", snapshot.git_tag, "-m", f"Snapshot: {name}"],
                capture_output=True, timeout=10,
            )
        except Exception:
            pass

        # Save JSON
        json_path = self.snapshots_dir / f"{name}.json"
        json_path.write_text(json.dumps(snapshot.to_json(), indent=2))

        return snapshot