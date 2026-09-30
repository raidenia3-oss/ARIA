"""One entry point for the whole reference library.

:class:`VideoLibrary` is the object the USB agent, the CLI and the Axum routes
all call, so "download → index → notify" exists once. Every step is reported:
when transcription or Discord fails, the caller gets a result that says so
instead of a video that silently looks complete.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from .agent_notifier import AgentNotifier, NotificationOutcome
from .downloader import VideoDownloader
from .extractor import MediaExtractor
from .indexer import SearchResult, VideoIndexer
from .models import VideoMetadata
from .storage import VideoLibraryStorage

log = logging.getLogger("aria.video-library")


@dataclass
class AddResult:
    """Outcome of adding one reference video."""

    video: VideoMetadata
    added: bool
    notified: NotificationOutcome | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "video": self.video.to_dict(),
            "added": self.added,
            "file_present": bool(self.video.file_path),
        }
        if self.notified is not None:
            payload["notified"] = {
                "agent_id": self.notified.notification.agent_id,
                "delivered": self.notified.delivered,
                "stored": self.notified.stored,
                "detail": self.notified.detail,
            }
        return payload


class VideoLibrary:
    """Facade over storage, downloader, indexer and notifier."""

    def __init__(
        self,
        root: str | os.PathLike[str] | None = None,
        storage: VideoLibraryStorage | None = None,
        downloader: VideoDownloader | None = None,
        indexer: VideoIndexer | None = None,
        notifier: AgentNotifier | None = None,
    ) -> None:
        self.storage = storage or VideoLibraryStorage(root)
        self.extractor = downloader.extractor if downloader else MediaExtractor(
            self.storage.cache_dir
        )
        self.downloader = downloader or VideoDownloader(self.storage, self.extractor)
        self.indexer = indexer or VideoIndexer(self.storage)
        self.notifier = notifier or AgentNotifier()

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    def add_reference(
        self,
        url: str,
        tags: list[str] | None = None,
        agent_type: str | None = None,
        context: str = "",
        notify: bool = True,
        transcribe: bool = True,
    ) -> AddResult:
        """Download a video, index it, and tell the interested agent about it."""
        video = self.downloader.download(
            url,
            tags=tags,
            agent_type=agent_type,
            transcribe=transcribe,
        )
        added = self.indexer.add_video(video)

        outcome: NotificationOutcome | None = None
        if notify and agent_type:
            outcome = self.notifier.notify_agent(agent_type, video, context=context)
        return AddResult(video=video, added=added, notified=outcome)

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------

    def search(self, query: str, limit: int = 20) -> list[SearchResult]:
        return self.indexer.search(query, limit=limit)

    def list_references(self, limit: int | None = None) -> list[VideoMetadata]:
        return self.indexer.list_videos(limit=limit)

    def get(self, video_id: str) -> VideoMetadata | None:
        return self.indexer.get(video_id)

    def stats(self) -> dict[str, Any]:
        return self.indexer.stats()

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def clean(
        self,
        drop_media: bool = False,
        retention_days: int = 30,
    ) -> dict[str, Any]:
        """Reclaim space: yt-dlp leftovers, stale notifications, orphan media.

        Without this the stick fills with files nothing reads — partial transfers
        from interrupted downloads, transcripts of videos that were deleted by
        hand, one notification row per video per agent — and `ensure_capacity`
        then refuses every new download with no way back from inside the tool.

        ``drop_media`` is opt-in because it deletes video files. It only removes
        media for ids that are *not* in the index; an indexed video is the user's
        library and is never touched here.
        """
        partials = self.storage.cleanup_partials()
        orphans = [path for path in self.storage.media_files() if not self.indexer.get(path.stem)]
        if drop_media:
            for path in orphans:
                try:
                    path.unlink()
                except OSError as exc:  # pragma: no cover - permission dependent
                    log.warning("could not remove %s: %s", path, exc)

        known = {video.id for video in self.indexer.list_videos()}
        cached = 0
        for path in self.storage.cache_dir.glob("*.txt"):
            if path.stem not in known:
                try:
                    path.unlink()
                    cached += 1
                except OSError as exc:  # pragma: no cover - permission dependent
                    log.warning("could not remove %s: %s", path, exc)

        notifications = self.notifier.prune(retention_days=retention_days)
        return {
            "partials_removed": partials,
            "orphan_media_found": len(orphans),
            "orphan_media_removed": len(orphans) if drop_media else 0,
            "cached_transcripts_removed": cached,
            "notifications_removed": notifications,
            "free_bytes": self.storage.free_bytes(),
        }

    def status(self) -> dict[str, Any]:
        """Where the library lives, which tools are installed, what is in it."""
        return {
            "storage": self.storage.report(),
            "tools": self.extractor.tool_status(),
            "discord_configured": bool(self.notifier.webhook),
            "notifications_db": str(self.notifier.db_path),
            "index": self.stats(),
        }
