"""BLOQUE 66 - Local Runtime Watchdog, Auto-Recovery & Session State Persistence tests."""

import time

import pytest

from backend.automation.watchdog import (
    HealthStatus,
    ProcessHealth,
    ProcessHealthMonitor,
    RecoveryAction,
    RuntimeWatchdog,
    SessionCheckpoint,
    SessionCheckpointManager,
    WatchdogEvent,
    WatchdogPolicy,
    WatchdogStatus,
    get_watchdog,
    reset_watchdog,
)


class TestProcessHealthMonitor:
    def test_track_untracked_pid(self):
        m = ProcessHealthMonitor()
        import os

        assert m.track(os.getpid()) is True
        assert m.tracked_pids() == [os.getpid()]
        m.untrack(os.getpid())
        assert m.tracked_pids() == []

    def test_check_dead_pid(self):
        m = ProcessHealthMonitor()
        assert m.track(999999) is False

    def test_clear(self):
        m = ProcessHealthMonitor()
        import os

        m.track(os.getpid())
        m.clear()
        assert m.tracked_pids() == []

    def test_kill_dead_pid(self):
        m = ProcessHealthMonitor()
        assert m.kill(999999) is False


class TestSessionCheckpointManager:
    def test_save_and_restore(self, tmp_path):
        cm = SessionCheckpointManager("s1", checkpoint_dir=str(tmp_path))
        cp = cm.save(task_id="t1", objective="test", progress={"step": 1})
        assert isinstance(cp, SessionCheckpoint)
        latest = cm.restore_latest()
        assert latest["task_id"] == "t1"
        assert latest["progress"]["step"] == 1

    def test_list_and_count(self, tmp_path):
        cm = SessionCheckpointManager("s2", checkpoint_dir=str(tmp_path))
        cm.save(task_id="t1", objective="a", progress={})
        cm.save(task_id="t2", objective="b", progress={})
        assert cm.count() == 2
        assert len(cm.list_checkpoints()) == 2

    def test_max_snapshots_eviction(self, tmp_path):
        cm = SessionCheckpointManager("s3", checkpoint_dir=str(tmp_path), max_snapshots=2)
        cm.save(task_id="t1", objective="a", progress={})
        cm.save(task_id="t2", objective="b", progress={})
        cm.save(task_id="t3", objective="c", progress={})
        assert cm.count() == 2
        cps = cm.list_checkpoints()
        assert cps[0]["task_id"] == "t2"

    def test_clear(self, tmp_path):
        cm = SessionCheckpointManager("s4", checkpoint_dir=str(tmp_path))
        cm.save(task_id="t1", objective="a", progress={})
        cm.clear()
        assert cm.count() == 0


class TestRuntimeWatchdog:
    def test_start_stop(self, tmp_path):
        wd = RuntimeWatchdog("sess-a", checkpoint_dir=str(tmp_path))
        assert wd.start() is True
        assert wd.get_status().running is True
        wd.stop()
        assert wd.get_status().running is False

    def test_double_start(self, tmp_path):
        wd = RuntimeWatchdog("sess-b", checkpoint_dir=str(tmp_path))
        assert wd.start() is True
        assert wd.start() is False
        wd.stop()

    def test_heartbeat_and_inactivity(self, tmp_path):
        wd = RuntimeWatchdog(
            "sess-c", checkpoint_dir=str(tmp_path), policy=WatchdogPolicy(inactivity_timeout=0.1)
        )
        wd.start()
        time.sleep(0.3)
        wd.check_once()
        events = wd.recent_events(10)
        assert any(e["kind"] == "inactivity" for e in events)
        wd.stop()

    def test_checkpoint_and_restore(self, tmp_path):
        wd = RuntimeWatchdog("sess-d", checkpoint_dir=str(tmp_path))
        wd.save_checkpoint(task_id="t1", objective="run", progress={"i": 1}, active_macros=["m1"])
        cp = wd.restore_session()
        assert cp["task_id"] == "t1"
        assert cp["progress"]["i"] == 1
        assert cp["active_macros"] == ["m1"]

    def test_crash_recovery_event(self, tmp_path):
        wd = RuntimeWatchdog("sess-e", checkpoint_dir=str(tmp_path))
        wd.track_process(999999)
        wd.check_once()
        events = wd.recent_events(10)
        assert any(e["kind"] == "process_crash" for e in events)

    def test_get_status_fields(self, tmp_path):
        wd = RuntimeWatchdog("sess-f", checkpoint_dir=str(tmp_path))
        st = wd.get_status()
        assert isinstance(st, WatchdogStatus)
        assert st.session_id == "sess-f"
        assert st.health == HealthStatus.HEALTHY
        assert st.events_total == 0

    def test_singleton(self, tmp_path):
        reset_watchdog()
        a = RuntimeWatchdog("singleton-sess", checkpoint_dir=str(tmp_path))
        import backend.automation.watchdog as mod

        mod._watchdog = a
        b = get_watchdog("singleton-sess")
        assert a is b
        reset_watchdog()


def test_policy_defaults():
    p = WatchdogPolicy()
    assert p.inactivity_timeout > 0
    assert p.max_retries > 0
    assert p.auto_restart is True


def test_recovery_action_values():
    assert RecoveryAction.NONE.value == "none"
    assert RecoveryAction.FULL_RECOVERY.value == "full_recovery"
