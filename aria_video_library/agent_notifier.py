"""Telling autonomous agents that a reference video exists.

Two destinations, one notification: a Discord message for a human watching
``#aria-improvements``, and a row in ``agents_video_references`` inside
``aura.db`` for an agent to read on its next cycle. Either can fail without
losing the other, because a Discord outage must not mean the agents never hear
about the video.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from .models import AgentNotification, VideoMetadata, utcnow

log = logging.getLogger("aria.video-library")

#: Webhook env vars, in priority order. The first non-empty one wins.
WEBHOOK_ENVS = ("ARIA_VIDEO_WEBHOOK", "DISCORD_WEBHOOK_URL", "DISCORD_WEBHOOK")
#: Overrides the database holding agent notifications.
DB_PATH_ENV = "ARIA_DB_PATH"

#: Discord rejects messages above 2000 characters; 1990 leaves room for the
#: truncation marker.
DISCORD_CONTENT_LIMIT = 2000
TRUNCATION_MARKER = "… *(truncated)*"

#: How long a write may wait for a busy shared database before it is reported
#: as lost, and the pause between attempts.
NOTIFY_BUSY_TIMEOUT_SECS = 10.0
NOTIFY_RETRY_SECS = 0.2
#: Notifications older than this are pruned; the table has no other cleanup.
NOTIFY_RETENTION_DAYS = 30

TABLE = "agents_video_references"

_CREATE_TABLE = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    video_id TEXT NOT NULL,
    context TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    read INTEGER NOT NULL DEFAULT 0
)
"""
_CREATE_INDEX = (
    f"CREATE INDEX IF NOT EXISTS idx_{TABLE}_agent ON {TABLE} (agent_id, read)"
)


def default_db_path() -> Path:
    """Where notifications are stored when the caller names no database."""
    from_env = os.getenv(DB_PATH_ENV, "").strip()
    if from_env:
        return Path(from_env).expanduser()
    return Path(__file__).resolve().parent.parent / "data" / "aura.db"


def resolve_webhook(explicit: str | None = None) -> str:
    """First configured Discord webhook, or an empty string."""
    if explicit:
        return explicit
    for name in WEBHOOK_ENVS:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def build_message(agent_id: str, video: VideoMetadata) -> str:
    """The Discord body: what the video is, and why this agent should care."""
    lines = [
        "📹 **Video Reference Added**",
        "",
        f"**Title:** {video.title}",
        f"**Duration:** {video.duration_display}",
        f"**Source:** {video.source_url or 'unknown'}",
        f"**Tags:** {', '.join(video.tags) if video.tags else 'reference'}",
        "",
        "**Summary:**",
        video.short_summary() or "(no transcript available yet)",
        "",
        f"**Relevant for:** {agent_id}",
        f"**Notes:** {video.agent_notes}",
        "",
        f"Stored as `{video.id}` — search it with `aria-videos search \"{video.title[:40]}\"`.",
    ]
    return "\n".join(lines)


def truncate_message(message: str, limit: int = DISCORD_CONTENT_LIMIT) -> str:
    """Cut an over-long message on a line boundary where possible."""
    if len(message) <= limit:
        return message
    room = limit - len(TRUNCATION_MARKER)
    cut = message[:room]
    newline = cut.rfind("\n")
    if newline > room // 2:
        cut = cut[:newline]
    return cut.rstrip() + TRUNCATION_MARKER


@dataclass
class NotificationOutcome:
    """What actually happened, so callers can report failures honestly."""

    notification: AgentNotification
    message: str
    delivered: bool = False
    stored: bool = False
    detail: str = ""


def _post_json(url: str, payload: dict[str, Any], timeout: int = 10) -> int:
    """POST JSON with stdlib only. Returns the HTTP status."""
    data = json.dumps(payload).encode()
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return int(response.status)


