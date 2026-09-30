"""ARIA Video Reference Library.

A USB stick that accumulates short-form video references, describes them
(duration, resolution, transcript, keyframes, summary) and tells the autonomous
agents which ones are worth watching.

Layout:

``aria_video_library.storage``
    Where the stick is and the three directories the library owns.
``aria_video_library.downloader``
    yt-dlp wrapper: download, then describe the file it produced.
``aria_video_library.extractor``
    ffprobe, ffmpeg scene detection, Whisper and Ollama summaries.
``aria_video_library.indexer``
    ``videos/index.json`` — atomic writes, weighted search, disk rebuild.
``aria_video_library.agent_notifier``
    Discord message plus the ``agents_video_references`` row agents read.
``aria_video_library.library``
    :class:`VideoLibrary`, the single download → index → notify path.
``aria_video_library.cli``
    The ``aria-videos`` command.
"""

from __future__ import annotations

from aria_version import ARIA_VERSION

from .agent_notifier import AgentNotifier, NotificationOutcome, build_message
from .downloader import VideoDownloader, build_video_id, infer_source, sanitize_component
from .errors import (
    DownloadError,
    ExtractionError,
    IndexCorruptError,
    InsufficientSpaceError,
    LibraryError,
    StorageError,
    ToolMissingError,
)
from .extractor import MediaExtractor, MediaProbe, TranscriptResult
from .indexer import SearchResult, VideoIndexer
from .library import AddResult, VideoLibrary
from .models import AgentNotification, VideoMetadata
from .storage import UsbDevice, VideoLibraryStorage, resolve_usb_root

__version__ = ARIA_VERSION

__all__ = [
    "ARIA_VERSION",
    "AddResult",
    "AgentNotification",
    "AgentNotifier",
    "DownloadError",
    "ExtractionError",
    "IndexCorruptError",
    "InsufficientSpaceError",
    "LibraryError",
    "MediaExtractor",
    "MediaProbe",
    "NotificationOutcome",
    "SearchResult",
    "StorageError",
    "ToolMissingError",
    "TranscriptResult",
    "UsbDevice",
    "VideoDownloader",
    "VideoIndexer",
    "VideoLibrary",
    "VideoLibraryStorage",
    "VideoMetadata",
    "__version__",
    "build_message",
    "build_video_id",
    "infer_source",
    "resolve_usb_root",
    "sanitize_component",
]
