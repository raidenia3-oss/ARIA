"""Ingest curated video analyses into the library index.

Claude/Gemini produce a richer JSON than the library stores, with nested
RESUMEN objects, duration_approx strings and pipe-separated agent labels.
This module flattens that into VideoMetadata entries and indexes them, so an
analyst can ship a batch of references without re-typing the fields the
library already knows how to derive.

The source JSON is also copied to videos/analysis/ so the original analysis
is preserved next to the media it describes.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .errors import LibraryError
from .indexer import VideoIndexer
from .models import VideoMetadata
from .storage import VideoLibraryStorage

#: Subdirectory under the library root holding the original analysis files.
ANALYSIS_SUBDIR = "analysis"


def _duration_seconds(raw: Any) -> int:
    """Coerce a duration into an integer number of seconds.

    Claude writes "0:32" or "1:04:21"; the library stores an int. A missing or
    unusable value is treated as unknown, not as 0.
    """
    if isinstance(raw, (int, float)):
        return int(raw)
    text = str(raw).strip()
    if not text:
        return 0
    parts = text.split(":")
    try:
        pieces = [int(p) for p in parts]
    except ValueError:
        return 0
    if len(pieces) == 1:
        return pieces[0]
    if len(pieces) == 2:
        return pieces[0] * 60 + pieces[1]
    return pieces[0] * 3600 + pieces[1] * 60 + pieces[2]


def _flatten_summary(resumen: dict[str, Any], fallback: str = "") -> str:
    """Join the nested RESUMEN object into one searchable string."""
    pieces: list[str] = []
    for key in ("one_liner", "key_insight", "main_topic"):
        value = resumen.get(key) if isinstance(resumen, dict) else None
        if value:
            pieces.append(str(value))
    if isinstance(resumen, dict):
        subtopics = resumen.get("subtopics")
        if isinstance(subtopics, list):
            pieces.append("; ".join(str(item) for item in subtopics))
    text = " ".join(pieces).strip()
    return text or fallback


def _agent_type(raw: Any) -> str | None:
    """Take the first label from a pipe-separated agent_type field."""
    if not raw:
        return None
    text = str(raw).split("|")[0].strip()
    return text or None


def _agent_notes(video: dict[str, Any], resumen: dict[str, Any]) -> str:
    """Bundle the action items, use case and external references into notes."""
    aplicable = video.get("APLICABLE PARA ARIA AGENTS") or {}
    if not isinstance(aplicable, dict):
        aplicable = {}
    pieces: list[str] = []
    use_case = aplicable.get("specific_use_case")
    if use_case:
        pieces.append(str(use_case))
    action_items = aplicable.get("action_items")
    if isinstance(action_items, list):
        pieces.append("Acciones: " + "; ".join(str(item) for item in action_items))
    refs = video.get("REFERENCIAS EXTERNAS") or video.get("external_references") or []
    if isinstance(refs, list) and refs:
        pieces.append("Referencias: " + ", ".join(str(item) for item in refs))
    reasons = (video.get("RELEVANCIA") or {}).get("reasons") if isinstance(video.get("RELEVANCIA"), dict) else None
    if isinstance(reasons, list) and reasons:
        pieces.append("Motivos: " + " ".join(str(item) for item in reasons))
    return " ".join(pieces).strip()


def convert_video(raw: dict[str, Any]) -> VideoMetadata:
    """Map one Claude/Gemini analysis entry onto a VideoMetadata."""
    resumen = raw.get("RESUMEN") or {}
    if not isinstance(resumen, dict):
        resumen = {}
    summary = _flatten_summary(resumen, raw.get("summary") or "")
    relevancia = raw.get("RELEVANCIA") if isinstance(raw.get("RELEVANCIA"), dict) else {}
    return VideoMetadata(
        id=str(raw.get("video_id") or raw.get("id") or "").strip(),
        source_url=str(raw.get("source_url") or "").strip(),
        title=str(raw.get("title") or "Unknown").strip(),
        duration_seconds=_duration_seconds(raw.get("duration_seconds", raw.get("duration_approx"))),
        summary=summary,
        tags=list(raw.get("TAGS") or raw.get("tags") or []),
        agent_type=_agent_type(
            (raw.get("APLICABLE PARA ARIA AGENTS") or {}).get("agent_type", raw.get("agent_type"))
        ),
        agent_notes=_agent_notes(raw, resumen),
        relevance_score=float(relevancia.get("score", raw.get("relevance_score", 0.85))),
    )


def convert_batch(data: dict[str, Any]) -> list[VideoMetadata]:
    """Convert every video in an analysis document."""
    videos = data.get("videos") or []
    return [convert_video(entry) for entry in videos if isinstance(entry, dict)]


def analysis_path(storage: VideoLibraryStorage, stamp: str) -> Path:
    """Where the original analysis JSON is copied for preservation.

    The storage root already points at the library root (``<usb>/``), and the
    analysis files live under ``videos/analysis/`` next to the cache.
    """
    return storage.root / "videos" / ANALYSIS_SUBDIR / f"{stamp}.json"


def ingest(
    source,
    storage=None,
    indexer=None,
    stamp=None,
):
    """Convert an analysis file and index every video in it.

    Returns a report with how many videos were new, how many refreshed an
    existing entry, and where the original analysis was preserved.
    """
    path = Path(source)
    if not path.exists():
        raise LibraryError(f"analysis file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("videos"), list):
        raise LibraryError(f"{path} has no videos array")

    storage = storage or VideoLibraryStorage()
    indexer = indexer or VideoIndexer(storage)
    stamp = stamp or datetime.now().strftime("%Y%m%dT%H%M%S")

    analysis_dest = analysis_path(storage, stamp)
    analysis_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, analysis_dest)

    new = 0
    refreshed = 0
    for metadata in convert_batch(data):
        added = indexer.add_video(metadata)
        new += 1 if added else 0
        refreshed += 0 if added else 1

    return {
        "source": str(path),
        "preserved_as": str(analysis_dest),
        "total": len(data["videos"]),
        "new": new,
        "refreshed": refreshed,
        "analysis_date": data.get("analysis_date"),
        "source_platform": data.get("source"),
    }
