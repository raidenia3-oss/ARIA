"""Machine-readable progress stream for the setup pipeline.

The Reporter paints for humans and only speaks once a step has finished. The
backend and the UI need to know that a run is in flight, which step is
current, and how far along it is. This module emits one JSON object per line
(NDJSON) so any consumer can tail the stream without a parser that has to
understand the terminal output.

Every line carries ``aria_progress: true`` so a consumer can drop it into a
mixed stream of ordinary subprocess output and pick out the frames it cares
about.

Nothing here is allowed to break a setup run. A closed pipe, a full disk or a
stream that raises on write is swallowed silently: progress is observability,
not a dependency of correctness.
"""

from __future__ import annotations

import json
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, TextIO

from .model import Status, Tier

#: A whole setup run has started; ``total`` is the number of planned steps.
EVENT_RUN_START = "run_start"
#: A step has begun executing; no outcome is known yet.
EVENT_STEP_START = "step_start"
#: A step has finished; ``status`` and ``message`` are final for that step.
EVENT_STEP_END = "step_end"
#: The run is over; ``steps_done`` carries how many steps actually executed.
EVENT_RUN_END = "run_end"

#: Discriminator present on every frame so a mixed stream can be filtered.
MARKER_FIELD = "aria_progress"

#: Step-level status vocabulary: short, lowercase, stable across releases.
#: ``FAILED`` becomes "fail" and ``SKIPPED`` becomes "skip" to match the
#: terminal marks the Reporter already prints (FAIL / SKIP).
_STATUS_SHORT: dict[Status, str] = {
    Status.OK: "ok",
    Status.WARN: "warn",
    Status.FAILED: "fail",
    Status.SKIPPED: "skip",
    Status.RUNNING: "running",
    Status.PENDING: "pending",
    Status.ROLLED_BACK: "rolled_back",
}


def _now() -> str:
    """RFC3339 UTC timestamp with a ``Z`` suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def status_str(status: Any) -> str:
    """Short lowercase label for a ``Status``.

    Accepts a ``Status`` member or a plain string, so a caller that already
    holds the ``.value`` does not need to know which one it has.
    """
    if isinstance(status, Status):
        return _STATUS_SHORT.get(status, str(status.value).lower())
    if isinstance(status, str):
        return status.strip().lower()
    return str(status).strip().lower()


def tier_str(tier: Any) -> str:
    """Short lowercase label for a ``Tier`` (core / runtime / optional)."""
    if isinstance(tier, Tier):
        return str(tier.value).lower()
    if isinstance(tier, str):
        return tier.strip().lower()
    return str(tier).strip().lower()


@dataclass
class ProgressEvent:
    """One NDJSON frame.

    Every field except ``event`` and ``ts`` is optional and omitted from
    :meth:`to_dict` when unset, so a frame only carries what applies to its
    own event type.
    """

    event: str
    ts: str
    name: str | None = None
    tier: str | None = None
    #: 0-based POSITION of a step within the run. Emitted ONLY on
    #: ``step_start`` and ``step_end``; absent on ``run_start`` and
    #: ``run_end``. It is never a step count - the run-level count lives in
    #: ``steps_done``, so a consumer must not read one meaning as the other.
    index: int | None = None
    total: int | None = None
    #: Number of steps that executed. Emitted ONLY on ``run_end``.
    steps_done: int | None = None
    status: str | None = None
    message: str | None = None
    elapsed_s: float | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            MARKER_FIELD: True,
            "event": self.event,
            "ts": self.ts,
        }
        for key in (
            "name",
            "tier",
            "index",
            "total",
            "steps_done",
            "status",
            "message",
            "elapsed_s",
        ):
            value = getattr(self, key)
            if value is not None:
                payload[key] = value
        return payload


class ProgressEmitter:
    """Writes progress frames as NDJSON.

    ``stream`` defaults to :func:`default_progress_stream` (stderr). All frames
    of one emitter share a ``run_id`` so a consumer can tell two interleaved
    runs apart.
    """

    def __init__(self, stream: TextIO | None = None, run_id: str | None = None) -> None:
        self.stream = stream if stream is not None else default_progress_stream()
        self.run_id = run_id or uuid.uuid4().hex[:12]

    # ------------------------------------------------------------------ events

    def run_start(self, total: int) -> None:
        self._write(ProgressEvent(event=EVENT_RUN_START, ts=_now(), total=total))

    def step_start(self, index: int, total: int, name: str, tier: str) -> None:
        self._write(
            ProgressEvent(
                event=EVENT_STEP_START,
                ts=_now(),
                index=index,
                total=total,
                name=name,
                tier=tier,
                status=status_str(Status.RUNNING),
            )
        )

    def step_end(
        self,
        index: int,
        total: int,
        name: str,
        tier: str,
        status: str,
        message: str = "",
        elapsed_s: float | None = None,
    ) -> None:
        self._write(
            ProgressEvent(
                event=EVENT_STEP_END,
                ts=_now(),
                index=index,
                total=total,
                name=name,
                tier=tier,
                status=status_str(status),
                message=message,
                elapsed_s=elapsed_s,
            )
        )

    def run_end(
        self,
        status: str,
        steps_done: int,
        total: int,
        elapsed_s: float | None = None,
    ) -> None:
        # ``index`` is the 0-based position of a step, so a run-level frame has
        # no position to report and must leave it unset. The count goes into its
        # own ``steps_done`` field; reusing ``index`` here would give one JSON
        # key two incompatible meanings across frame types.
        self._write(
            ProgressEvent(
                event=EVENT_RUN_END,
                ts=_now(),
                steps_done=steps_done,
                total=total,
                status=status_str(status),
                elapsed_s=elapsed_s,
            )
        )

    # ------------------------------------------------------------------- write

    def _write(self, event: ProgressEvent) -> None:
        try:
            payload = event.to_dict()
            payload["run_id"] = self.run_id
            # Compact separators keep a frame on one line; ensure_ascii=False
            # keeps human-readable text intact. json.dumps escapes embedded
            # newlines, so a step name can never corrupt NDJSON framing.
            line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            self.stream.write(line + "\n")
            # The consumer tails this pipe live; without the flush it would
            # only see a frame when the buffer happened to fill.
            self.stream.flush()
        except Exception:  # noqa: BLE001 - a broken progress pipe must never abort setup
            return


def default_progress_stream() -> TextIO:
    """The stream progress goes to when the caller does not pick one.

    stderr, deliberately, and not stdout: ``--json`` already owns stdout and
    must stay a clean, machine-parseable report. Routing frames to stderr keeps
    ``aria_setup.py --progress --json > report.json 2> progress.ndjson`` honest
    and still leaves the painted report visible on a terminal.
    """
    return sys.stderr
