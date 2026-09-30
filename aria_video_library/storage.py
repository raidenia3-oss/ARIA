"""USB layout management for the video reference library.

The stick holds three things and nothing else::

    <usb>/
      videos/reference-library/    the media files
      videos/cache/                thumbnails, transcripts, ffprobe dumps
      videos/index.json            searchable metadata

The root is resolved in this order: an explicit argument, ``$ARIA_USB_PATH``, the
first removable drive Windows reports, and finally a per-user directory under
``~/.local/share/aria-usb``. The last one is a *fallback, not a USB*: it exists
so a laptop with no stick plugged in still has somewhere to write, and it is
reported as ``removable: false`` rather than pretended to be the drive the user
meant.
"""

from __future__ import annotations

import ctypes
import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .errors import InsufficientSpaceError, StorageError

log = logging.getLogger("aria.video-library")

#: Overrides the automatic USB lookup.
USB_PATH_ENV = "ARIA_USB_PATH"

#: Directories created under the library root.
VIDEO_SUBDIR = "reference-library"
CACHE_SUBDIR = "cache"
INDEX_FILENAME = "index.json"

#: Containers the library accepts as a finished download.
MEDIA_SUFFIXES = (".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v")
#: yt-dlp scratch files: a partial transfer or an unmerged stream component.
PARTIAL_MARKERS = (".part", ".ytdl", ".temp", ".tmp")

#: Leave this much headroom on the stick; a download that fills a filesystem to
#: 100% also fails on the rename, which leaves a half-written file behind.
DEFAULT_FREE_SPACE_MARGIN_BYTES = 512 * 1024 * 1024


@dataclass(frozen=True)
class UsbDevice:
    """A candidate library root and how it was chosen."""

    path: Path
    source: str
    removable: bool


def _windows_removable_drives() -> list[Path]:
    """Removable drive roots on Windows, in drive-letter order.

    Returns an empty list off Windows and on any ctypes failure: drive probing
    is a convenience, and a library that cannot enumerate sticks should still
    run against an explicit path.
    """
    if os.name != "nt":
        return []

    DRIVE_REMOVABLE = 2
    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        mask = kernel32.GetLogicalDrives()
    except (AttributeError, OSError):
        return []

    found: list[Path] = []
    for index in range(26):
        if not mask & (1 << index):
            continue
        letter = f"{chr(ord('A') + index)}:\\"
        try:
            if kernel32.GetDriveTypeW(ctypes.c_wchar_p(letter)) == DRIVE_REMOVABLE:
                found.append(Path(letter))
        except OSError:
            continue
    return found


def resolve_usb_root(explicit: str | os.PathLike[str] | None = None) -> UsbDevice:
    """Pick the library root, most explicit source first."""
    if explicit:
        return UsbDevice(Path(explicit).expanduser(), "argument", False)

    from_env = os.getenv(USB_PATH_ENV, "").strip()
    if from_env:
        return UsbDevice(Path(from_env).expanduser(), f"${USB_PATH_ENV}", False)

    candidates = _windows_removable_drives()
    if len(candidates) == 1:
        return UsbDevice(candidates[0], "windows-removable-drive", True)
    if len(candidates) > 1:
        # Ambiguous: guessing would create the library tree on an unrelated
        # stick, and a read-only card reader would break every command.
        listed = ", ".join(str(candidate) for candidate in candidates)
        log.warning(
            "several removable drives are present (%s); set %s to choose one",
            listed,
            USB_PATH_ENV,
        )

    if os.name == "nt":
        fallback = Path(os.getenv("LOCALAPPDATA", Path.home())) / "ARIA" / "usb-library"
    else:
        fallback = Path(
            os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share")
        ) / "aria-usb"
    return UsbDevice(fallback.expanduser(), "fallback", False)


