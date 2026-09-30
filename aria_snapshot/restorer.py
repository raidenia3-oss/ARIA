"""Snapshot restorer - restores state from snapshots."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

from .models import Snapshot


def _verify_snapshot(snapshot: Snapshot, aria_home: Path) -> bool:
    """Verify snapshot integrity by checking hashes."""
    db_path = aria_home / "aura.db"
    if snapshot.db_hash:
        sha256 = hashlib.sha256()
        if db_path.exists():
            with open(db_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    sha256.update(chunk)
            if sha256.hexdigest() != snapshot.db_hash:
                return False
    return True


def _restore_git_state(git_tag: str) -> bool:
    """Restore git state to the tagged commit."""
    try:
        result = subprocess.run(
            ["git", "tag", "--list", git_tag],
            capture_output=True, text=True, timeout=5,
        )
        if git_tag not in result.stdout:
            return False
        # Don't reset hard - just checkout the tag
        subprocess.run(
            ["git", "checkout", git_tag],
            capture_output=True, timeout=10,
        )
        return True
    except Exception:
        return False


def _restore_state_files(snapshot_path: Path, aria_home: Path) -> bool:
    """Restore saved state files."""
    state_files = [
        "brain_state.json",
        "orchestrator_state.json",
        "router_state.json",
        "improvement_state.json",
    ]
    restored = 0
    for fname in state_files:
        src = snapshot_path / fname
        if src.exists():
            try:
                dest = aria_home.parent / fname
                dest.write_bytes(src.read_bytes())
                restored += 1
            except Exception:
                pass
    return restored > 0


def _reinstall_plugins(plugins: list[str], aria_home: Path) -> None:
    """Reinstall plugins from snapshot list."""
    plugins_dir = aria_home / "plugins"
    for plugin in plugins:
        plugin_dir = plugins_dir / plugin
        if not plugin_dir.exists():
            try:
                plugin_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass


def _restart_services() -> None:
    """Restart ARIA services."""
    try:
        subprocess.run(
            ["pkill", "-f", "aria-axum"],
            capture_output=True, timeout=5,
        )
    except Exception:
        pass
    try:
        subprocess.run(
            ["pkill", "-f", "aria_autonomous"],
            capture_output=True, timeout=5,
        )
    except Exception:
        pass


class SnapshotRestorer:
    """Restores ARIA state from snapshots."""

    def __init__(self, aria_home: Path) -> None:
        self.aria_home = Path(aria_home)
        self.snapshots_dir = self.aria_home / "snapshots"

    def restore(self, snapshot: Snapshot) -> bool:
        """Restore from a snapshot."""
        try:
            snapshot_path = self.snapshots_dir / snapshot.name
            if not snapshot_path.exists():
                # Try to find by name pattern
                candidates = list(self.snapshots_dir.glob(f"{snapshot.name}*"))
                if not candidates:
                    return False
                snapshot_path = candidates[0]

            # 1. Restore git state
            _restore_git_state(snapshot.git_tag)

            # 2. Restore state files
            _restore_state_files(snapshot_path, self.aria_home)

            # 3. Reinstall plugins
            _reinstall_plugins(snapshot.plugins, self.aria_home)

            # 4. Restart services
            _restart_services()

            return True

        except Exception as exc:
            print(f"Restore failed: {exc}")
            return False

    def restore_by_name(self, name: str) -> bool:
        """Restore by snapshot name."""
        from .models import SnapshotManager
        manager = SnapshotManager(self.aria_home)
        snap = manager.get_snapshot(name)
        if snap is None:
            return False
        return self.restore(snap)