"""The searchable index that lives at ``videos/index.json``.

The index is a cache of what is on the stick, not the source of truth for the
media itself: if it is deleted the videos are still there and
:meth:`VideoIndexer.rebuild_from_disk` reconstructs a usable, if thinner, index.
Writes are atomic (temp file plus ``os.replace``) *and* serialised by a lock file,
because the stick is written by several processes at once — the USB agent, every
``aria-videos download`` job the Axum route dispatches, and a human running the
CLI. ``os.replace`` keeps a single write intact; it does not keep two writers
from clobbering each other's entries.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

from .errors import IndexCorruptError
from .models import DEFAULT_TAGS, VideoMetadata, utcnow
from .storage import VideoLibraryStorage

log = logging.getLogger("aria.video-library")

#: Bumped when the on-disk shape changes. A file written by a *newer* schema is
#: refused rather than silently downgraded, which would drop its extra fields.
SCHEMA_VERSION = 1

#: Sidecar used to serialise read-modify-write across processes.
LOCK_FILENAME = "index.lock"
#: Kept copy of the last known-good index.
BACKUP_FILENAME = "index.json.bak"
#: Quarantined copies retained before the oldest are deleted.
QUARANTINE_KEEP = 3

#: Relevance weight per searchable field, highest-signal first.
FIELD_WEIGHTS: dict[str, int] = {
    "title": 10,
    "tags": 8,
    "summary": 5,
    "agent_notes": 3,
    "transcript": 2,
}

#: Fields that make up the ``search_index`` word list.
SHORTLIST_FIELDS = ("title", "tags", "summary", "agent_notes")

#: Fields a re-description must never blank out: an update that carries no
#: transcript, no tags or no agent association keeps the ones already stored.
PRESERVED_FIELDS = ("transcript", "summary", "agent_notes", "agent_type")


@dataclass
class SearchResult:
    """One hit: the video, its score, and which fields matched."""

    video: VideoMetadata
    score: int
    matched: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"video": self.video.to_dict(), "score": self.score, "matched": self.matched}


def _tokens(text: str) -> set[str]:
    """Lowercase word set, ignoring punctuation and single characters."""
    return {
        token
        for token in "".join(c if c.isalnum() else " " for c in text.lower()).split()
        if len(token) > 1
    }


@contextmanager
def _file_lock(path: Path, timeout: float = 30.0) -> Iterator[None]:
    """Hold an exclusive lock on ``path`` for the duration of the block.

    Advisory and OS-level (``msvcrt.locking`` / ``fcntl.flock``), so two
    ``aria-videos download`` processes serialise against each other rather than
    both writing. Falls back to an in-process lock when the filesystem refuses
    the syscall (some network and FAT mounts do).
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = os.open(path, os.O_RDWR | os.O_CREAT, 0o666)
    except OSError as exc:
        log.warning("index lock unavailable at %s: %s", path, exc)
        yield
        return

    acquired = False
    try:
        if os.name == "nt":
            import msvcrt

            deadline = _monotonic() + timeout
            while True:
                try:
                    handle and msvcrt.locking(handle, msvcrt.LK_NBLCK, 1)
                    acquired = True
                    break
                except OSError:
                    if _monotonic() > deadline:
                        break
                    _sleep(0.05)
        else:
            import fcntl

            deadline = _monotonic() + timeout
            while True:
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                    break
                except OSError:
                    if _monotonic() > deadline:
                        break
                    _sleep(0.05)
        if not acquired:
            log.warning("index lock at %s timed out after %ss", path, timeout)
        yield
    finally:
        try:
            if acquired:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle, fcntl.LOCK_UN)
        except OSError:  # pragma: no cover - unlocking a closed handle
            pass
        os.close(handle)


def _monotonic() -> float:
    import time

    return time.monotonic()


def _sleep(seconds: float) -> None:
    import time

    time.sleep(seconds)


