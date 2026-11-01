from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aria_autoconfig import (  # noqa: E402
    EnvironmentDetector,
    Orchestrator,
    Reporter,
    Status,
    Tier,
)
from aria_autoconfig.progress import (  # noqa: E402
    EVENT_RUN_END,
    EVENT_RUN_START,
    EVENT_STEP_END,
    EVENT_STEP_START,
    ProgressEmitter,
    ProgressEvent,
    default_progress_stream,
    status_str,
    tier_str,
)


def _emitter():
    """An emitter writing to an in-memory stream, plus that stream."""
    stream = io.StringIO()
    return ProgressEmitter(stream=stream), stream


def _frames(stream):
    return [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]


def _full_run(emitter, total=2):
    """A minimal but complete run: start, two steps, end."""
    emitter.run_start(total=total)
    for index in range(total):
        emitter.step_start(index=index, total=total, name=f"step_{index}", tier="core")
        emitter.step_end(
            index=index,
            total=total,
            name=f"step_{index}",
            tier="core",
            status=status_str(Status.OK),
            message="done",
            elapsed_s=0.5,
        )
    emitter.run_end(status="ok", steps_done=total, total=total, elapsed_s=1.0)


class _BrokenStream:
    """A stream that is gone, like a closed pipe."""

    def write(self, _text):
        raise ValueError("closed")

    def flush(self):
        raise ValueError("closed")


# --------------------------------------------------------------------- framing


def test_every_line_is_one_json_object():
    emitter, stream = _emitter()
    _full_run(emitter)
    lines = stream.getvalue().splitlines()
    assert len(lines) == 6  # run_start + 2 * (step_start, step_end) + run_end
    for line in lines:
        assert isinstance(json.loads(line), dict)


def test_every_frame_is_marked_and_correctly_typed():
    emitter, stream = _emitter()
    _full_run(emitter)
    expected = [
        EVENT_RUN_START,
        EVENT_STEP_START,
        EVENT_STEP_END,
        EVENT_STEP_START,
        EVENT_STEP_END,
        EVENT_RUN_END,
    ]
    frames = _frames(stream)
    assert [f["event"] for f in frames] == expected
    for frame in frames:
        assert frame["aria_progress"] is True
        assert frame["ts"].endswith("Z")
        assert frame["run_id"] == emitter.run_id


def test_step_end_carries_identity_and_outcome():
    emitter, stream = _emitter()
    emitter.step_end(
        index=3,
        total=7,
        name="install_core",
        tier="core",
        status=Status.FAILED,
        message="boom",
        elapsed_s=1.25,
    )
    frame = _frames(stream)[0]
    assert frame["event"] == EVENT_STEP_END
    assert frame["status"] == "fail"
    assert frame["index"] == 3
    assert frame["total"] == 7
    assert frame["name"] == "install_core"
    assert frame["tier"] == "core"
    assert frame["message"] == "boom"
    assert frame["elapsed_s"] == 1.25


def test_to_dict_omits_unset_optional_fields():
    payload = ProgressEvent(event=EVENT_RUN_START, ts="2026-09-30T00:00:00Z").to_dict()
    assert payload == {
        "aria_progress": True,
        "event": "run_start",
        "ts": "2026-09-30T00:00:00Z",
    }


def test_frames_are_in_order_with_sequential_indices():
    emitter, stream = _emitter()
    _full_run(emitter)
    frames = _frames(stream)
    assert frames[0]["event"] == EVENT_RUN_START
    assert frames[-1]["event"] == EVENT_RUN_END
    assert [f["index"] for f in frames if f["event"] == EVENT_STEP_START] == [0, 1]
    assert [f["index"] for f in frames if f["event"] == EVENT_STEP_END] == [0, 1]
    # On run_end the count lives in its own field, not in ``index``.
    assert frames[-1]["steps_done"] == 2
    assert "index" not in frames[-1]
    assert frames[-1]["status"] == "ok"
    assert frames[-1]["total"] == 2


def test_run_end_omits_index_and_keeps_total():
    """``index`` is a step position, so a run-level frame must not carry one."""
    emitter, stream = _emitter()
    emitter.run_start(total=5)
    emitter.run_end(status="ok", steps_done=3, total=5, elapsed_s=2.5)
    frame = _frames(stream)[-1]
    assert frame["event"] == EVENT_RUN_END
    assert "index" not in frame
    assert frame["total"] == 5
    assert frame["steps_done"] == 3
    assert frame["elapsed_s"] == 2.5


