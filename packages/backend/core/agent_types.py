# -*- coding: utf-8 -*-
"""Agent lifecycle types for AURA OS.

Centralises the states an agent can be in and the transitions between them.
The swarm used bare strings ("idle", "busy", "error") before this module;
this replaces them with a typed enum so the APEX dashboard and any future
status API can pattern-match instead of guessing.

Stalled / offline are *derived* states: the lifecycle manager decides them
from heartbeat age and busy duration, they are never set directly by callers.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class AgentStatus(str, Enum):
    """Every state an agent can be in, in order of typical lifecycle."""

    IDLE = "idle"
    # The Rust daemon reports `online` for a roster entry it is tracking.
    # Without this member the value silently coerced to IDLE, so the same
    # agent read two different ways by the API and the dashboard.
    ONLINE = "online"
    BUSY = "busy"
    ERROR = "error"
    STALLED = "stalled"
    OFFLINE = "offline"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


# Thresholds used by the lifecycle manager to derive stalled / offline.
# BUSY_STALL_SECONDS is about busy DURATION; HEARTBEAT_OFFLINE_SECONDS is about
# how long since the agent was last SEEN. The Rust side derives its `stale`
# flag from heartbeat age, so it must use the heartbeat threshold (300), not the
# busy one, or the two disagree for ~3 minutes on the same agent.
BUSY_STALL_SECONDS = 120.0
HEARTBEAT_OFFLINE_SECONDS = 300.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


class AgentLifecycle:
    """Tracks one agent's state transitions and derives stalled/offline.

    The swarm stores its own dict per agent; this class is the *typed* view
    used by the status API and the APEX dashboard. It is intentionally
    stateless between calls: every method recomputes from the timestamps
    the swarm already stores, so there is no separate clock to drift.
    """

    def __init__(
        self,
        agent_id: str,
        role: str = "",
        status: str = "idle",
        current_task: Optional[str] = None,
        task_started_at: Optional[str] = None,
        last_heartbeat: Optional[str] = None,
        last_error: Optional[str] = None,
        errors: int = 0,
    ) -> None:
        self.agent_id = agent_id
        self.role = role
        self._status = AgentStatus(status) if status in [s.value for s in AgentStatus] else AgentStatus.IDLE
        self.current_task = current_task
        self.task_started_at = task_started_at
        self.last_heartbeat = last_heartbeat
        self.last_error = last_error
        self.errors = errors

    # -- transitions ---------------------------------------------------- #

    def set_task_started(self, task_id: str) -> None:
        """Mark the agent as busy on ``task_id`` and record the start time."""
        self._status = AgentStatus.BUSY
        self.current_task = task_id
        self.task_started_at = _now_iso()

    def set_task_completed(self) -> None:
        """Return the agent to idle after a successful task."""
        self._status = AgentStatus.IDLE
        self.current_task = None
        self.task_started_at = None

    def set_task_failed(self, error: str) -> None:
        """Mark the agent as error after a failed task; keep the task id."""
        self._status = AgentStatus.ERROR
        self.last_error = error
        self.errors += 1

    def touch(self) -> None:
        """Refresh the heartbeat; an offline agent that comes back is idle."""
        self.last_heartbeat = _now_iso()
        if self._status == AgentStatus.OFFLINE:
            self._status = AgentStatus.IDLE

    # -- derived states ------------------------------------------------- #

    def derived_status(self, now: Optional[datetime] = None) -> AgentStatus:
        """Return the *effective* status, deriving stalled / offline.

        An agent that has not been seen recently is offline regardless of
        what its last recorded status was. A busy agent that has been busy
        longer than the stall threshold is stalled, not busy.
        """
        if self._status == AgentStatus.OFFLINE:
            return AgentStatus.OFFLINE

        hb = _parse_iso(self.last_heartbeat)
        if hb is not None:
            age = (now or datetime.now(timezone.utc)) - hb
            if age.total_seconds() >= HEARTBEAT_OFFLINE_SECONDS:
                return AgentStatus.OFFLINE

        if self._status == AgentStatus.BUSY and self.task_started_at:
            started = _parse_iso(self.task_started_at)
            if started is not None:
                busy_for = (now or datetime.now(timezone.utc)) - started
                if busy_for.total_seconds() >= BUSY_STALL_SECONDS:
                    return AgentStatus.STALLED

        return self._status

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "status": self.derived_status().value,
            "status_enum": self.derived_status().name,
            "current_task": self.current_task,
            "task_started_at": self.task_started_at,
            "last_heartbeat": self.last_heartbeat,
            "last_error": self.last_error,
            "errors": self.errors,
            "busy_stall_seconds": BUSY_STALL_SECONDS,
            "heartbeat_offline_seconds": HEARTBEAT_OFFLINE_SECONDS,
        }


def status_from_string(value: Any, default: AgentStatus = AgentStatus.IDLE) -> AgentStatus:
    """Best-effort coercion of a stored status string into the enum."""
    if isinstance(value, AgentStatus):
        return value
    if isinstance(value, str):
        for member in AgentStatus:
            if member.value == value.lower():
                return member
    return default


def is_terminal(status: AgentStatus) -> bool:
    """True for states that block further work until a human touches the agent."""
    return status in (AgentStatus.STALLED, AgentStatus.OFFLINE)