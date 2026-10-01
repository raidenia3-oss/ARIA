"""Bridge between the setup-pipeline ProgressEmitter and the Axum hub.

The setup pipeline already writes NDJSON progress frames to stderr via
``aria_autoconfig.progress.ProgressEmitter``. Those frames are invisible to
the React UI, which reads the Rust Axum hub on ``/api/control/progress``.

This module forwards every frame the emitter produces to
``POST /api/control/progress/push`` so the same hub that folds child-pipe
frames also folds in-process frames. The bridge is fire-and-forget: a
dropped connection or a refused request must never abort the setup run.

Nothing here is allowed to break a setup run. A closed pipe, a full disk or a
stream that raises on write is swallowed silently: progress is observability,
not a dependency of correctness.
"""

from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable, TextIO

from .progress import ProgressEmitter, ProgressEvent, default_progress_stream

#: Where the Axum hub lives. Overridable per-process for tests.
PROGRESS_HUB_URL = os.environ.get("ARIA_PROGRESS_HUB_URL", "http://127.0.0.1:8002/api/control/progress/push")

#: Bearer token for the hub; falls back to the env var the server reads.
PROGRESS_HUB_TOKEN = os.environ.get("ARIA_API_KEY", "")

#: How long a single POST may take before the bridge drops the frame.
_PUSH_TIMEOUT_S = 2.0


def _post_frame(payload: dict[str, Any]) -> bool:
    """POST one frame to the hub. Returns True on success, False on any error.

    Never raises: the bridge is observability, not correctness.
    """
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Content-Length": str(len(data)),
    }
    if PROGRESS_HUB_TOKEN:
        headers["Authorization"] = f"Bearer {PROGRESS_HUB_TOKEN}"
    req = urllib.request.Request(PROGRESS_HUB_URL, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=_PUSH_TIMEOUT_S) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return False


class HubForwardingEmitter(ProgressEmitter):
    """A ProgressEmitter that also pushes every frame to the Axum hub.

    Subclasses rather than monkey-patches ``_write`` so the inheritance chain
    stays honest and IDEs can still jump to the base implementation. The base
    still writes NDJSON to its stream; the hub push is additive.
    """

    def __init__(self, stream: TextIO | None = None, run_id: str | None = None,
                 hub_url: str | None = None, token: str | None = None) -> None:
        super().__init__(stream=stream, run_id=run_id)
        self._hub_url = hub_url or PROGRESS_HUB_URL
        self._token = token if token is not None else PROGRESS_HUB_TOKEN
        self._lock = threading.Lock()
        self._dropped = 0
        self._sent = 0

    def _write(self, event: ProgressEvent) -> None:  # type: ignore[override]
        # Always let the base write its NDJSON line first; the hub push is
        # observability and must not replace the stream the caller tails.
        super()._write(event)
        payload = event.to_dict()
        payload["run_id"] = self.run_id
        if not _post_frame(payload):
            with self._lock:
                self._dropped += 1
        else:
            with self._lock:
                self._sent += 1

    def stats(self) -> dict[str, int]:
        """Frames acknowledged by the hub vs frames it never saw."""
        with self._lock:
            return {"sent": self._sent, "dropped": self._dropped}

    def reset_stats(self) -> None:
        with self._lock:
            self._sent = 0
            self._dropped = 0


def make_emitter(stream: TextIO | None = None,
                 hub_url: str | None = None,
                 token: str | None = None) -> HubForwardingEmitter:
    """Convenience constructor used by the setup CLI and tests."""
    return HubForwardingEmitter(stream=stream or default_progress_stream(),
                                hub_url=hub_url, token=token)


def make_swarm_sink(hub_url: str | None = None,
                    token: str | None = None) -> Callable[..., None]:
    """Build a progress sink for ``AgentSwarmManager.set_progress_sink``.

    The swarm calls ``sink(event, run_id, index, total, name, tier, status,
    message)``. This adapter maps those positional args onto a
    :class:`ProgressEvent` and pushes it to the hub. The push is fire-and-
    forget: a refused hub is counted and swallowed, so a broken UI channel
    can never abort task execution.
    """
    from .progress import (
        ProgressEvent,
        EVENT_RUN_START, EVENT_STEP_START, EVENT_STEP_END, EVENT_RUN_END,
    )

    def _sink(event: str, run_id: str, index: int, total: int,
              name: str = "", tier: str = "",
              status: str = "", message: str = "") -> None:
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if event == EVENT_RUN_START:
            progress_event = ProgressEvent(event=EVENT_RUN_START, ts=ts, total=total, name=name or None)
        elif event == EVENT_STEP_START:
            progress_event = ProgressEvent(
                event=EVENT_STEP_START, ts=ts, index=index, total=total,
                name=name or None, tier=tier or None,
            )
        elif event == EVENT_STEP_END:
            progress_event = ProgressEvent(
                event=EVENT_STEP_END, ts=ts, index=index, total=total,
                name=name or None, tier=tier or None, status=status or None,
                message=message or None,
            )
        elif event == EVENT_RUN_END:
            progress_event = ProgressEvent(
                event=EVENT_RUN_END, ts=ts, steps_done=index, total=total,
                status=status or None,
            )
        else:
            return
        payload = progress_event.to_dict()
        payload["run_id"] = run_id
        _post_frame(payload)

    return _sink


__all__ = [
    "HubForwardingEmitter",
    "make_emitter",
    "make_swarm_sink",
    "PROGRESS_HUB_URL",
    "PROGRESS_HUB_TOKEN",
]