class VideoIndexer:
    """Reads, updates and queries ``index.json``."""

    def __init__(self, storage: VideoLibraryStorage) -> None:
        self.storage = storage
        self.index_file = storage.index_file
        self.lock_file = self.index_file.with_name(LOCK_FILENAME)
        # RLock: `save` is called from inside the already-locked `add_video`.
        self._lock = threading.RLock()
        self._file_lock_depth = 0

    @contextmanager
    def _locked(self) -> Iterator[None]:
        """Serialise a read-modify-write, across threads *and* processes.

        The file lock is taken once per nesting level: `add_video` holds it and
        then calls `save`, and re-locking the same file from the same process
        would either deadlock (flock) or block (msvcrt).
        """
        with self._lock:
            outermost = self._file_lock_depth == 0
            if outermost:
                with _file_lock(self.lock_file):
                    self._file_lock_depth += 1
                    try:
                        yield
                    finally:
                        self._file_lock_depth -= 1
            else:
                self._file_lock_depth += 1
                try:
                    yield
                finally:
                    self._file_lock_depth -= 1

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def empty_index(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utcnow().isoformat(),
            "total_videos": 0,
            "total_storage": 0,
            "videos": [],
            "search_index": {},
        }

    def load(self, repair: bool = True) -> dict[str, Any]:
        """Load the index.

        Corruption and I/O failure are treated differently on purpose. A
        malformed file is quarantined and rebuilt, because nothing else will make
        the library usable again. An ``OSError`` is a flaky drive — a yanked
        stick, a share violation — and is re-raised: rewriting the index there
        would destroy transcripts and tags over a transient read failure.
        """
        if not self.index_file.exists():
            return self.empty_index()
        try:
            raw = self.index_file.read_text(encoding="utf-8")
        except OSError:
            log.exception("cannot read %s", self.index_file)
            raise

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            if not repair:
                raise
            log.error("%s is not valid JSON (%s); quarantining", self.index_file, exc)
            return self._quarantine_and_rebuild()

        if not isinstance(data, dict) or not isinstance(data.get("videos"), list):
            if not repair:
                raise IndexCorruptError(f"{self.index_file} is not an ARIA video index")
            log.error("%s has no 'videos' array; quarantining", self.index_file)
            return self._quarantine_and_rebuild()

        version = data.get("schema_version", SCHEMA_VERSION)
        try:
            newer = int(version) > SCHEMA_VERSION
        except (TypeError, ValueError):
            newer = False
        if newer:
            # Rewriting it here would strip the fields this build does not know
            # about, so refuse and leave the newer file untouched.
            raise IndexCorruptError(
                f"{self.index_file} was written by a newer library (schema {version} > "
                f"{SCHEMA_VERSION}); upgrade ARIA or point ARIA_USB_PATH elsewhere"
            )
        return self._normalize(data)

    def _normalize(self, data: dict[str, Any]) -> dict[str, Any]:
        """Fill in anything a hand-edited or older index is missing.

        Unknown keys are preserved: the round-trip through
        :class:`VideoMetadata` only supplies defaults for the fields this build
        knows about.
        """
        data.setdefault("schema_version", SCHEMA_VERSION)
        data.setdefault("updated_at", utcnow().isoformat())
        data.setdefault("search_index", {})
        entries: list[dict[str, Any]] = []
        for entry in data["videos"]:
            if not isinstance(entry, dict) or not entry.get("id"):
                continue
            known = VideoMetadata.from_dict(entry).to_dict()
            known.update({key: value for key, value in entry.items() if key not in known})
            entries.append(known)
        data["videos"] = entries
        data["total_videos"] = len(entries)
        data["total_storage"] = sum(int(entry.get("size_bytes") or 0) for entry in entries)
        return data

    def _quarantine_and_rebuild(self) -> dict[str, Any]:
        """Move the broken file into the cache and reconstruct from the stick."""
        stamp = utcnow().strftime("%Y%m%dT%H%M%S%f")
        broken = self.storage.cache_dir / f"index.json.corrupt-{stamp}"
        try:
            self.storage.cache_dir.mkdir(parents=True, exist_ok=True)
            os.replace(self.index_file, broken)
        except OSError as exc:
            log.error("could not quarantine %s: %s", self.index_file, exc)
        log.error("index quarantined at %s and rebuilt from the media on disk", broken)
        data = self.rebuild_from_disk()
        self.save(data)
        self._prune_quarantine()
        return data

    def _prune_quarantine(self) -> None:
        """Keep the newest ``QUARANTINE_KEEP`` copies; the rest go.

        Each copy is a full index, transcripts included, so leaving them all
        would fill the stick and block future downloads.
        """
        copies = sorted(self.storage.cache_dir.glob("index.json.corrupt-*"))
        for stale in copies[:-QUARANTINE_KEEP] if len(copies) > QUARANTINE_KEEP else []:
            try:
                stale.unlink()
                log.info("pruned old quarantine %s", stale.name)
            except OSError as exc:  # pragma: no cover - permission dependent
                log.warning("could not prune %s: %s", stale, exc)

    def save(self, index: dict[str, Any]) -> None:
        """Write the index atomically, keeping one backup of the last good copy."""
        with self._locked():
            index["updated_at"] = utcnow().isoformat()
            index["schema_version"] = SCHEMA_VERSION
            index["total_videos"] = len(index.get("videos", []))
            index["total_storage"] = sum(
                int(entry.get("size_bytes") or 0) for entry in index.get("videos", [])
            )
            index["search_index"] = self.build_search_index(index.get("videos", []))
            self.index_file.parent.mkdir(parents=True, exist_ok=True)
            if self.index_file.exists():
                try:
                    os.replace(self.index_file, self.index_file.with_name(BACKUP_FILENAME))
                except OSError as exc:  # pragma: no cover - permission dependent
                    log.warning("could not write the index backup: %s", exc)
            temp = self.index_file.with_suffix(".json.tmp")
            temp.write_text(
                json.dumps(index, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
            )
            os.replace(temp, self.index_file)

    def restore_backup(self) -> bool:
        """Put ``index.json.bak`` back after a quarantine, when there is one."""
        backup = self.index_file.with_name(BACKUP_FILENAME)
        if not backup.exists():
            return False
        os.replace(backup, self.index_file)
        log.warning("restored the index from %s", backup.name)
        return True

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_video(self, metadata: VideoMetadata) -> bool:
        """Insert or update one entry. Returns ``True`` when it was new.

        Re-adding an existing id refreshes it in place and keeps what the new
        description does not carry: a re-download without tags or an agent must
        not erase the tags and association an earlier call stored, because search
        weights tags eight times a transcript match.
        """
        with self._locked():
            index = self.load()
            videos: list[dict[str, Any]] = index["videos"]
            payload = metadata.to_dict()
            for position, existing in enumerate(videos):
                if existing.get("id") == metadata.id:
                    videos[position] = _merge_entry(existing, payload)
                    self.save(index)
                    return False
            videos.append(payload)
            self.save(index)
            return True

    def remove(self, video_id: str) -> bool:
        """Drop an entry from the index. The media file is left alone."""
        with self._locked():
            index = self.load()
            before = len(index["videos"])
            index["videos"] = [entry for entry in index["videos"] if entry.get("id") != video_id]
            if len(index["videos"]) == before:
                return False
            self.save(index)
            return True

    def rebuild_from_disk(self) -> dict[str, Any]:
        """Reconstruct entries for media files the index does not mention.

        Recovered entries carry the truth that survives without ffprobe (name,
        size, mtime) and say so, instead of inventing a duration or resolution.
        """
        index = self.empty_index()
        if self.index_file.exists():
            try:
                index = self.load(repair=False)
            except (IndexCorruptError, ValueError, json.JSONDecodeError, OSError):
                index = self.empty_index()
        known = {entry.get("id") for entry in index["videos"]}
        for path in sorted(self.storage.video_dir.glob("*")):
            if not path.is_file() or path.stem in known:
                continue
            if not self.storage.is_media(path):
                continue
            stat = path.stat()
            index["videos"].append(
                VideoMetadata(
                    id=path.stem,
                    title=path.stem,
                    # tz-aware: a naive local time would be relabelled as UTC by
                    # to_dict and shift the entry by the host's offset.
                    date_downloaded=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                    size_bytes=stat.st_size,
                    format=path.suffix.lstrip(".") or "mp4",
                    agent_notes="Recovered from disk; run a re-describe pass for full metadata.",
                ).to_dict()
            )
        self._normalize(index)
        return index

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def build_search_index(self, videos: Iterable[dict[str, Any]]) -> dict[str, list[str]]:
        """Word → video ids.

        Written for external consumers (a UI, a desktop search box) that want a
        candidate set without parsing the transcripts. This package's own
        :meth:`search` does not use it: a term that appears only inside a
        transcript has no entry here, so shortlisting on it would drop exactly
        the hits it is meant to help find.
        """
        index: dict[str, list[str]] = {}
        for video in videos:
            text = " ".join(
                str(video.get(field_name) or "")
                for field_name in SHORTLIST_FIELDS
                + tuple(str(tag) for tag in video.get("tags") or [])
            )
            for word in _tokens(text):
                index.setdefault(word, []).append(str(video.get("id", "")))
        return index

    def get(self, video_id: str) -> VideoMetadata | None:
        for entry in self.load()["videos"]:
            if entry.get("id") == video_id:
                return VideoMetadata.from_dict(entry)
        return None

    def list_videos(self, limit: int | None = None) -> list[VideoMetadata]:
        videos = [
            VideoMetadata.from_dict(entry)
            for entry in self.load()["videos"]
            if entry.get("id")
        ]
        videos.sort(key=lambda video: video.date_downloaded, reverse=True)
        return videos[:limit] if limit else videos

    def search(self, query: str, limit: int = 20) -> list[SearchResult]:
        """Rank videos by where the query matched: title beats transcript.

        A multi-word query requires every term to appear somewhere in the
        video, so "agent tools" does not return every video mentioning "tools".
        Stored ``relevance_score`` breaks ties, so agent feedback on one video
        actually changes where it lands.
        """
        terms = sorted(_tokens(query))
        if not terms:
            return []

        results: list[SearchResult] = []
        for entry in self.load()["videos"]:
            video = VideoMetadata.from_dict(entry)
            score, matched = _score(video, terms)
            if score > 0:
                results.append(SearchResult(video=video, score=score, matched=matched))

        results.sort(
            key=lambda result: (
                -result.score,
                -result.video.relevance_score,
                result.video.id,
            )
        )
        return results[:limit] if limit > 0 else results

    def stats(self) -> dict[str, Any]:
        index = self.load()
        tags: dict[str, int] = {}
        for entry in index["videos"]:
            for tag in entry.get("tags") or []:
                tags[str(tag)] = tags.get(str(tag), 0) + 1
        return {
            "total_videos": index.get("total_videos", 0),
            "total_storage": index.get("total_storage", 0),
            "total_duration": sum(
                int(entry.get("duration_seconds") or 0) for entry in index["videos"]
            ),
            "tagged": len([entry for entry in index["videos"] if entry.get("tags")]),
            "with_transcript": len(
                [entry for entry in index["videos"] if entry.get("transcript")]
            ),
            "tags": dict(sorted(tags.items(), key=lambda item: (-item[1], item[0]))),
            "index_file": str(self.index_file),
            "updated_at": index.get("updated_at"),
        }


def _merge_entry(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Overlay ``new`` on ``old`` without dropping what ``new`` does not know."""
    merged = dict(old)
    merged.update(new)
    for name in PRESERVED_FIELDS:
        if not new.get(name) and old.get(name):
            merged[name] = old[name]
    if new.get("tags") in (None, [], list(DEFAULT_TAGS)) and old.get("tags"):
        merged["tags"] = list(old["tags"])
    if not new.get("keyframes") and old.get("keyframes"):
        merged["keyframes"] = list(old["keyframes"])
    return merged


def _score(video: VideoMetadata, terms: list[str]) -> tuple[int, list[str]]:
    """Weighted score for a video, requiring every term to be present."""
    haystacks = {
        "title": (video.title, FIELD_WEIGHTS["title"]),
        "tags": (" ".join(video.tags), FIELD_WEIGHTS["tags"]),
        "summary": (video.summary, FIELD_WEIGHTS["summary"]),
        "agent_notes": (video.agent_notes, FIELD_WEIGHTS["agent_notes"]),
        "transcript": (video.transcript, FIELD_WEIGHTS["transcript"]),
    }
    lowered = {name: text.lower() for name, (text, _) in haystacks.items()}

    total = 0
    matched: list[str] = []
    for term in terms:
        term_score = 0
        for name, (_, weight) in haystacks.items():
            if term in lowered[name]:
                term_score = max(term_score, weight)
        if term_score == 0:
            return 0, []
        total += term_score
        matched.extend(name for name, text in lowered.items() if term in text)
    return total, sorted(set(matched))
