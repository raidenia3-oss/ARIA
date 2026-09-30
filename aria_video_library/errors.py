"""Exception types shared across the video library.

One base class so callers can catch anything the library raises on purpose,
without also swallowing the ``OSError``/``json.JSONDecodeError`` that signal real
bugs or a broken disk.
"""

from __future__ import annotations


class LibraryError(RuntimeError):
    """Base class for every deliberate failure in ``aria_video_library``."""


class ToolMissingError(LibraryError):
    """An external binary the operation needs is not on ``PATH``."""

    def __init__(self, tool: str, hint: str = "") -> None:
        message = f"'{tool}' is not installed or not on PATH"
        if hint:
            message = f"{message}; {hint}"
        super().__init__(message)
        self.tool = tool


class DownloadError(LibraryError):
    """yt-dlp ran and refused the URL (private, geo-blocked, network, …)."""


class ExtractionError(LibraryError):
    """ffprobe/ffmpeg could not read the media file."""


class StorageError(LibraryError):
    """The library layout on the stick could not be created."""


class InsufficientSpaceError(StorageError):
    """The stick cannot hold the download plus a safety margin."""


class IndexCorruptError(LibraryError):
    """The index on disk is unusable and cannot be repaired."""