class VideoLibraryStorage:
    """The on-disk layout. Constructing it creates the directory tree."""

    def __init__(self, root: str | os.PathLike[str] | None = None) -> None:
        self.device = resolve_usb_root(root)
        self.root = self.device.path
        self.video_dir = self.root / "videos" / VIDEO_SUBDIR
        self.cache_dir = self.root / "videos" / CACHE_SUBDIR
        self.index_file = self.root / "videos" / INDEX_FILENAME
        self.ensure_layout()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def ensure_layout(self) -> None:
        """Create the library directories, failing loudly if the stick is gone.

        A read-only or absent root is a real problem: silently falling back would
        write a library the user then cannot find.
        """
        try:
            self.video_dir.mkdir(parents=True, exist_ok=True)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StorageError(
                f"cannot create the library layout under {self.root}: {exc}"
            ) from exc

    def is_media(self, path: Path) -> bool:
        """True when ``path`` is a finished video, not a yt-dlp leftover.

        ``<id>.mp4.part`` and the ``<id>.f137.mp4`` stream components of an
        interrupted merge both start with the id and end in a container-looking
        suffix, so a suffix check alone is not enough.
        """
        name = Path(path).name.lower()
        if any(marker in name for marker in PARTIAL_MARKERS):
            return False
        # yt-dlp names merged-away components `<id>.<format id>.<ext>`.
        stem = Path(path).stem
        if "." in stem and Path(path).suffix.lower() in MEDIA_SUFFIXES:
            return False
        return Path(path).suffix.lower() in MEDIA_SUFFIXES

    def video_path(self, video_id: str) -> Path:
        return self.video_dir / f"{video_id}.mp4"

    def find_video(self, video_id: str) -> Path | None:
        """Locate a stored video, whatever container it ended up in.

        The id is the filename stem and the extension is decided at download
        time, so the exact ``.mp4`` guess is only a fast path. Partial transfers
        are excluded: treating one as the stored video would describe a
        truncated file and permanently skip re-downloading it.
        """
        direct = self.video_path(video_id)
        if direct.exists() and self.is_media(direct):
            return direct
        for candidate in sorted(self.video_dir.glob(f"{video_id}.*")):
            if candidate.is_file() and self.is_media(candidate):
                return candidate
        return None

    def cleanup_partials(self, video_id: str | None = None) -> int:
        """Delete yt-dlp leftovers; returns how many files were removed.

        Without this, an aborted download leaves megabytes on the stick forever
        and `ensure_capacity` eventually refuses every new download because of
        files nothing will ever read.
        """
        pattern = f"{video_id}.*" if video_id else "*"
        removed = 0
        for candidate in self.video_dir.glob(pattern):
            if not candidate.is_file() or self.is_media(candidate):
                continue
            try:
                candidate.unlink()
                removed += 1
                log.info("removed partial download %s", candidate.name)
            except OSError as exc:  # pragma: no cover - permission dependent
                log.warning("could not remove %s: %s", candidate, exc)
        return removed

    # ------------------------------------------------------------------
    # Capacity
    # ------------------------------------------------------------------

    def free_bytes(self) -> int:
        """Free space on the volume holding the library."""
        probe = self.root if self.root.exists() else self.root.anchor or "/"
        return shutil.disk_usage(probe).free

    def used_bytes(self) -> int:
        """Bytes currently occupied by stored videos."""
        if not self.video_dir.exists():
            return 0
        return sum(
            entry.stat().st_size for entry in self.video_dir.iterdir() if entry.is_file()
        )

    def ensure_capacity(
        self,
        expected_bytes: int = 0,
        margin_bytes: int = DEFAULT_FREE_SPACE_MARGIN_BYTES,
    ) -> None:
        """Refuse a download that would leave the stick without headroom.

        ``expected_bytes`` of 0 means "size unknown" (yt-dlp did not report one),
        in which case only the margin is reserved.
        """
        required = max(0, int(expected_bytes)) + max(0, int(margin_bytes))
        free = self.free_bytes()
        if free < required:
            raise InsufficientSpaceError(
                f"{self.root} has {free} bytes free but the download needs "
                f"{required} ({expected_bytes} media + {margin_bytes} headroom)"
            )

    def cache_used_bytes(self) -> int:
        """Bytes occupied by transcripts and other scratch files."""
        if not self.cache_dir.exists():
            return 0
        return sum(
            entry.stat().st_size for entry in self.cache_dir.iterdir() if entry.is_file()
        )

    def media_files(self) -> list[Path]:
        """Every finished video currently on the stick."""
        if not self.video_dir.exists():
            return []
        return sorted(
            entry
            for entry in self.video_dir.iterdir()
            if entry.is_file() and self.is_media(entry)
        )

    def report(self) -> dict:
        """Machine-readable description of where the library lives."""
        return {
            "root": str(self.root),
            "video_dir": str(self.video_dir),
            "cache_dir": str(self.cache_dir),
            "index_file": str(self.index_file),
            "source": self.device.source,
            "removable": self.device.removable,
            "free_bytes": self.free_bytes(),
            "used_bytes": self.used_bytes(),
            "cache_bytes": self.cache_used_bytes(),
            "videos": len(self.media_files()),
        }