def test_step_frames_never_carry_steps_done():
    """``steps_done`` is a run-level count; step frames use ``index``."""
    emitter, stream = _emitter()
    emitter.step_start(index=0, total=2, name="a", tier="core")
    emitter.step_end(index=0, total=2, name="a", tier="core", status="ok")
    emitter.step_start(index=1, total=2, name="b", tier="runtime")
    emitter.step_end(index=1, total=2, name="b", tier="runtime", status="ok")
    frames = _frames(stream)
    assert len(frames) == 4
    for frame in frames:
        assert "steps_done" not in frame
    step_ends = [f for f in frames if f["event"] == EVENT_STEP_END]
    assert [f["index"] for f in step_ends] == [0, 1]


def test_progress_event_defaults_steps_done_to_none():
    event = ProgressEvent(event=EVENT_RUN_END, ts="2026-09-30T00:00:00Z")
    assert event.steps_done is None
    assert "steps_done" not in event.to_dict()


# ------------------------------------------------------------ status vocabulary


@pytest.mark.parametrize(
    "status,expected",
    [
        (Status.OK, "ok"),
        (Status.WARN, "warn"),
        (Status.FAILED, "fail"),
        (Status.SKIPPED, "skip"),
        (Status.RUNNING, "running"),
        (Status.PENDING, "pending"),
        (Status.ROLLED_BACK, "rolled_back"),
    ],
)
def test_status_str_maps_every_status_member(status, expected):
    assert status_str(status) == expected


def test_status_str_distinguishes_every_member():
    labels = {status_str(member) for member in Status}
    assert len(labels) == len(list(Status)), "two Status members collapse to one label"


def test_status_str_accepts_plain_strings():
    assert status_str("OK") == "ok"
    assert status_str("failed") == "failed"


def test_tier_str_lowercases_every_tier():
    assert [tier_str(tier) for tier in Tier] == ["core", "runtime", "optional"]


# ------------------------------------------------------------------ resilience


def test_a_broken_stream_never_propagates():
    """A dead progress consumer must not abort a setup run."""
    emitter = ProgressEmitter(stream=_BrokenStream())
    emitter.run_start(total=1)
    emitter.step_start(index=0, total=1, name="x", tier="core")
    emitter.step_end(index=0, total=1, name="x", tier="core", status="ok")
    emitter.run_end(status="ok", steps_done=1, total=1)
    assert emitter.run_id


def test_a_hostile_step_name_cannot_break_framing():
    emitter, stream = _emitter()
    hostile = 'we"ird\nname\\with\ttabs'
    emitter.step_start(index=0, total=1, name=hostile, tier="core")
    raw = stream.getvalue()
    assert raw.count("\n") == 1, "a frame must never contain a raw newline"
    assert len(raw.splitlines()) == 1
    assert json.loads(raw)["name"] == hostile


def test_run_id_is_stable_within_a_run_and_unique_across_two():
    first, first_stream = _emitter()
    second, second_stream = _emitter()
    _full_run(first)
    second.run_start(total=1)
    assert len({f["run_id"] for f in _frames(first_stream)}) == 1
    assert first.run_id != second.run_id
    assert _frames(second_stream)[0]["run_id"] == second.run_id


def test_default_progress_stream_is_stderr():
    assert default_progress_stream() is sys.stderr


# ----------------------------------------------------------------- orchestrator


def test_orchestrator_without_progress_behaves_exactly_as_before(tmp_path):
    orchestrator = Orchestrator(
        EnvironmentDetector(tmp_path).detect(),
        tmp_path,
        reporter=Reporter(quiet=True),
    )
    assert orchestrator.progress is None
    assert callable(orchestrator.run_full_setup)


def test_orchestrator_emits_frames_during_a_dry_run(tmp_path):
    stream = io.StringIO()
    orchestrator = Orchestrator(
        EnvironmentDetector(tmp_path).detect(),
        tmp_path,
        reporter=Reporter(quiet=True),
        dry_run=True,
        progress=ProgressEmitter(stream=stream),
    )
    orchestrator.run_full_setup([Tier.CORE.value])

    frames = _frames(stream)
    assert frames, "progress produced no frames"
    assert frames[0]["event"] == EVENT_RUN_START
    assert frames[-1]["event"] == EVENT_RUN_END

    starts = [f for f in frames if f["event"] == EVENT_STEP_START]
    ends = [f for f in frames if f["event"] == EVENT_STEP_END]
    assert starts and len(starts) == len(ends), "every start needs an end"
    assert [f["index"] for f in starts] == list(range(len(starts)))
    assert all(f["status"] == "running" for f in starts)
    assert all("steps_done" not in f for f in starts + ends)

    assert frames[-1]["status"] in ("ok", "failed")
    assert "index" not in frames[-1]
    assert frames[-1]["steps_done"] == len(starts)
    assert frames[-1]["total"] == frames[0]["total"]
