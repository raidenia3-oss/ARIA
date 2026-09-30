"""Release updater with atomic symlink updates and rollback."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import Release

logger = logging.getLogger(__name__)


class Updater:
    """Applies ARIA releases with atomic symlink updates and rollback."""

    def __init__(self, aria_home: Path) -> None:
        self.aria_home = Path(aria_home)
        self.releases_dir = self.aria_home / "releases"
        self.current_link = self.aria_home / "current"
        self.snapshots_dir = self.aria_home / "snapshots"

        self.releases_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def apply_update(self, release: Release, binary_path: Path) -> bool:
        """Apply a release update atomically.

        Steps:
        1. Create pre-upgrade snapshot
        2. Install release binary
        3. Atomically update current symlink
        4. Restart services
        """
        version = release.version
        release_path = self.releases_dir / f"v{version}"
        release_path.mkdir(parents=True, exist_ok=True)

        try:
            # 1. Create pre-upgrade snapshot
            snapshot_name = f"pre-upgrade-{version}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            self._create_snapshot(snapshot_name)

            # 2. Install release binary
            dest_binary = release_path / self._binary_name()
            shutil.copy2(str(binary_path), str(dest_binary))
            os.chmod(dest_binary, 0o755)

            # 3. Atomic symlink update
            self._atomic_symlink_update(release_path)

            # 4. Restart services
            self._restart_services()

            logger.info("Successfully applied update to v%s", version)
            return True

        except Exception as exc:
            logger.error("Update to v%s failed: %s", version, exc)
            self._rollback(version)
            return False

    def rollback(self, failed_version: str) -> bool:
        """Rollback to the previous stable version."""
        return self._rollback(failed_version)

    def get_current_version(self) -> Optional[str]:
        """Return the version currently pointed to by the 'current' symlink."""
        if not self.current_link.exists() and not self.current_link.is_symlink():
            return None

        try:
            target = self.current_link.resolve()
            return target.name.lstrip("v")
        except OSError:
            return None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _atomic_symlink_update(self, new_path: Path) -> None:
        """Atomically update the current symlink (or copy fallback)."""
        temp_link = self.aria_home / "current.tmp"

        # Remove old temp link if it exists
        if temp_link.exists() or temp_link.is_symlink():
            if temp_link.is_symlink():
                temp_link.unlink()
            else:
                shutil.rmtree(temp_link, ignore_errors=True)

        # Try symlink first, fall back to directory copy
        try:
            temp_link.symlink_to(new_path)
        except OSError:
            logger.warning("Symlink failed, falling back to directory copy")
            if temp_link.exists():
                shutil.rmtree(temp_link, ignore_errors=True)
            shutil.copytree(str(new_path), str(temp_link))

        # Atomic rename
        if self.current_link.exists() or self.current_link.is_symlink():
            if self.current_link.is_symlink():
                self.current_link.unlink()
            else:
                shutil.rmtree(self.current_link, ignore_errors=True)

        os.replace(temp_link, self.current_link)
        logger.info("Current updated: -> %s", new_path)

    def _create_snapshot(self, name: str) -> None:
        """Create a pre-upgrade snapshot for rollback."""
        snapshot_path = self.snapshots_dir / name
        snapshot_path.mkdir(parents=True, exist_ok=True)

        # Save current symlink target
        if self.current_link.exists() or self.current_link.is_symlink():
            try:
                if self.current_link.is_symlink():
                    target = self.current_link.resolve()
                    (snapshot_path / "previous_version.txt").write_text(target.name)
                else:
                    # Directory copy fallback
                    (snapshot_path / "previous_version.txt").write_text(
                        self.current_link.name
                    )
            except OSError:
                pass

        # Save state JSONs
        state_files = [
            "brain_state.json",
            "orchestrator_state.json",
            "router_state.json",
            "improvement_state.json",
        ]
        aria_parent = self.aria_home.parent
        for fname in state_files:
            src = aria_parent / fname
            if src.exists():
                try:
                    shutil.copy2(str(src), str(snapshot_path / fname))
                except OSError:
                    pass

        logger.info("Snapshot created: %s", name)

    def _rollback(self, failed_version: str) -> bool:
        """Rollback to the previous version."""
        # Find the most recent snapshot
        snapshots = sorted(self.snapshots_dir.iterdir(), reverse=True)
        if not snapshots:
            logger.error("No snapshots available for rollback")
            return False

        snapshot = snapshots[0]
        version_file = snapshot / "previous_version.txt"

        if not version_file.exists():
            logger.error("Snapshot missing version info: %s", snapshot)
            return False

        previous_version = version_file.read_text().strip()
        # Handle both "v6.0.0" and "6.0.0" formats
        if not previous_version.startswith("v"):
            previous_path = self.releases_dir / f"v{previous_version}"
        else:
            previous_path = self.releases_dir / previous_version

        if not previous_path.exists():
            logger.error("Previous version directory missing: %s", previous_path)
            return False

        try:
            # Atomic symlink update back (with fallback)
            temp_link = self.aria_home / "current.tmp"
            if temp_link.exists() or temp_link.is_symlink():
                if temp_link.is_symlink():
                    temp_link.unlink()
                else:
                    shutil.rmtree(temp_link, ignore_errors=True)

            try:
                temp_link.symlink_to(previous_path)
            except OSError:
                shutil.copytree(str(previous_path), str(temp_link))

            if self.current_link.exists() or self.current_link.is_symlink():
                if self.current_link.is_symlink():
                    self.current_link.unlink()
                else:
                    shutil.rmtree(self.current_link, ignore_errors=True)

            os.replace(temp_link, self.current_link)

            self._restart_services()
            logger.info("Rolled back to v%s", previous_version)
            return True
        except Exception as exc:
            logger.error("Rollback failed: %s", exc)
            return False

    def _restart_services(self) -> None:
        """Restart ARIA services after an update."""
        try:
            # Stop services
            self._run_command(["pkill", "-f", "aria-axum"])
            self._run_command(["pkill", "-f", "aria_autonomous"])
        except Exception:
            pass  # Services may not be running

        # Start services
        try:
            subprocess.Popen(
                [sys.executable, "aria_autonomous.py"],
                cwd=self.aria_home.parent,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            logger.warning("Failed to restart autonomous: %s", exc)

    def _run_command(self, cmd: list[str]) -> None:
        """Run a command silently."""
        try:
            subprocess.run(cmd, capture_output=True, timeout=10)
        except Exception:
            pass

    @staticmethod
    def _binary_name() -> str:
        """Return the binary filename for the current platform."""
        if sys.platform == "win32":
            return "ARIA.exe"
        return "aria"