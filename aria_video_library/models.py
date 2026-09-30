"""Dataclasses describing a video reference and the agent notifications about it.

These are the objects that get persisted into ``videos/index.json`` on the USB
stick, so the serialised shape is a contract: fields are only ever added, never
renamed or repurposed. [`VideoMetadata.from_dict`] tolerates missing and unknown
keys so an index written by an older or newer build still loads.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

#: Tags applied when the caller supplies none.
DEFAULT_TAGS: list[str] = ["reference"]

#: Relevance assigned to a freshly downloaded video with no agent scoring yet.
DEFAULT_RELEVANCE = 0.85


def utcnow() -> datetime:
    """Timezone-aware current time, used as the default download stamp."""
    return datetime.now(timezone.utc)


def _isoformat(value: datetime) -> str:
    """Render a datetime as ISO-8601, normalising naive values to UTC.

    Naive timestamps are assumed to be UTC rather than rejected: a hand-edited
    or older index may contain them, and dropping the entry would lose the video.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _parse_datetime(value: Any) -> datetime:
    """Best-effort timestamp parse, falling back to now for unusable input."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return utcnow()


@dataclass
class VideoMetadata:
    """One downloaded video plus everything an agent needs to judge relevance."""

    #: Stable id, also the filename stem: ``instagram_ai-tools_20260930``.
    id: str
    source_url: str = ""
    title: str = "Unknown"
    date_downloaded: datetime = field(default_factory=utcnow)
    duration_seconds: int = 0
    size_bytes: int = 0
    format: str = "mp4"
    resolution: str = "unknown"
    fps: float = 0.0

    # Content
    transcript: str = ""
    summary: str = ""
    keyframes: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=lambda: list(DEFAULT_TAGS))

    # For agents
    agent_type: str | None = None
    agent_notes: str = ""
    relevance_score: float = DEFAULT_RELEVANCE

    #: Absolute path of the media file on the machine that wrote the entry.
    #: Informational: the library is meant to be read from a USB stick that is
    #: mounted somewhere else, so consumers resolve paths through
    #: ``VideoLibraryStorage`` rather than trusting this string.
    file_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "date_downloaded": _isoformat(self.date_downloaded)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VideoMetadata":
        """Rebuild an entry from ``index.json``, ignoring unknown keys."""
        known = {f for f in cls.__dataclass_fields__}
        payload = {key: value for key, value in data.items() if key in known}
        payload.setdefault("id", "")
        payload["date_downloaded"] = _parse_datetime(payload.get("date_downloaded"))
        for list_field in ("tags", "keyframes"):
            if not isinstance(payload.get(list_field), list):
                payload.pop(list_field, None)
        return cls(**payload)

    @property
    def duration_display(self) -> str:
        """``m:ss`` (or ``h:mm:ss``) rendering for terminals and notifications."""
        total = max(0, int(self.duration_seconds))
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    def short_summary(self, limit: int = 240) -> str:
        """Summary trimmed to ``limit`` characters on a word boundary."""
        text = " ".join(self.summary.split())
        if len(text) <= limit:
            return text
        cut = text[:limit].rsplit(" ", 1)[0]
        return f"{cut}…"


@dataclass
class AgentNotification:
    """A pending "this video exists and here is why it matters" message."""

    agent_id: str
    video_id: str
    context: str
    timestamp: datetime = field(default_factory=utcnow)
    read: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "timestamp": _isoformat(self.timestamp)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentNotification":
        return cls(
            agent_id=str(data.get("agent_id", "")),
            video_id=str(data.get("video_id", "")),
            context=str(data.get("context", "")),
            timestamp=_parse_datetime(data.get("timestamp")),
            read=bool(data.get("read", False)),
        )
