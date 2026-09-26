"""BLOQUE 67 - Local Autonomous Task Scheduler & Cron Engine tests."""

import time

import pytest

from backend.automation.scheduler import (
    CronParseError,
    ResourceConflictResolver,
    ScheduledTask,
    TaskPersistence,
    TaskSchedulerEngine,
    get_scheduler,
    next_cron_fire,
    parse_cron,
    reset_scheduler,
    validate_cron,
)


class TestCronParser:
    def test_basic_cron(self):
        mins, hors, doms, mons, dows, dom_all, dow_all = parse_cron("0 0 * * *")
        assert mins == {0}
        assert hors == {0}
        assert dom_all is True
        assert dow_all is True

    def test_step(self):
        mins, *_ = parse_cron("*/5 * * * *")
        assert mins == {0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}

    def test_list(self):
        mins, *_ = parse_cron("0,15,30,45 * * * *")
        assert mins == {0, 15, 30, 45}

    def test_range(self):
        mins, *_ = parse_cron("0-10 * * * *")
        assert mins == set(range(0, 11))

    def test_invalid(self):
        with pytest.raises(CronParseError):
            parse_cron("bad cron")
        with pytest.raises(CronParseError):
            parse_cron("60 * * * *")

    def test_validate(self):
        assert validate_cron("0 0 * * *") is True
        assert validate_cron("not a cron") is False

    def test_next_fire(self):
        now = time.time()
        nxt = next_cron_fire("*/5 * * * *", now)
        assert nxt > now
        assert nxt - now <= 5 * 60 + 5


class TestScheduledTask:
    def test_validate_interval(self):
        t = ScheduledTask(task_id="t1", name="n", kind="k", trigger="interval", interval_seconds=10)
        t.validate()

    def test_validate_cron(self):
        t = ScheduledTask(task_id="t2", name="n", kind="k", trigger="cron", cron="0 0 * * *")
        t.validate()

    def test_invalid_trigger(self):
        t = ScheduledTask(task_id="t3", name="n", kind="k", trigger="bad")
        with pytest.raises(ValueError):
            t.validate()

    def test_to_dict(self):
        t = ScheduledTask(task_id="t4", name="n", kind="k", resources=("screen",))
        d = t.to_dict()
        assert d["task_id"] == "t4"
        assert d["resources"] == ["screen"]


class TestResourceConflictResolver:
    def test_acquire_release(self):
        r = ResourceConflictResolver()
        assert r.acquire_all(["screen"], "owner1") is True
        assert r.acquire_all(["screen"], "owner2") is False
        r.release_all(["screen"], "owner1")
        assert r.acquire_all(["screen"], "owner2") is True

    def test_snapshot(self):
        r = ResourceConflictResolver()
        r.acquire_all(["a", "b"], "x")
        snap = r.snapshot()
        assert snap == {"a": "x", "b": "x"}


class TestTaskSchedulerEngine:
    def test_add_and_list(self, tmp_path):
        s = TaskSchedulerEngine(persist_dir=str(tmp_path))
        t = ScheduledTask(task_id="t1", name="n", kind="k", trigger="interval", interval_seconds=10)
        assert s.add_task(t) is True
        assert s.add_task(t) is False
        assert len(s.list_tasks()) == 1

    def test_remove(self, tmp_path):
        s = TaskSchedulerEngine(persist_dir=str(tmp_path))
        t = ScheduledTask(task_id="t1", name="n", kind="k")
        s.add_task(t)
        assert s.remove_task("t1") is True
        assert s.remove_task("t1") is False

    def test_pause_resume(self, tmp_path):
        s = TaskSchedulerEngine(persist_dir=str(tmp_path))
        t = ScheduledTask(task_id="t1", name="n", kind="k")
        s.add_task(t)
        assert s.pause_task("t1") is True
        assert s.get_task("t1").status == "paused"
        assert s.resume_task("t1") is True
        assert s.get_task("t1").status == "idle"

    def test_enable_disable(self, tmp_path):
        s = TaskSchedulerEngine(persist_dir=str(tmp_path))
        t = ScheduledTask(task_id="t1", name="n", kind="k")
        s.add_task(t)
        assert s.enable_task("t1", False) is True
        assert s.get_task("t1").enabled is False

    def test_tick_fires(self, tmp_path):
        fired_events = []

        def on_task(task, result):
            fired_events.append(task.task_id)

        s = TaskSchedulerEngine(persist_dir=str(tmp_path), on_task=on_task)
        t = ScheduledTask(task_id="t1", name="n", kind="k", trigger="interval", interval_seconds=1)
        t.next_run = time.time() - 1
        s.add_task(t)
        fired = s.tick_once()
        assert len(fired) == 1
        assert fired[0]["task_id"] == "t1"
        assert fired_events == ["t1"]
        assert s.get_task("t1").run_count == 1

    def test_overlap_skip(self, tmp_path):
        s = TaskSchedulerEngine(persist_dir=str(tmp_path))
        t1 = ScheduledTask(task_id="t1", name="n", kind="k", resources=("screen",))
        t1.next_run = time.time() - 1
        t2 = ScheduledTask(task_id="t2", name="n2", kind="k", resources=("screen",))
        t2.next_run = time.time() - 1
        s.add_task(t1)
        s.add_task(t2)
        fired = s.tick_once()
        assert len(fired) == 1

    def test_persistence_roundtrip(self, tmp_path):
        s = TaskSchedulerEngine(persist_dir=str(tmp_path))
        t = ScheduledTask(task_id="t1", name="n", kind="k")
        s.add_task(t)
        s._persist()
        s2 = TaskSchedulerEngine(persist_dir=str(tmp_path))
        assert s2.get_task("t1") is not None
        assert s2.get_task("t1").name == "n"

    def test_status(self, tmp_path):
        s = TaskSchedulerEngine(persist_dir=str(tmp_path))
        st = s.status()
        assert st["running"] is False
        assert st["tasks_total"] == 0


def test_singleton():
    reset_scheduler()
    import backend.automation.scheduler as mod

    mod._scheduler = None
    a = get_scheduler()
    b = get_scheduler()
    assert a is b
    reset_scheduler()
