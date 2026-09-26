"""BLOQUE 71 - Unit tests for TelemetryCollector and GovernorEngine."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from backend.telemetry.governor import (
    GovernorAction,
    GovernorDecision,
    GovernorEngine,
    GovernorPolicy,
    GovernorThresholds,
    TelemetryCollector,
    WorkloadItem,
    get_governor,
    reset_governor,
)
from backend.telemetry.models import HardwareSnapshot, SensorStatus


def test_imports():
    assert TelemetryCollector is not None
    assert GovernorEngine is not None


def test_snapshot_structure():
    c = TelemetryCollector(sample_interval_s=0.2)
    snap = c.snapshot()
    assert isinstance(snap, HardwareSnapshot)
    assert snap.cpu_percent >= 0
    assert snap.ram_percent >= 0
    assert snap.disk_percent >= 0
    assert isinstance(snap.sensors, dict)


def test_snapshot_to_dict():
    c = TelemetryCollector(sample_interval_s=0.2)
    snap = c.snapshot()
    d = snap.to_dict()
    assert "cpu_percent" in d
    assert "ram_percent" in d
    assert "sensors" in d


def test_avg_methods():
    c = TelemetryCollector(sample_interval_s=0.2)
    c.snapshot()
    c.snapshot()
    assert c.avg_cpu() >= 0
    assert c.avg_ram() >= 0


def test_governor_allow_when_idle():
    reset_governor()
    gov = GovernorEngine()
    gov.set_thresholds(GovernorThresholds(cpu_throttle=99.0, ram_throttle=99.0))
    report = gov.evaluate()
    assert report.decision in (GovernorDecision.ALLOW, GovernorDecision.DEFER)


def test_governor_critical_cpu():
    reset_governor()
    gov = GovernorEngine()
    gov.set_thresholds(GovernorThresholds(cpu_critical=1.0, cpu_throttle=1.0))
    snap = HardwareSnapshot(
        timestamp=0.0,
        cpu_percent=50.0,
        cpu_per_core=[],
        cpu_cores_logical=4,
        cpu_cores_physical=2,
        cpu_load_1m=50.0,
        cpu_load_5m=50.0,
        cpu_load_15m=50.0,
        cpu_temp_c=None,
        ram_percent=10.0,
        ram_used_gb=1.0,
        ram_total_gb=16.0,
        ram_available_gb=15.0,
        swap_percent=0.0,
        disk_percent=10.0,
        disk_read_bytes_s=0.0,
        disk_write_bytes_s=0.0,
        net_bytes_sent_s=0.0,
        net_bytes_recv_s=0.0,
        gpu_percent=None,
        gpu_memory_used_mb=None,
        gpu_memory_total_mb=None,
        gpu_name=None,
        gpu_driver=None,
        gpu_temp_c=None,
        sensors={},
        host_os="test",
        host_machine="x86_64",
        host_processor="test",
    )
    decision, action, reasons, severity = gov._classify(snap)
    assert decision == GovernorDecision.PAUSE
    assert action == GovernorAction.PAUSE
    assert severity == "critical"


def test_governor_throttle_ram():
    reset_governor()
    gov = GovernorEngine()
    gov.set_thresholds(GovernorThresholds(ram_throttle=50.0, ram_critical=99.0))
    snap = HardwareSnapshot(
        timestamp=0.0,
        cpu_percent=10.0,
        cpu_per_core=[],
        cpu_cores_logical=4,
        cpu_cores_physical=2,
        cpu_load_1m=10.0,
        cpu_load_5m=10.0,
        cpu_load_15m=10.0,
        cpu_temp_c=None,
        ram_percent=80.0,
        ram_used_gb=12.0,
        ram_total_gb=16.0,
        ram_available_gb=4.0,
        swap_percent=10.0,
        disk_percent=10.0,
        disk_read_bytes_s=0.0,
        disk_write_bytes_s=0.0,
        net_bytes_sent_s=0.0,
        net_bytes_recv_s=0.0,
        gpu_percent=None,
        gpu_memory_used_mb=None,
        gpu_memory_total_mb=None,
        gpu_name=None,
        gpu_driver=None,
        gpu_temp_c=None,
        sensors={},
        host_os="test",
        host_machine="x86_64",
        host_processor="test",
    )
    decision, action, reasons, severity = gov._classify(snap)
    assert decision == GovernorDecision.THROTTLE
    assert action == GovernorAction.THROTTLE


def test_workload_register_unregister():
    reset_governor()
    gov = GovernorEngine()
    wl = WorkloadItem(workload_id="w1", name="test", priority=5)
    gov.register_workload(wl)
    assert len(gov.get_workloads()) == 1
    gov.unregister_workload("w1")
    assert len(gov.get_workloads()) == 0


def test_singleton():
    reset_governor()
    g1 = get_governor()
    g2 = get_governor()
    assert g1 is g2
    reset_governor()
    g3 = get_governor()
    assert g3 is not g1


def test_policy_thresholds_update():
    reset_governor()
    gov = GovernorEngine()
    p = GovernorPolicy(web_priority=90)
    gov.set_policy(p)
    assert gov.policy.web_priority == 90
    t = GovernorThresholds(cpu_warn=30.0)
    gov.set_thresholds(t)
    assert gov.thresholds.cpu_warn == 30.0


def test_history():
    reset_governor()
    gov = GovernorEngine()
    gov.evaluate()
    gov.evaluate()
    assert len(gov._history) >= 1


def test_concurrent_register():
    import threading

    reset_governor()
    gov = GovernorEngine()
    errors = []

    def worker(i):
        try:
            gov.register_workload(WorkloadItem(workload_id=f"w{i}", name=f"t{i}"))
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert len(gov.get_workloads()) == 20
