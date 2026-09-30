"""Integration helpers for the rolling release pipeline."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .detector import ReleaseDetector
from .downloader import ReleaseDownloader
from .models import Release, ReleaseChannel
from .verifier import MetadataVerifier, verify_checksum
from .updater import Updater

logger = logging.getLogger(__name__)


class RollingReleasePipeline:
    """High-level orchestrator for the rolling release pipeline."""

    def __init__(
        self,
        aria_home: Path,
        channel: ReleaseChannel = ReleaseChannel.STABLE,
        current_version: str = "",
    ) -> None:
        self.aria_home = Path(aria_home)
        self.channel = channel
        self.current_version = current_version

        self.detector = ReleaseDetector(self.aria_home, channel)
        self.verifier = MetadataVerifier(self.aria_home / "metadata")
        self.downloader = ReleaseDownloader(self.aria_home)
        self.updater = Updater(self.aria_home)

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------
    def check_and_update(self) -> dict:
        """Run the full check-and-update pipeline.

        Returns a dict with status information.
        """
        result = {
            "checked": False,
            "update_available": False,
            "downloaded": False,
            "applied": False,
            "error": None,
        }

        try:
            # 1. Check for updates
            release = self.detector.check_for_updates(self.current_version)
            if release is None:
                result["checked"] = True
                return result

            result["checked"] = True
            result["update_available"] = True
            result["version"] = release.version

            # 2. Verify metadata
            if not self.verifier.verify_metadata("timestamp", release.to_dict()):
                result["error"] = "Metadata verification failed"
                return result

            # 3. Download
            binary_path = self.downloader.download(release)
            if binary_path is None:
                result["error"] = "Download failed"
                return result

            result["downloaded"] = True

            # 4. Apply
            if self.updater.apply_update(release, binary_path):
                result["applied"] = True
                self.current_version = release.version
            else:
                result["error"] = "Update application failed"

        except Exception as exc:
            result["error"] = str(exc)
            logger.exception("Pipeline error: %s", exc)

        return result

    def check_only(self) -> Optional[Release]:
        """Check for updates without downloading or applying."""
        return self.detector.check_for_updates(self.current_version)

    def get_current_version(self) -> Optional[str]:
        """Return the currently installed version."""
        if self.current_version:
            return self.current_version
        return self.updater.get_current_version()