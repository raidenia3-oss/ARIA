"""Tests for backend.agents.llm_cli.quota."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from backend.agents.llm_cli.quota import (
    DailyCounter,
    QuotaConfig,
    QuotaManager,
    get_quota_manager,
    reset_quota_manager,
)


@pytest.fixture
def state_path(tmp_path: Path) -> str:
    return str(tmp_path / "quota.json")


@pytest.fixture
def manager(state_path: str) -> QuotaManager:
    return QuotaManager(
        state_path=state_path,
        config=QuotaConfig(max_calls_per_day=3, cooldown_seconds=60.0),
    )


def test_can_call_when_under_limit(manager: QuotaManager):
    ok, reason = manager.can_call()
    assert ok is True
    assert reason is None


def test_record_increments_counter(manager: QuotaManager):
    manager.record_call(success=True)
    manager.record_call(success=False)
    st = manager.state()
    assert st["calls_measured"] == 2
    assert st["limit"] == 3


def test_exhaustion_triggers_cooldown(manager: QuotaManager):
    for _ in range(3):
        manager.record_call(success=True)
    ok, reason = manager.can_call()
    assert ok is False
    assert reason is not None
    assert "quota exhausted" in reason
    st = manager.state()
    assert st["in_cooldown"] is True
    assert st["cooldown_remaining_s"] > 0


def test_no_limit_when_disabled(state_path: str):
    mgr = QuotaManager(
        state_path=state_path,
        config=QuotaConfig(max_calls_per_day=0, cooldown_seconds=1.0),
    )
    ok, _ = mgr.can_call()
    assert ok is True
    # recording does not block
    for _ in range(1000):
        mgr.record_call(success=True)
    ok, _ = mgr.can_call()
    assert ok is True


def test_persists_to_disk(state_path: str):
    mgr = QuotaManager(
        state_path=state_path,
        config=QuotaConfig(max_calls_per_day=5, cooldown_seconds=10.0),
    )
    mgr.record_call(success=True)
    mgr2 = QuotaManager(
        state_path=state_path,
        config=QuotaConfig(max_calls_per_day=5, cooldown_seconds=10.0),
    )
    assert mgr2.state()["calls_measured"] == 1


def test_reset_on_new_day(state_path: str):
    mgr = QuotaManager(
        state_path=state_path,
        config=QuotaConfig(max_calls_per_day=2, cooldown_seconds=10.0),
    )
    mgr.record_call(success=True)
    mgr.record_call(success=True)
    # Simulate a stale persisted state from a previous day.
    data = json.loads(Path(state_path).read_text(encoding="utf-8"))
    data["day"] = "1970-01-01"
    Path(state_path).write_text(json.dumps(data), encoding="utf-8")
    mgr2 = QuotaManager(
        state_path=state_path,
        config=QuotaConfig(max_calls_per_day=2, cooldown_seconds=10.0),
    )
    ok, _ = mgr2.can_call()
    assert ok is True
    assert mgr2.state()["calls_measured"] == 0


def test_corrupt_state_file_falls_back(state_path: str):
    Path(state_path).write_text("not json{", encoding="utf-8")
    mgr = QuotaManager(
        state_path=state_path,
        config=QuotaConfig(max_calls_per_day=2, cooldown_seconds=10.0),
    )
    ok, _ = mgr.can_call()
    assert ok is True
    assert mgr.state()["calls_measured"] == 0


def test_source_is_documented(manager: QuotaManager):
    assert manager.state()["source"] == "documented"


def test_never_reports_remaining(manager: QuotaManager):
    st = manager.state()
    assert "remaining" not in st
    assert "calls_measured" in st
    assert "limit" in st


def test_singleton_get_and_reset(state_path: str, monkeypatch):
    monkeypatch.setenv("AURA_GEMINI_CLI_QUOTA_STATE", state_path)
    reset_quota_manager()
    a = get_quota_manager()
    b = get_quota_manager()
    assert a is b
    reset_quota_manager()
    c = get_quota_manager()
    assert c is not a


def test_env_config(state_path: str, monkeypatch):
    monkeypatch.setenv("AURA_GEMINI_CLI_DAILY_LIMIT", "2")
    monkeypatch.setenv("AURA_GEMINI_CLI_COOLDOWN", "5")
    mgr = QuotaManager(state_path=state_path)
    assert mgr.config.max_calls_per_day == 2
    assert mgr.config.cooldown_seconds == 5.0


def test_daily_counter_dataclass():
    dc = DailyCounter(day="2026-10-10", calls=1)
    assert dc.day == "2026-10-10"
    assert dc.calls == 1