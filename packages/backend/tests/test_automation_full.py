# -*- coding: utf-8 -*-
"""AURA OS — Automation Full Test Suite."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestUSBStorageManager:
    def setup_method(self):
        from backend.storage.usb_storage_manager import USBStorageManager
        self.usb = USBStorageManager()
        self.usb._log_file.unlink(missing_ok=True)
        self.usb.offload_history.clear()
        self.usb.offload_queue.clear()
        self.usb.usb_devices.clear()

    def test_scan_usb(self):
        devices = self.usb.scan_usb(force=True)
        assert isinstance(devices, list)

    def test_find_usb(self):
        device = self.usb.find_usb(min_free_gb=0.1)
        if device:
            assert device.free_gb >= 0.1

    def test_is_usb_available(self):
        available, device = self.usb.is_usb_available(min_free_gb=0.1)
        assert isinstance(available, bool)

    def test_usb_status(self):
        status = self.usb.get_usb_status()
        assert "connected" in status
        assert "total_devices" in status

    def test_offload_history_empty(self):
        history = self.usb.get_offload_history()
        assert isinstance(history, list)

    def test_detect_mounts(self):
        mounts = self.usb._detect_mounts()
        assert isinstance(mounts, list)

    def test_get_usage(self):
        usage = self.usb._get_usage(".")
        if usage:
            assert "total" in usage
            assert "free" in usage
            assert "used" in usage

    def test_offload_file_missing(self):
        with pytest.raises(FileNotFoundError):
            self.usb.offload_file("/nonexistent/path/file.txt")


class TestStorageManager:
    def setup_method(self):
        from backend.storage.storage_manager import StorageManager
        self.sm = StorageManager(storage_dir="data/test_storage")

    def test_scan_storage(self):
        report = self.sm.scan_storage(directories=["backend"])
        assert report.total_bytes >= 0
        assert isinstance(report.by_extension, dict)

    def test_cleanup_cache(self):
        result = self.sm.cleanup_cache(max_size_mb=500)
        assert isinstance(result, dict)
        assert "cleaned_files" in result

    def test_compress_videos(self):
        result = self.sm.compress_videos(directory="backend")
        assert isinstance(result, dict)

    def test_get_storage_summary(self):
        summary = self.sm.get_storage_summary()
        assert "total_bytes" in summary
        assert "by_extension" in summary

    def test_auto_cleanup(self):
        result = self.sm.auto_cleanup()
        assert isinstance(result, dict)

    def test_scan_empty(self):
        report = self.sm.scan_storage(directories=["data/test_nonexistent"])
        assert report.total_bytes == 0

    def test_largest_files(self):
        report = self.sm.scan_storage(directories=["backend"])
        assert isinstance(report.largest_files, list)

    def test_by_extension(self):
        report = self.sm.scan_storage(directories=["backend"])
        assert isinstance(report.by_extension, dict)
        assert len(report.by_extension) > 0


class TestWorkflowTemplates:
    def setup_method(self):
        from backend.automation.workflow_templates import WorkflowTemplates
        self.wf = WorkflowTemplates()
        self.wf.STORAGE_FILE.unlink(missing_ok=True)
        self.wf.templates.clear()
        self.wf.executions.clear()

    def test_register_template(self):
        t = self.wf.register_template("test-wf", "Test", "manual", [
            {"action": "step1"}, {"action": "step2"},
        ])
        assert t.template_id == "test-wf"
        assert len(t.steps) == 2

    def test_get_template(self):
        self.wf.register_template("get-test", "Get Test", "manual", [{"action": "a"}])
        t = self.wf.get_template("get-test")
        assert t is not None
        assert t.name == "Get Test"

    def test_validate_template(self):
        self.wf.register_template("validate-test", "V", "manual", [{"action": "a"}])
        result = self.wf.validate_template("validate-test")
        assert result["valid"] is True

    def test_validate_empty_template(self):
        self.wf.register_template("empty", "", "", [])
        result = self.wf.validate_template("empty")
        assert result["valid"] is False

    def test_execute_template(self):
        self.wf.register_template("exec-test", "Execute", "manual", [
            {"action": "step1"}, {"action": "step2"},
        ])
        exec_result = self.wf.execute_template("exec-test")
        assert exec_result.status in ("completed", "failed")
        assert len(exec_result.results) == 2

    def test_list_templates(self):
        self.wf.register_template("t1", "Template 1", "manual", [{"action": "a"}])
        templates = self.wf.list_templates()
        assert len(templates) >= 1

    def test_schedule_all(self):
        self.wf.register_template("sched", "Scheduled", "manual", [{"action": "a"}],
                                   schedule="0 * * * *")
        scheduled = self.wf.schedule_all()
        assert "sched" in scheduled

    def test_get_stats(self):
        stats = self.wf.get_stats()
        assert "total_templates" in stats

    def test_execute_missing_template(self):
        with pytest.raises(ValueError):
            self.wf.execute_template("nonexistent")

    def test_disabled_template(self):
        self.wf.register_template("dis", "Disabled", "manual", [{"action": "a"}])
        self.wf.templates["dis"].enabled = False
        with pytest.raises(ValueError):
            self.wf.execute_template("dis")


class TestTriggerEngine:
    def setup_method(self):
        from backend.automation.trigger_engine import TriggerEngine
        self.te = TriggerEngine()
        self.te.STORAGE_FILE.unlink(missing_ok=True)
        self.te.conditions.clear()
        self.te.events.clear()

    def test_add_condition(self):
        c = self.te.add_condition("t1", "Test", "cpu", ">", 0.8, "action")
        assert c.condition_id == "t1"
        assert c.operator == ">"

    def test_set_value_and_evaluate(self):
        self.te.add_condition("cpu-high", "CPU", "cpu_usage", ">", 0.8, "cool_down")
        self.te.set_value("cpu_usage", 0.9)
        triggered = self.te.evaluate(self.te.conditions["cpu-high"])
        assert triggered is True

    def test_not_triggered(self):
        self.te.add_condition("cpu-low", "CPU", "cpu_usage", ">", 0.8, "cool_down")
        self.te.set_value("cpu_usage", 0.3)
        triggered = self.te.evaluate(self.te.conditions["cpu-low"])
        assert triggered is False

    def test_check_all(self):
        self.te.add_condition("m1", "Metric 1", "metric_a", ">", 5, "a")
        self.te.add_condition("m2", "Metric 2", "metric_b", "<", 10, "b")
        self.te.set_value("metric_a", 100)
        self.te.set_value("metric_b", 1)
        events = self.te.check_all()
        assert len(events) == 2  # both m1 and m2 triggered

    def test_get_active_conditions(self):
        self.te.add_condition("a1", "A1", "m1", ">", 1, "act")
        self.te.add_condition("a2", "A2", "m2", ">", 1, "act")
        self.te.conditions["a2"].active = False
        active = self.te.get_active_conditions()
        assert len(active) == 1

    def test_remove_condition(self):
        self.te.add_condition("remove-me", "Remove", "m", ">", 1, "a")
        result = self.te.remove_condition("remove-me")
        assert result is True

    def test_get_stats(self):
        self.te.add_condition("s1", "S1", "m1", ">", 1, "a")
        stats = self.te.get_stats()
        assert stats["total_conditions"] >= 1

    def test_get_triggered_events(self):
        self.te.add_condition("e1", "E1", "cpu", ">", 0.5, "a")
        self.te.set_value("cpu", 0.9)
        self.te.evaluate(self.te.conditions["e1"])
        events = self.te.get_triggered_events()
        assert len(events) >= 1

    def test_equal_operator(self):
        self.te.add_condition("eq", "Equals", "val", "==", 42, "a")
        self.te.set_value("val", 42)
        assert self.te.evaluate(self.te.conditions["eq"]) is True

    def test_not_equal_operator(self):
        self.te.add_condition("ne", "Not Equals", "val", "!=", 99, "a")
        self.te.set_value("val", 42)
        assert self.te.evaluate(self.te.conditions["ne"]) is True


class TestRollerCoinScheduler:
    def setup_method(self):
        from backend.automation.rollercoin_scheduler import RollerCoinScheduler
        self.rc = RollerCoinScheduler()
        self.rc.STORAGE_FILE.unlink(missing_ok=True)
        self.rc.cycles.clear()
        self.rc._last_claim_time = 0.0
        self.rc._current_cycle = None

    def test_can_claim_initial(self):
        can, reason = self.rc.can_claim()
        assert isinstance(can, bool)

    def test_start_cycle(self):
        cycle = self.rc.start_cycle()
        assert cycle.status == "running"
        assert cycle.claims_made == 0

    def test_complete_cycle(self):
        cycle = self.rc.start_cycle()
        completed = self.rc.complete_cycle(claims=3, tokens=2.5)
        assert completed.status == "completed"
        assert completed.claims_made == 3
        assert completed.tokens_mined == 2.5

    def test_get_mining_stats(self):
        self.rc.start_cycle()
        self.rc.complete_cycle(claims=2, tokens=1.0)
        stats = self.rc.get_mining_stats()
        assert stats["total_cycles"] >= 1
        assert stats["completed"] >= 1

    def test_claim(self):
        result = self.rc.claim()
        assert isinstance(result, dict)

    def test_get_schedule(self):
        self.rc.start_cycle()
        self.rc.complete_cycle(claims=1, tokens=0.5)
        schedule = self.rc.get_schedule()
        assert isinstance(schedule, list)

    def test_get_next_claim_time(self):
        next_time = self.rc.get_next_claim_time()
        assert isinstance(next_time, float)

    def test_claim_after_cycle(self):
        self.rc.cycles.clear()
        self.rc._last_claim_time = time.time()
        can, _ = self.rc.can_claim()
        assert can is True


class TestRecoveryAutomation:
    def setup_method(self):
        from backend.automation.recovery_automation import RecoveryAutomation
        self.ra = RecoveryAutomation()
        self.ra.STORAGE_FILE.unlink(missing_ok=True)
        self.ra.policies.clear()
        self.ra.attempts.clear()

    def test_register_policy(self):
        p = self.ra.register_policy("r1", "Retry", "action_a", ["alt_b", "alt_c"])
        assert p.max_retries == 3
        assert len(p.alternatives) == 2

    def test_execute_direct(self):
        result = self.ra.execute_with_recovery("test_action")
        assert result["success"] is True

    def test_get_stats(self):
        stats = self.ra.get_recovery_stats()
        assert "total_attempts" in stats

    def test_register_multiple_policies(self):
        self.ra.register_policy("p1", "P1", "action1", ["alt1"])
        self.ra.register_policy("p2", "P2", "action2", ["alt2"])
        assert len(self.ra.policies) == 2

    def test_execute_with_policy(self):
        self.ra.register_policy("policy1", "Test Policy", "test_action", ["alt"])
        result = self.ra.execute_with_recovery("test_action", policy_id="policy1")
        assert isinstance(result, dict)
        assert "retries" in result

    def test_get_failed_actions(self):
        failed = self.ra.get_failed_actions()
        assert isinstance(failed, list)

    def test_rerun_failed(self):
        result = self.ra.rerun_failed()
        assert isinstance(result, dict)

    def test_execute_with_alternative(self):
        self.ra.register_policy("policy2", "Alt Policy", "primary", ["alternative"])
        self.ra._try_action = lambda a, c: (_ for _ in ()).throw(Exception("fail"))
        result = self.ra.execute_with_recovery("primary", policy_id="policy2")
        assert isinstance(result, dict)


class TestBrowserPool:
    def setup_method(self):
        from backend.automation.browser_pool import BrowserPool
        self.bp = BrowserPool()
        self.bp.STORAGE_FILE.unlink(missing_ok=True)
        self.bp.sessions.clear()

    def test_create_session(self):
        session = self.bp.create_session()
        assert session.session_id.startswith("BRW-")
        assert session.status == "idle"

    def test_assign_task(self):
        session = self.bp.create_session()
        result = self.bp.assign_task(session.session_id, "mining")
        assert result is True
        assert session.status == "active"

    def test_complete_task(self):
        session = self.bp.create_session()
        self.bp.assign_task(session.session_id, "task")
        result = self.bp.complete_task(session.session_id)
        assert result is True
        assert session.status == "idle"

    def test_get_pool_status(self):
        self.bp.create_session()
        self.bp.create_session()
        status = self.bp.get_pool_status()
        assert status["total_sessions"] == 2
        assert status["idle"] == 2

    def test_release_session(self):
        session = self.bp.create_session()
        result = self.bp.release_session(session.session_id)
        assert result is True
        assert self.bp.get_session(session.session_id) is None

    def test_get_idle_sessions(self):
        s1 = self.bp.create_session()
        s2 = self.bp.create_session()
        idle = self.bp.get_idle_sessions()
        assert len(idle) == 2

    def test_pool_max_capacity(self):
        from backend.automation.browser_pool import BrowserPool
        fresh = BrowserPool()
        for _ in range(BrowserPool.MAX_SESSIONS):
            fresh.create_session()
        with pytest.raises(RuntimeError):
            fresh.create_session()

    def test_cleanup_stale(self):
        session = self.bp.create_session()
        session.last_activity = time.time() - 7200
        stale = self.bp.cleanup_stale(max_idle_sec=3600)
        assert len(stale) >= 1


class TestDaemonExtended:
    def setup_method(self):
        from backend.daemon.aura_daemon_extended import AuraDaemonExtended
        self.daemon = AuraDaemonExtended()

    def test_initial_status(self):
        status = self.daemon.get_status()
        assert status["active"] is False
        assert status["total_tasks"] == 13

    def test_task_names(self):
        status = self.daemon.get_status()
        assert "storage-manager" in status["task_names"]
        assert "trigger-engine" in status["task_names"]
        assert "browser-pool" in status["task_names"]

    def test_get_status_fields(self):
        status = self.daemon.get_status()
        assert "uptime_seconds" in status
        assert "storage" in status
        assert "triggers" in status

    def test_empty_status(self):
        status = self.daemon.get_status()
        assert status["storage"] == {}
        assert status["triggers"] == {}


class TestIntegration:
    def setup_method(self):
        self.cleanups = []

    def teardown_method(self):
        for path in self.cleanups:
            if Path(path).exists():
                Path(path).unlink()

    def test_full_automation_pipeline(self):
        from backend.automation.workflow_templates import workflow_templates as wt
        from backend.automation.trigger_engine import trigger_engine as te
        from backend.automation.recovery_automation import recovery_automation as ra
        from backend.automation.browser_pool import browser_pool as bp

        wt.templates.clear()
        te.conditions.clear()
        bp.sessions.clear()

        wt.register_template("pipe", "Pipeline", "manual", [{"action": "step1"}])
        exec_result = wt.execute_template("pipe")
        assert exec_result.status == "completed"

        te.add_condition("integ", "Integration", "val", ">", 0, "act")
        te.set_value("val", 10)
        assert te.evaluate(te.conditions["integ"]) is True

        bp.create_session()
        status = bp.get_pool_status()
        assert status["total_sessions"] == 1

        stats = ra.get_recovery_stats()
        assert "total_attempts" in stats

    def test_storage_and_workflows_together(self):
        from backend.storage.storage_manager import storage_manager as sm
        from backend.automation.workflow_templates import workflow_templates as wt
        sm.scan_storage(directories=["backend"])
        summary = sm.get_storage_summary()
        assert summary["total_bytes"] >= 0
        wt.register_template("stor", "Storage", "manual", [{"action": "backup"}])
        assert wt.get_template("stor") is not None

    def test_trigger_and_recovery_together(self):
        from backend.automation.trigger_engine import trigger_engine as te
        from backend.automation.recovery_automation import recovery_automation as ra
        te.add_condition("r1", "Recovery Test", "err_count", ">", 5, "recover")
        ra.register_policy("rp1", "Auto Recovery", "retry", ["fallback"])
        stats_te = te.get_stats()
        stats_ra = ra.get_recovery_stats()
        assert stats_te["total_conditions"] >= 1
        assert "total_attempts" in stats_ra

    def test_routes_importable(self):
        from backend.api.automation_routes import router as auto_router
        from backend.api.storage_routes import router as storage_router
        assert auto_router is not None
        assert storage_router is not None
        assert auto_router.prefix == "/api/automation"
        assert storage_router.prefix == "/api/storage"

    def test_all_modules_importable(self):
        from backend.storage.usb_storage_manager import usb_storage_manager
        from backend.storage.storage_manager import storage_manager
        from backend.config.storage_config import storage_config
        from backend.automation.workflow_templates import workflow_templates
        from backend.automation.trigger_engine import trigger_engine
        from backend.automation.rollercoin_scheduler import rollercoin_scheduler
        from backend.automation.recovery_automation import recovery_automation
        from backend.automation.browser_pool import browser_pool
        assert usb_storage_manager is not None
        assert storage_manager is not None
        assert storage_config is not None
        assert workflow_templates is not None
        assert trigger_engine is not None
        assert rollercoin_scheduler is not None
        assert recovery_automation is not None
        assert browser_pool is not None

    def test_daemon_extended_importable(self):
        from backend.daemon.aura_daemon_extended import AuraDaemonExtended, aura_daemon_extended
        d = AuraDaemonExtended()
        assert d.task_count == 13
        assert aura_daemon_extended is not None