class AgentNotifier:
    """Sends a video to Discord and records it for the agents to read."""

    def __init__(
        self,
        webhook: str | None = None,
        db_path: str | os.PathLike[str] | None = None,
        post: Callable[[str, dict[str, Any], int], int] | None = None,
        timestamp: Callable[[], datetime] = utcnow,
    ) -> None:
        # The webhook URL is a credential: it is never logged, only used.
        self.webhook = resolve_webhook(webhook)
        self.db_path = Path(db_path).expanduser() if db_path else default_db_path()
        self._post = post or _post_json
        self._now = timestamp

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def notify_agent(
        self,
        agent_id: str,
        video: VideoMetadata,
        context: str = "",
    ) -> NotificationOutcome:
        """Announce one video to one agent.

        ``context`` explains *why this agent* is being told, which is the part
        the generic message cannot know; it is stored with the notification.
        """
        if not agent_id:
            raise ValueError("agent_id is required to notify an agent")

        message = build_message(agent_id, video)
        notification = AgentNotification(
            agent_id=agent_id,
            video_id=video.id,
            context=context or video.agent_notes,
            timestamp=self._now(),
        )
        outcome = NotificationOutcome(
            notification=notification,
            message=message,
            detail="no Discord webhook configured" if not self.webhook else "",
        )
        outcome.delivered = self._send_discord(message)
        outcome.stored = self._store(notification, message)
        if not outcome.stored:
            outcome.detail = (outcome.detail + "; " if outcome.detail else "") + (
                f"could not write {self.db_path}"
            )
        return outcome

    def _send_discord(self, message: str) -> bool:
        """POST to the webhook. ``False`` means "not delivered", never "fine"."""
        if not self.webhook:
            return False
        payload = {
            "content": truncate_message(message),
            "username": "ARIA Video Library",
        }
        try:
            status = self._post(self.webhook, payload, 10)
        except urllib.error.HTTPError as exc:
            log.warning("Discord webhook rejected the notification: HTTP %s", exc.code)
            return False
        except (urllib.error.URLError, OSError) as exc:
            log.warning("Discord webhook unreachable: %s", exc)
            return False
        # Discord answers 204 on success; anything else is not a delivery.
        return 200 <= status < 300

    # ------------------------------------------------------------------
    # SQLite side
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # WAL lets the USB agent read while a dispatched download writes, which
        # is the normal case now that several processes share this database.
        connection = sqlite3.connect(self.db_path, timeout=NOTIFY_BUSY_TIMEOUT_SECS)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA journal_mode = WAL")
        except sqlite3.Error as exc:  # pragma: no cover - filesystem dependent
            log.debug("WAL unavailable for %s: %s", self.db_path, exc)
        return connection

    def _store(self, notification: AgentNotification, message: str) -> bool:
        """Insert one notification, retrying while the shared database is busy.

        `aura.db` is written by the agent, by every CLI invocation and by each
        dispatched download. Dropping the row because another process held the
        write lock would leave the agent silently unaware of a video, so the
        insert is retried before it is reported as failed.
        """
        deadline = _monotonic() + NOTIFY_BUSY_TIMEOUT_SECS
        while True:
            try:
                with self._connect() as connection:
                    connection.execute(_CREATE_TABLE)
                    connection.execute(_CREATE_INDEX)
                    connection.execute(
                        f"INSERT INTO {TABLE} "
                        "(agent_id, video_id, context, message, created_at, read) "
                        "VALUES (?, ?, ?, ?, ?, 0)",
                        (
                            notification.agent_id,
                            notification.video_id,
                            notification.context,
                            message,
                            notification.timestamp.isoformat(),
                        ),
                    )
                return True
            except sqlite3.OperationalError as exc:
                if "lock" not in str(exc).lower() or _monotonic() > deadline:
                    log.warning("could not store video notification: %s", exc)
                    return False
                _sleep(NOTIFY_RETRY_SECS)
            except sqlite3.Error as exc:
                log.warning("could not store video notification: %s", exc)
                return False

    def pending(self, agent_id: str | None = None, limit: int = 20) -> list[AgentNotification]:
        """Unread notifications, newest first, optionally for one agent."""
        with self._connect() as connection:
            connection.execute(_CREATE_TABLE)
            if agent_id:
                cursor = connection.execute(
                    f"SELECT * FROM {TABLE} WHERE agent_id = ? AND read = 0 "
                    "ORDER BY id DESC LIMIT ?",
                    (agent_id, int(limit)),
                )
            else:
                cursor = connection.execute(
                    f"SELECT * FROM {TABLE} WHERE read = 0 ORDER BY id DESC LIMIT ?",
                    (int(limit),),
                )
            return [
                AgentNotification(
                    agent_id=row["agent_id"],
                    video_id=row["video_id"],
                    context=row["context"],
                    timestamp=datetime.fromisoformat(row["created_at"]),
                    read=bool(row["read"]),
                )
                for row in cursor.fetchall()
            ]

    def message_for(self, video_id: str) -> str | None:
        """The stored Discord text for a video, for an agent that wants detail."""
        with self._connect() as connection:
            connection.execute(_CREATE_TABLE)
            row = connection.execute(
                f"SELECT message FROM {TABLE} WHERE video_id = ? ORDER BY id DESC LIMIT 1",
                (video_id,),
            ).fetchone()
        return row["message"] if row else None

    def mark_read(self, agent_id: str, video_id: str) -> int:
        """Acknowledge notifications; returns how many rows were updated."""
        with self._connect() as connection:
            connection.execute(_CREATE_TABLE)
            cursor = connection.execute(
                f"UPDATE {TABLE} SET read = 1 WHERE agent_id = ? AND video_id = ? AND read = 0",
                (agent_id, video_id),
            )
            return int(cursor.rowcount or 0)

    def prune(self, retention_days: int = NOTIFY_RETENTION_DAYS) -> int:
        """Drop rows older than the retention window; returns rows deleted.

        `mark_read` only flips a flag, so without this the table grows for the
        life of the autonomous process — one row per video per agent, each
        holding the full announcement text.
        """
        cutoff = (utcnow() - timedelta(days=max(0, int(retention_days)))).isoformat()
        with self._connect() as connection:
            connection.execute(_CREATE_TABLE)
            cursor = connection.execute(f"DELETE FROM {TABLE} WHERE created_at < ?", (cutoff,))
            deleted = int(cursor.rowcount or 0)
        if deleted:
            log.info("pruned %d video notifications older than %s", deleted, retention_days)
        return deleted


def _monotonic() -> float:
    import time

    return time.monotonic()


def _sleep(seconds: float) -> None:
    import time

    time.sleep(seconds)
