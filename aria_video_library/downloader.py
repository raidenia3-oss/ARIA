"""yt-dlp wrapper that produces a fully-described :class:`VideoMetadata`.

One download is one media file plus a metadata record, and both are produced
here so a half-described video never reaches the index. The filename is
``<source>_<slug>_<YYYYMMDD>``, which keeps provenance and lets two versions of
the same topic coexist instead of overwriting each other.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from .errors import DownloadError, ToolMissingError
from .extractor import CommandResult, MediaExtractor, Runner, SubprocessRunner
from .models import DEFAULT_TAGS, VideoMetadata, utcnow
from .storage import VideoLibraryStorage

YTDLP = "yt-dlp"

#: Sources the library recognises by name in the filename.
KNOWN_SOURCES = {
    "instagram.com": "instagram",
    "instagr.am": "instagram",
    "tiktok.com": "tiktok",
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "x.com": "x",
    "twitter.com": "x",
}

#: Hosts the download path accepts. Fail-closed: an unknown host is rejected,
#: and the list is read from ``ARIA_VIDEO_SOURCES`` (comma-separated) when it is
#: set, so an operator can widen or narrow it. Empty entries are ignored, so a
#: trailing comma or a blank value still falls back to the defaults.
ALLOWED_DOMAINS: frozenset[str] = frozenset(
    os.getenv("ARIA_VIDEO_SOURCES", "").strip().split(",")
)
if not ALLOWED_DOMAINS or any(not d.strip() for d in ALLOWED_DOMAINS):
    ALLOWED_DOMAINS = frozenset(KNOWN_SOURCES.keys())

#: How long a single download may run before it is abandoned.
DOWNLOAD_TIMEOUT_SECS = 3600
#: Longest slug fragment kept from the upstream title.
SLUG_MAX_LEN = 40

_UNSAFE_RE = re.compile(r"[^a-z0-9]+")


def sanitize_component(text: str, max_len: int = SLUG_MAX_LEN) -> str:
    """Lowercase ASCII slug, safe on Windows, macOS and Linux filesystems.

    Titles come from Instagram and routinely contain ``/``, ``:``, emoji and
    RTL text. Anything outside ``[a-z0-9-]`` collapses to a single dash, and the
    result is never empty, so the id always has a readable core.
    """
    ascii_text = (
        text.encode("ascii", "ignore").decode("ascii").lower().replace("&", " and ")
    )
    slug = _UNSAFE_RE.sub("-", ascii_text).strip("-")
    slug = "-".join(part for part in slug.split("-") if part)
    return slug[:max_len].strip("-")


def infer_source(url: str) -> str:
    """Platform name for a URL, from its host."""
    host = (urlparse(url).hostname or "").lower()
    for domain, name in KNOWN_SOURCES.items():
        if host == domain or host.endswith(f".{domain}"):
            return name
    return "web" if host else "unknown"


def url_fingerprint(url: str) -> str:
    """Six hex characters identifying the upstream video.

    Titles are not identifiers: two reels called "AI Tools Episode 5" collide on
    the same day, and one would then be described with the other's content. The
    fingerprint comes from the canonical URL, so the same video always gets the
    same id and a different one never does.
    """
    return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()[:6]


def build_video_id(url: str, title: str, when: datetime) -> str:
    """``instagram_ai-tools-a1b2c3_20260930`` — source, slug, URL, download date."""
    slug = (
        sanitize_component(title)
        or sanitize_component(Path(urlparse(url).path).name)
        or "video"
    )
    return f"{infer_source(url)}_{slug}-{url_fingerprint(url)}_{when:%Y%m%d}"


class VideoDownloader:
    """Downloads a video onto the library stick and describes it."""

    def __init__(
        self,
        storage: VideoLibraryStorage,
        extractor: MediaExtractor | None = None,
        runner: Runner | None = None,
        ytdlp: str = YTDLP,
        clock: Callable[[], datetime] = utcnow,
        language: str = "es",
    ) -> None:
        self.storage = storage
        self.extractor = extractor or MediaExtractor(storage.cache_dir)
        self.runner: Runner = runner or SubprocessRunner()
        self.ytdlp = ytdlp
        self.clock = clock
        self.language = language

    # ------------------------------------------------------------------
    # Remote inspection
    # ------------------------------------------------------------------

    def probe_remote(self, url: str) -> dict[str, Any]:
        """Ask yt-dlp for the video's own metadata without downloading it."""
        _validate_url(url)
        result = self.runner(
            [self.ytdlp, "--dump-single-json", "--no-playlist", "--no-warnings", url], 300
        )
        if not result.ok:
            raise DownloadError(f"yt-dlp could not read {url}: {result.tail(300)}")
        try:
            data = json.loads(result.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise DownloadError(f"yt-dlp returned invalid JSON for {url}") from exc
        if not isinstance(data, dict) or not data:
            raise DownloadError(f"yt-dlp reported no video at {url}")
        return data

    def expected_size(self, info: dict[str, Any]) -> int:
        """Best available size estimate, used for the free-space check.

        ``filesize`` is absent for some extractors, so the chosen format's own
        size and the container's bitrate-times-duration estimate are tried in
        turn before giving up and letting the margin speak for itself.
        """
        for key in ("filesize", "filesize_approx"):
            value = info.get(key)
            if isinstance(value, (int, float)) and value > 0:
                return int(value)
        for entry in info.get("requested_formats") or []:
            if isinstance(entry, dict) and entry.get("filesize"):
                return int(entry["filesize"])
        duration = info.get("duration")
        bitrate = info.get("tbr") or info.get("vbr")
        try:
            if duration and bitrate:
                return int(float(duration) * float(bitrate) * 1000 / 8)
        except (TypeError, ValueError):
            return 0
        return 0

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def download(
        self,
        url: str,
        tags: list[str] | None = None,
        agent_type: str | None = None,
        agent_notes: str = "",
        transcribe: bool = True,
    ) -> VideoMetadata:
        """Fetch ``url`` into the library and return its full description.

        Re-downloading a video already on the stick is a no-op: the existing
        file is re-described from disk instead, so a repeated agent request
        costs one ffprobe and no bandwidth.
        """
        _validate_url(url)
        info = self.probe_remote(url)
        title = str(info.get("title") or "").strip() or "Unknown"
        when = self.clock()
        video_id = build_video_id(url, title, when)

        existing = self.storage.find_video(video_id)
        if existing is not None:
            return self._describe(
                existing,
                video_id=video_id,
                source_url=url,
                title=title,
                when=when,
                tags=tags,
                agent_type=agent_type,
                agent_notes=agent_notes or f"already on the library: {existing.name}",
                transcribe=transcribe,
            )

        # A previous attempt may have left `<id>.mp4.part` or an unmerged
        # component behind; those would be picked up as the stored video later.
        self.storage.cleanup_partials(video_id)
        self.storage.ensure_capacity(self.expected_size(info))
        media_path = self._fetch(url, video_id)
        self.storage.cleanup_partials(video_id)
        return self._describe(
            media_path,
            video_id=video_id,
            source_url=url,
            title=title,
            when=when,
            tags=tags,
            agent_type=agent_type,
            agent_notes=agent_notes,
            transcribe=transcribe,
        )

    def _fetch(self, url: str, video_id: str) -> Path:
        """Run the actual transfer into the library directory."""
        template = str(self.storage.video_dir / f"{video_id}.%(ext)s")
        argv: list[str] = [
            self.ytdlp,
            "--no-playlist",
            "--no-warnings",
            "--newline",
            # Best video plus best audio, merged to a single mp4 file: a
            # separate audio track would leave two files where the library
            # expects one media file per id.
            "-f",
            "bestvideo*+bestaudio/best",
            "--merge-output-format",
            "mp4",
            "-o",
            template,
            url,
        ]
        try:
            result: CommandResult = self.runner(argv, DOWNLOAD_TIMEOUT_SECS)
        except ToolMissingError as exc:
            raise ToolMissingError(
                self.ytdlp, "install it with: pip install yt-dlp"
            ) from exc
        if not result.ok:
            # yt-dlp leaves a .part behind on failure; keeping it would fill the
            # stick and make a later run believe the video is already there.
            self.storage.cleanup_partials(video_id)
            raise DownloadError(f"yt-dlp failed for {url}: {result.tail(300)}")

        media_path = self.storage.find_video(video_id)
        if media_path is None:
            raise DownloadError(
                f"yt-dlp reported success but no file for {video_id} matched {template}"
            )
        return media_path

    def _describe(
        self,
        media_path: Path,
        video_id: str,
        source_url: str,
        title: str,
        when: datetime,
        tags: list[str] | None,
        agent_type: str | None,
        agent_notes: str,
        transcribe: bool,
    ) -> VideoMetadata:
        """Read facts, transcript, keyframes and summary out of a stored file."""
        probe = self.extractor.probe(media_path)

        transcript = ""
        if transcribe:
            transcript = self.extractor.transcript(media_path, self.language).text
        keyframes = self.extractor.keyframes(media_path)
        summary = self.extractor.summarize(transcript, title=title)

        return VideoMetadata(
            id=video_id,
            source_url=source_url,
            title=title,
            date_downloaded=when,
            duration_seconds=probe.duration_seconds,
            size_bytes=probe.size_bytes or media_path.stat().st_size,
            format=(probe.format.split(",")[0] if probe.format else "mp4"),
            resolution=probe.resolution,
            fps=round(probe.fps, 2),
            transcript=transcript,
            summary=summary,
            keyframes=keyframes,
            tags=list(tags) if tags else list(DEFAULT_TAGS),
            agent_type=agent_type,
            agent_notes=agent_notes or f"Stored on the library stick as {media_path.name}",
            file_path=str(media_path),
        )


def _host_of(url: str) -> str | None:
    """Lowercase host of an ``http(s)`` URL, stripping credentials and port."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return host or None


def is_allowed_domain(url: str) -> bool:
    """True when the URL's host is in :data:`ALLOWED_DOMAINS`.

    Exact match or a subdomain of an allowed host — ``instagram.com`` matches
    ``www.instagram.com`` but not ``notinstagram.com``.
    """
    host = _host_of(url)
    if not host:
        return False
    return any(
        host == domain or host.endswith(f".{domain}")
        for domain in ALLOWED_DOMAINS
    )


def _validate_url(url: str) -> None:
    """Reject anything that is not an http(s) URL from an allowed source.

    yt-dlp accepts ``file://``, ``smb://`` and arbitrary protocol handlers, so
    the scheme check is the boundary that keeps a request from turning into a
    local file read, and the host check is the boundary that keeps it from
    turning into a fetch of whatever the host can reach.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise DownloadError(f"only http(s) URLs are supported, got '{parsed.scheme or 'none'}'")
    if not parsed.netloc:
        raise DownloadError(f"'{url}' has no host")
    if not is_allowed_domain(url):
        host = _host_of(url) or parsed.netloc
        raise DownloadError(
            f"'{host}' is not an allowed source; allowed: "
            f"{', '.join(sorted(ALLOWED_DOMAINS))}"
        )
