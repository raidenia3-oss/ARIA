"""Release detection — checks GitHub for new ARIA releases."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

from .models import Release, ReleaseChannel

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
GITHUB_ORG = "raidenia3-oss"
GITHUB_REPO = "ARIA"


class ReleaseDetector:
    """Detects available ARIA releases from GitHub."""

    def __init__(
        self,
        aria_home: Path,
        channel: ReleaseChannel = ReleaseChannel.STABLE,
        github_org: str = GITHUB_ORG,
        github_repo: str = GITHUB_REPO,
    ) -> None:
        self.aria_home = Path(aria_home)
        self.channel = channel
        self.github_org = github_org
        self.github_repo = github_repo
        self.metadata_dir = self.aria_home / "metadata"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def check_for_updates(self, current_version: str = "") -> Optional[Release]:
        """Return the latest release for the configured channel, or None."""
        try:
            releases = self._fetch_releases()
            if not releases:
                return None

            channel_release = self._select_latest(releases)
            if channel_release is None:
                return None

            # If we already have this version, no update needed
            if current_version and self._versions_equal(
                channel_release.version, current_version
            ):
                return None

            return channel_release
        except Exception as exc:
            logger.warning("Update check failed: %s", exc)
            return None

    def get_available_versions(self) -> list[Release]:
        """Return all releases for the configured channel."""
        try:
            releases = self._fetch_releases()
            return [self._parse_release(r) for r in releases]
        except Exception as exc:
            logger.warning("Failed to list releases: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _fetch_releases(self) -> list[dict]:
        """Fetch release list from GitHub API."""
        url = f"{GITHUB_API}/repos/{self.github_org}/{self.github_repo}/releases"
        resp = requests.get(
            url,
            headers={"Accept": "application/vnd.github+json"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def _select_latest(self, releases: list[dict]) -> Optional[Release]:
        """Pick the newest release matching the configured channel."""
        candidates: list[Release] = []
        for raw in releases:
            parsed = self._parse_release(raw)
            if parsed is None:
                continue
            if parsed.channel != self.channel:
                continue
            candidates.append(parsed)

        if not candidates:
            return None
        return max(candidates, key=lambda r: r.version_tuple)

    def _parse_release(self, raw: dict) -> Optional[Release]:
        """Parse a GitHub release payload into a Release object."""
        tag = raw.get("tag_name", "")
        if not tag:
            return None

        # Determine channel from tag or release name
        channel = self._detect_channel(raw)

        # Extract version (strip leading 'v')
        version = tag.lstrip("v")

        # Find the asset URL for the release binary
        download_url = ""
        checksum = ""
        for asset in raw.get("assets", []):
            name = asset.get("name", "")
            if name.endswith(".exe") or name.endswith(".tar.gz") or name.endswith(".zip"):
                download_url = asset.get("browser_download_url", "")
                # Try to fetch checksum from asset description
                checksum = asset.get("digest", "")
                break

        # Fallback: use the tag-based download URL pattern
        if not download_url:
            download_url = (
                f"https://github.com/{self.github_org}/{self.github_repo}"
                f"/releases/download/{tag}/ARIA-{tag}.exe"
            )

        # Signature: look for .asc file
        signature = ""
        for asset in raw.get("assets", []):
            if asset.get("name", "").endswith(".asc"):
                signature = asset.get("browser_download_url", "")
                break

        changelog = raw.get("body", "") or ""
        published = raw.get("published_at", "")
        try:
            timestamp = datetime.fromisoformat(published.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            timestamp = datetime.now(timezone.utc)

        return Release(
            version=version,
            channel=channel,
            timestamp=timestamp,
            checksum=checksum,
            download_url=download_url,
            signature=signature,
            changelog=changelog,
        )

    @staticmethod
    def _detect_channel(raw: dict) -> ReleaseChannel:
        """Detect channel from release name/tag/prerelease flags."""
        name = (raw.get("name", "") or "").lower()
        tag = (raw.get("tag_name", "") or "").lower()

        if "unstable" in name or "unstable" in tag or "rawhide" in tag:
            return ReleaseChannel.UNSTABLE
        if "testing" in name or "testing" in tag or raw.get("prerelease", False):
            return ReleaseChannel.TESTING
        return ReleaseChannel.STABLE

    @staticmethod
    def _versions_equal(version_a: str, version_b: str) -> bool:
        """Compare two version strings ignoring build metadata."""
        return re.sub(r"[^0-9.]", "", version_a) == re.sub(r"[^0-9.]", "", version_b)