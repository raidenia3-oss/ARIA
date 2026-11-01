"""Tests del event log append-only.

Se cubren las garantias que hacen util el log: esquema cerrado (el modelo
evaluado no puede escribir contenido arbitrario), append-only real,
durabilidad, y que lo no medido se marque como `unavailable` en vez de 0.
"""

from __future__ import annotations

import json
import os

import pytest

from backend.eventlog import EventLog


@pytest.fixture()
def log(tmp_path) -> EventLog:
    return EventLog(tmp_path / "events.jsonl")


def _lines(path):
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_append_writes_one_json_line_per_event(log, tmp_path):
    first = log.append("routing.decision", provider="mistral", outcome="ok", latency_ms=120.5)
    second = log.append("routing.decision", provider="local-ollama", outcome="ok", latency_ms=3400.0)

    assert first["seq"] == 0
    assert second["seq"] == 1
    assert first["ts"].endswith("Z")

    lines = _lines(tmp_path / "events.jsonl")
    assert len(lines) == 2
    assert json.loads(lines[0])["provider"] == "mistral"


def test_unknown_field_is_rejected(log):
    """El esquema cerrado es lo que impide que el modelo escriba en el log."""
    with pytest.raises(TypeError) as excinfo:
        log.append("routing.decision", prompt="instruccion inyectada", outcome="ok")
    assert "prompt" in str(excinfo.value)


def test_cannot_smuggle_content_through_error_field_shape(log):
    """Un error se acota y se aplana: no puede inyectar saltos de linea en JSONL."""
    event = log.append(
        "routing.provider_error",
        provider="deepseek",
        outcome="error",
        error="linea1\nlinea2\n" + "x" * 5000,
    )
    assert "\n" not in event["error"]
    assert len(event["error"]) <= 300
    # Sigue siendo una sola linea JSON valida.
    assert len(_lines(log.path)) == 1


def test_append_only_never_rewrites_history(log, tmp_path):
    log.append("routing.decision", provider="a", outcome="ok", latency_ms=1.0)
    first_snapshot = (tmp_path / "events.jsonl").read_text(encoding="utf-8")

    log.append("routing.decision", provider="b", outcome="ok", latency_ms=2.0)
    log.append("routing.decision", provider="c", outcome="error", error="boom")

    current = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert current.startswith(first_snapshot), "un evento anterior fue reescrito"
    assert len(_lines(tmp_path / "events.jsonl")) == 3


def test_unmeasured_values_are_none_not_zero(log):
    """tokens y coste no medidos se registran como None + data_source unavailable."""
    event = log.append(
        "routing.decision",
        provider="mistral",
        outcome="ok",
        latency_ms=88.2,
        tokens=None,
        cost_usd=None,
    )
    assert event["tokens"] is None
    assert event["cost_usd"] is None
    # El evento viene de una medicion real: la latencia SI se midio.
    assert event["data_source"] == "measured"
    assert event["latency_ms"] == 88.2
    # Y el log dice exactamente que campos faltan, en vez de marcarlo todo.
    assert event["unmeasured"] == ["tokens", "cost_usd"]

    reloaded = log.tail(1)[0]
    assert reloaded["tokens"] is None
    assert reloaded["cost_usd"] is None


def test_measured_values_are_marked_measured(log):
    event = log.append(
        "routing.decision",
        provider="local-ollama",
        outcome="ok",
        latency_ms=3400.0,
        tokens=128,
        cost_usd=0.002,
    )
    assert event["data_source"] == "measured"
    assert event["tokens"] == 128


def test_corrupt_line_is_visible_not_skipped(log, tmp_path):
    log.append("routing.decision", provider="mistral", outcome="ok", latency_ms=10.0)
    with open(tmp_path / "events.jsonl", "a", encoding="utf-8", newline="\n") as handle:
        handle.write("{esto no es json\n")
    log.append("routing.decision", provider="deepseek", outcome="ok", latency_ms=20.0)

    assert log.corrupt_count() == 1
    events = log.tail(10)
    assert len(events) == 3
    assert events[1]["_corrupt"] is True
    assert events[1]["raw"].startswith("{esto no es json")


def test_tail_filters_by_kind(log):
    log.append("routing.decision", provider="a", outcome="ok", latency_ms=1.0)
    log.append("provider.probe", provider="deepseek", available=False)
    log.append("routing.decision", provider="b", outcome="ok", latency_ms=2.0)

    decisions = log.tail(10, kind="routing.decision")
    assert [e["provider"] for e in decisions] == ["a", "b"]


def test_tail_respects_limit_and_keeps_chronological_order(log):
    for index in range(10):
        log.append("routing.decision", provider=f"p{index}", outcome="ok", latency_ms=index)

    tail = log.tail(3)
    assert [e["provider"] for e in tail] == ["p7", "p8", "p9"]
    assert log.tail(0) == []


def test_provider_stats_ignores_unmeasured_latency(log):
    log.append("routing.decision", provider="mistral", outcome="ok", latency_ms=100.0, tokens=10)
    log.append("routing.decision", provider="mistral", outcome="ok", latency_ms=200.0, tokens=12)
    log.append("routing.decision", provider="deepseek", outcome="error", error="HTTP 402")
    log.append("routing.decision", provider="none", outcome="error", error="all failed")

    stats = log.provider_stats()

    assert stats["mistral"]["ok"] == 2
    assert stats["mistral"]["latency_mean_ms"] == 150.0
    assert stats["mistral"]["token_samples"] == 2

    assert stats["deepseek"]["ok"] == 0
    assert stats["deepseek"]["error"] == 1
    # Sin muestras no se inventa un promedio.
    assert stats["deepseek"]["latency_mean_ms"] is None

    assert stats["none"]["error"] == 1


def test_summary_reports_measured_counts(log):
    log.append("routing.decision", provider="mistral", outcome="ok", latency_ms=10.0)
    summary = log.summary()
    assert summary["events"] == 1
    assert summary["corrupt_lines"] == 0
    assert summary["data_source"] == "measured"


def test_reopen_continues_sequence(log, tmp_path):
    log.append("routing.decision", provider="a", outcome="ok", latency_ms=1.0)
    reopened = EventLog(tmp_path / "events.jsonl")
    event = reopened.append("routing.decision", provider="b", outcome="ok", latency_ms=2.0)
    assert event["seq"] == 1


def test_missing_parent_dir_is_created(log, tmp_path):
    nested = EventLog(tmp_path / "a" / "b" / "events.jsonl")
    assert nested.append("routing.decision", provider="a", outcome="ok", latency_ms=1.0)
    assert (tmp_path / "a" / "b" / "events.jsonl").exists()


def test_disk_failure_returns_none_instead_of_raising(log, tmp_path, monkeypatch):
    """Un fallo de E/S no puede tumbar la peticion que ya se respondio."""

    def boom(*_args, **_kwargs):
        raise OSError("disco lleno")

    monkeypatch.setattr("backend.eventlog.os.fsync", boom)
    assert log.append("routing.decision", provider="a", outcome="ok", latency_ms=1.0) is None


def test_invalid_outcome_and_data_source_rejected(log):
    with pytest.raises(ValueError):
        log.append("routing.decision", provider="a", outcome="tal_maybe")
    with pytest.raises(ValueError):
        log.append("routing.decision", provider="a", outcome="ok", data_source="vibes")


def test_iter_events_on_missing_file_is_empty(tmp_path):
    empty = EventLog(tmp_path / "nunca.jsonl")
    assert empty.tail(10) == []
    assert list(empty.iter_events()) == []
    assert empty.summary()["events"] == 0