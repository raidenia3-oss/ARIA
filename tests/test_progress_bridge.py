"""Tests for the progress bridge.

The bridge must never raise: a refused hub, a dropped connection or a timeout
has to be counted and swallowed, because progress is observability and a
broken bridge must not abort a setup run.
"""

from __future__ import annotations

import io
import json
from unittest.mock import patch

import pytest

from aria_autoconfig.progress import ProgressEmitter, ProgressEvent, EVENT_RUN_START
from aria_autoconfig.progress_bridge import HubForwardingEmitter, make_emitter, _post_frame


class _FakeResponse:
    def __init__(self, status: int = 202) -> None:
        self.status = status
        self._body = b'{"status":"accepted"}'

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


def test_post_frame_success_returns_true():
    with patch("aria_autoconfig.progress_bridge.urllib.request.urlopen") as mock_open:
        mock_open.return_value = _FakeResponse(202)
        assert _post_frame({"aria_progress": True, "event": "run_start"}) is True


def test_post_frame_http_error_returns_false():
    import urllib.error
    with patch("aria_autoconfig.progress_bridge.urllib.request.urlopen") as mock_open:
        mock_open.side_effect = urllib.error.HTTPError(
            "http://127.0.0.1:8002/api/control/progress/push", 503, "Unavailable", {}, None
        )
        assert _post_frame({"aria_progress": True}) is False


def test_post_frame_url_error_returns_false():
    import urllib.error
    with patch("aria_autoconfig.progress_bridge.urllib.request.urlopen") as mock_open:
        mock_open.side_effect = urllib.error.URLError("connection refused")
        assert _post_frame({"aria_progress": True}) is False


def test_post_frame_timeout_returns_false():
    with patch("aria_autoconfig.progress_bridge.urllib.request.urlopen") as mock_open:
        mock_open.side_effect = TimeoutError("timed out")
        assert _post_frame({"aria_progress": True}) is False


def test_emitter_still_writes_ndjson_to_stream():
    buf = io.StringIO()
    emitter = HubForwardingEmitter(stream=buf, hub_url="http://127.0.0.1:8002/api/control/progress/push")
    with patch("aria_autoconfig.progress_bridge.urllib.request.urlopen") as mock_open:
        mock_open.return_value = _FakeResponse(202)
        emitter.run_start(3)

    lines = [line for line in buf.getvalue().splitlines() if line.strip()]
    assert len(lines) == 1
    frame = json.loads(lines[0])
    assert frame["aria_progress"] is True
    assert frame["event"] == EVENT_RUN_START
    assert frame["total"] == 3
    assert emitter.stats()["sent"] == 1
    assert emitter.stats()["dropped"] == 0


def test_emitter_counts_dropped_when_hub_unreachable():
    buf = io.StringIO()
    emitter = HubForwardingEmitter(stream=buf, hub_url="http://127.0.0.1:8002/api/control/progress/push")
    with patch("aria_autoconfig.progress_bridge.urllib.request.urlopen") as mock_open:
        mock_open.side_effect = ConnectionError("refused")
        emitter.run_start(2)

    assert emitter.stats()["sent"] == 0
    assert emitter.stats()["dropped"] == 1
    # The NDJSON line still made it to the stream — the bridge is additive.
    assert "run_start" in buf.getvalue()


def test_make_emitter_uses_default_stream():
    emitter = make_emitter()
    assert isinstance(emitter, HubForwardingEmitter)
    assert emitter.stream is not None


def test_emitter_run_id_propagated_to_frame():
    buf = io.StringIO()
    emitter = HubForwardingEmitter(stream=buf, run_id="abc123")
    with patch("aria_autoconfig.progress_bridge.urllib.request.urlopen") as mock_open:
        mock_open.return_value = _FakeResponse(202)
        emitter.run_start(1)

    frame = json.loads(buf.getvalue().splitlines()[0])
    assert frame["run_id"] == "abc123"


def test_reset_stats_zeroes_counters():
    emitter = HubForwardingEmitter()
    with patch("aria_autoconfig.progress_bridge.urllib.request.urlopen") as mock_open:
        mock_open.return_value = _FakeResponse(202)
        emitter.run_start(1)
        emitter.run_start(1)

    assert emitter.stats()["sent"] == 2
    emitter.reset_stats()
    assert emitter.stats() == {"sent": 0, "dropped": 0}


def test_progress_event_to_dict_has_marker():
    event = ProgressEvent(event=EVENT_RUN_START, ts="2026-10-01T00:00:00Z", total=4)
    payload = event.to_dict()
    assert payload["aria_progress"] is True
    assert payload["event"] == EVENT_RUN_START
    assert payload["total"] == 4
    # Absent optional fields are omitted, not materialised as null.
    assert "index" not in payload
    assert "steps_done" not in payload