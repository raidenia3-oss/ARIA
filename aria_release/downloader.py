"""Resumable release downloader with chunked downloads."""

from __future__ import annotations

import logging
import os
import shutil
import time
from pathlib import Path
from typing import Callable, Optional

import requests

from .models import Release
from .verifier import compute_checksum, verify_checksum

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 1024  # 1 MiB
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


class ReleaseDownloader:
    """Downloads ARIA releases with resume support and integrity checks."""

    def __init__(
        self,
        aria_home: Path,
        chunk_size: int = CHUNK_SIZE,
    ) -> None:
        self.aria_home = Path(aria_home)
        self.cache_dir = self.aria_home / "update-cache"
        self.downloads_dir = self.cache_dir / "downloads"
        self.verified_dir = self.cache_dir / "verified"
        self.chunk_size = chunk_size

        # Ensure directories exist
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.verified_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def download(self, release: Release, progress_callback: Optional[Callable[[int, int], None]] = None) -> Optional[Path]:
        """Download a release with resume support.

        Returns the path to the downloaded file, or None on failure.
        """
        dest_dir = self.downloads_dir / f"v{release.version}"
        dest_dir.mkdir(parents=True, exist_ok=True)

        filename = self._extract_filename(release.download_url)
        dest_path = dest_dir / filename

        # Check if already fully downloaded
        if dest_path.exists():
            if not release.checksum or verify_checksum(dest_path, release.checksum):
                logger.info("Release already downloaded: %s", dest_path)
                return dest_path
            else:
                logger.warning("Existing download failed checksum, re-downloading")
                dest_path.unlink()

        # Download with retries
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                self._download_with_resume(release, dest_path, progress_callback)
                break
            except Exception as exc:
                logger.warning("Download attempt %d/%d failed: %s", attempt, MAX_RETRIES, exc)
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY * attempt)
                else:
                    return None

        # Verify checksum
        if release.checksum:
            if not verify_checksum(dest_path, release.checksum):
                logger.error("Checksum verification failed for %s", dest_path)
                return None

        # Move to verified directory
        verified_path = self.verified_dir / filename
        shutil.move(str(dest_path), str(verified_path))
        logger.info("Release verified and cached: %s", verified_path)
        return verified_path

    def get_cached_release(self, version: str) -> Optional[Path]:
        """Return path to a previously downloaded release, or None."""
        verified_dir = self.verified_dir
        for path in verified_dir.iterdir():
            if f"v{version}" in path.name or version in path.name:
                return path
        return None

    def cleanup_old_releases(self, keep: int = 3) -> None:
        """Remove old release downloads, keeping only the N newest."""
        versions = sorted(self.downloads_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        for old_dir in versions[keep:]:
            shutil.rmtree(old_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _download_with_resume(
        self,
        release: Release,
        dest_path: Path,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        """Download a file with resume support."""
        # Check for partial download
        headers = {}
        existing_size = 0
        if dest_path.exists():
            existing_size = dest_path.stat().st_size
            headers["Range"] = f"bytes={existing_size}-"

        resp = requests.get(
            release.download_url,
            headers=headers,
            stream=True,
            timeout=60,
        )
        resp.raise_for_status()

        total = existing_size + int(resp.headers.get("Content-Length", 0))
        mode = "ab" if existing_size > 0 else "wb"

        downloaded = existing_size
        with open(dest_path, mode) as f:
            for chunk in resp.iter_content(chunk_size=self.chunk_size):
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    progress_callback(downloaded, total)

    @staticmethod
    def _extract_filename(url: str) -> str:
        """Extract filename from download URL."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return os.path.basename(parsed.path) or "aria-release.bin"