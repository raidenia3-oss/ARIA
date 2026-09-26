"""BLOQUE 71 - Local Hardware Telemetry, Resource Governor & Performance Profiler.

Engine that collects local hardware metrics (CPU, RAM, GPU, disk, net, temperature),
evaluates saturation against configurable thresholds, and issues dynamic throttle/pause
decisions for tracked workloads. 100% local: no cloud telemetry, no external monitoring.
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
import threading
import time
from collections import deque
from typing import Any, Callable, Dict, List, Optional, Tuple

from backend.telemetry.models import (
    GovernorAction,
    GovernorDecision,
    GovernorPolicy,
    GovernorReport,
    GovernorThresholds,
    HardwareSnapshot,
    SensorStatus,
    WorkloadItem,
)

logger = logging.getLogger("AURAGovernor")

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


_PSUTIL = None
try:
    import psutil as _PSUTIL
except Exception:
    _PSUTIL = None

_WIN = platform.system() == "Windows"


def _run_ps(args, timeout=4):
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", args],
            capture_output=True, text=True, timeout=timeout,
        )
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except Exception as exc:
        return "", repr(exc), 1


class TelemetryCollector:
    """Collects local hardware telemetry snapshots using psutil + OS-native probes."""

    def __init__(self, sample_interval_s: float = 1.0):
        self.sample_interval_s = max(0.2, float(sample_interval_s))
        self._prev_cpu_times = None
        self._prev_disk = None
        self._prev_net = None
        self._prev_t = None
        self._cpu_cache = deque(maxlen=60)
        self._ram_cache = deque(maxlen=60)
        self._gpu_cache = deque(maxlen=60)
        self._temp_cache = deque(maxlen=60)
        self._sensors: Dict[str, SensorStatus] = {}
        self._host_os = f"{platform.system()} {platform.release()}"
        self._host_machine = platform.machine() or "unknown"
        self._host_processor = platform.processor() or "unknown"
        self._cpu_name = ""
        self._probe_cpu_name()
        self._snapshots: deque = deque(maxlen=200)

    def _probe_cpu_name(self):
        try:
            if _WIN:
                out, _, _ = _run_ps(
                    "Get-CimInstance Win32_Processor | Select-Object -First 1 Name | Format-List"
                )
                for line in out.splitlines():
                    if "Name" in line and ":" in line:
                        self._cpu_name = line.split(":", 1)[1].strip()
                        break
        except Exception:
            pass

    def _cpu(self):
        sensors = {}
        if _PSUTIL is None:
            sensors["cpu"] = SensorStatus.UNAVAILABLE
            return 0.0, [], 0, 0, 0.0, 0.0, 0.0, sensors
        try:
            per = _PSUTIL.cpu_percent(percpu=True, interval=0.15)
            total = sum(per) / max(1, len(per))
            self._cpu_cache.append(total)
            logical = _PSUTIL.cpu_count(logical=True) or 0
            physical = _PSUTIL.cpu_count(logical=False) or logical
            try:
                load1, load5, load15 = _PSUTIL.getloadavg()
            except Exception:
                load1 = load5 = load15 = total
            sensors["cpu"] = SensorStatus.OK
            return total, [round(x, 1) for x in per], logical, physical, load1, load5, load15, sensors
        except Exception:
            sensors["cpu"] = SensorStatus.ERROR
            return 0.0, [], 0, 0, 0.0, 0.0, 0.0, sensors

    def _ram(self):
        sensors = {}
        if _PSUTIL is None:
            sensors["ram"] = SensorStatus.UNAVAILABLE
            return 0.0, 0.0, 0.0, 0.0, 0.0, sensors
        try:
            vm = _PSUTIL.virtual_memory()
            sw = _PSUTIL.swap_memory()
            self._ram_cache.append(vm.percent)
            sensors["ram"] = SensorStatus.OK
            sensors["swap"] = SensorStatus.OK
            return (round(vm.percent, 1), round(vm.used / 1024 ** 3, 2),
                    round(vm.total / 1024 ** 3, 2), round(vm.available / 1024 ** 3, 2),
                    round(sw.percent, 1), sensors)
        except Exception:
            sensors["ram"] = SensorStatus.ERROR
            return 0.0, 0.0, 0.0, 0.0, 0.0, sensors

    def _disk(self):
        sensors = {}
        if _PSUTIL is None:
            sensors["disk"] = SensorStatus.UNAVAILABLE
            return 0.0, 0.0, 0.0, sensors
        try:
            now = time.time()
            du = _PSUTIL.disk_usage("/")
            io_ = _PSUTIL.disk_io_counters() or _PSUTIL.DiskIOCounters()
            read_s = write_s = 0.0
            if self._prev_disk is not None and self._prev_t:
                dt = max(1e-6, now - self._prev_t)
                read_s = max(0.0, (io_.read_bytes - self._prev_disk.read_bytes) / dt)
                write_s = max(0.0, (io_.write_bytes - self._prev_disk.write_bytes) / dt)
            self._prev_disk = io_
            self._prev_t = now
            sensors["disk"] = SensorStatus.OK
            return round(du.percent, 1), round(read_s, 1), round(write_s, 1), sensors
        except Exception:
            sensors["disk"] = SensorStatus.ERROR
            return 0.0, 0.0, 0.0, sensors

    def _net(self):
        sensors = {}
        if _PSUTIL is None:
            sensors["net"] = SensorStatus.UNAVAILABLE
            return 0.0, 0.0, sensors
        try:
            now = time.time()
            n = _PSUTIL.net_io_counters()
            sent_s = recv_s = 0.0
            if self._prev_net is not None and self._prev_t:
                dt = max(1e-6, now - self._prev_t)
                sent_s = max(0.0, (n.bytes_sent - self._prev_net.bytes_sent) / dt)
                recv_s = max(0.0, (n.bytes_recv - self._prev_net.bytes_recv) / dt)
            self._prev_net = n
            sensors["net"] = SensorStatus.OK
            return round(sent_s, 1), round(recv_s, 1), sensors
        except Exception:
            sensors["net"] = SensorStatus.ERROR
            return 0.0, 0.0, sensors

    def _gpu(self):
        sensors = {}
        if not _WIN:
            sensors["gpu"] = SensorStatus.NOT_SUPPORTED
            return None, None, None, None, None, None, sensors
        try:
            out, _, rc = _run_ps(
                "Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion,AdapterRAM | ConvertTo-Json -Compress"
            )
            if rc != 0 or not out:
                sensors["gpu"] = SensorStatus.ERROR
                return None, None, None, None, None, None, sensors
            import json as _json
            data = _json.loads(out)
            if isinstance(data, dict):
                data = [data]
            if not data:
                sensors["gpu"] = SensorStatus.NOT_SUPPORTED
                return None, None, None, None, None, None, sensors
            first = data[0]
            name = first.get("Name")
            driver = first.get("DriverVersion")
            total_mb = None
            try:
                ram = first.get("AdapterRAM")
                if ram:
                    total_mb = round(int(ram) / (1024 * 1024), 1)
            except Exception:
                pass
            self._gpu_cache.append(name)
            sensors["gpu"] = SensorStatus.OK
            return None, None, total_mb, name, driver, None, sensors
        except Exception:
            sensors["gpu"] = SensorStatus.ERROR
            return None, None, None, None, None, None, sensors

    def _temp(self):
        sensors = {}
        if not _WIN:
            sensors["temp"] = SensorStatus.NOT_SUPPORTED
            return None, sensors
        try:
            out, _, rc = _run_ps(
                "Get-CimInstance Win32_Processor | Select-Object LoadPercentage | ConvertTo-Json -Compress"
            )
            if rc != 0 or not out:
                sensors["temp"] = SensorStatus.ERROR
                return None, sensors
            import json as _json
            data = _json.loads(out)
            if isinstance(data, dict):
                data = [data]
            load = 0.0
            for d in data:
                v = d.get("LoadPercentage")
                if v is not None:
                    load = max(load, float(v))
            self._temp_cache.append(load)
            sensors["temp"] = SensorStatus.OK
            return round(load, 1), sensors
        except Exception:
            sensors["temp"] = SensorStatus.ERROR
            return None, sensors

    def snapshot(self) -> HardwareSnapshot:
        ts = time.time()
        cpu, per, log, phy, l1, l5, l15, s1 = self._cpu()
        ram, used, total, avail, swap, s2 = self._ram()
        disk_pct, dr, dw, s3 = self._disk()
        ns, nr, s4 = self._net()
        gpu_pct, gpu_used, gpu_total, gpu_name, gpu_driver, gpu_temp, s5 = self._gpu()
        temp, s6 = self._temp()
        sensors = {**s1, **s2, **s3, **s4, **s5, **s6}
        snap = HardwareSnapshot(
            timestamp=ts,
            cpu_percent=round(cpu, 1),
            cpu_per_core=per,
            cpu_cores_logical=log,
            cpu_cores_physical=phy,
            cpu_load_1m=round(l1, 1),
            cpu_load_5m=round(l5, 1),
            cpu_load_15m=round(l15, 1),
            cpu_temp_c=temp,
            ram_percent=ram,
            ram_used_gb=used,
            ram_total_gb=total,
            ram_available_gb=avail,
            swap_percent=swap,
            disk_percent=disk_pct,
            disk_read_bytes_s=dr,
            disk_write_bytes_s=dw,
            net_bytes_sent_s=ns,
            net_bytes_recv_s=nr,
            gpu_percent=gpu_pct,
            gpu_memory_used_mb=gpu_used,
            gpu_memory_total_mb=gpu_total,
            gpu_name=gpu_name,
            gpu_driver=gpu_driver,
            gpu_temp_c=gpu_temp,
            sensors=sensors,
            host_os=self._host_os,
            host_machine=self._host_machine,
            host_processor=self._host_processor,
        )
        self._snapshots.append(snap)
        return snap

    def avg_cpu(self, n=5):
        vals = list(self._cpu_cache)[-n:]
        return round(sum(vals) / max(1, len(vals)), 1)

    def avg_ram(self, n=5):
        vals = list(self._ram_cache)[-n:]
        return round(sum(vals) / max(1, len(vals)), 1)



class GovernorEngine:
    """Evaluates hardware saturation and issues throttle/pause decisions."""

    def __init__(
        self,
        thresholds: Optional[GovernorThresholds] = None,
        policy: Optional[GovernorPolicy] = None,
        collector: Optional[TelemetryCollector] = None,
        on_action: Optional[Callable[[GovernorReport], None]] = None,
    ):
        self.thresholds = thresholds or GovernorThresholds()
        self.policy = policy or GovernorPolicy()
        self.collector = collector or TelemetryCollector(
            sample_interval_s=self.thresholds.sample_interval_s,
        )
        self.on_action = on_action
        self._workloads: Dict[str, WorkloadItem] = {}
        self._last_eval = 0.0
        self._last_decision = GovernorDecision.ALLOW
        self._last_action = GovernorAction.NONE
        self._history: deque = deque(maxlen=200)
        self._lock = threading.RLock()

    def register_workload(self, workload: WorkloadItem) -> None:
        with self._lock:
            workload.updated_at = time.time()
            self._workloads[workload.workload_id] = workload

    def unregister_workload(self, workload_id: str) -> None:
        with self._lock:
            self._workloads.pop(workload_id, None)

    def set_policy(self, policy: GovernorPolicy) -> None:
        with self._lock:
            policy.updated_at = time.time()
            self.policy = policy

    def set_thresholds(self, thresholds: GovernorThresholds) -> None:
        with self._lock:
            self.thresholds = thresholds
            self.collector.sample_interval_s = max(0.2, thresholds.sample_interval_s)

    def get_workloads(self) -> List[WorkloadItem]:
        with self._lock:
            return list(self._workloads.values())

    def _classify(self, snap: HardwareSnapshot) -> Tuple[GovernorDecision, GovernorAction, List[str], str]:
        t = self.thresholds
        reasons: List[str] = []
        severity = "info"
        decision = GovernorDecision.ALLOW
        action = GovernorAction.NONE

        temp = snap.cpu_temp_c if snap.cpu_temp_c is not None else None
        if snap.cpu_percent >= t.cpu_critical or (temp is not None and temp >= t.temp_critical_c):
            decision = GovernorDecision.PAUSE
            action = GovernorAction.PAUSE
            severity = "critical"
            reasons.append(f"cpu={snap.cpu_percent}% critical")
            if temp is not None:
                reasons.append(f"temp={temp}C critical")
        elif snap.cpu_percent >= t.cpu_throttle or (temp is not None and temp >= t.temp_throttle_c):
            decision = GovernorDecision.THROTTLE
            action = GovernorAction.THROTTLE
            severity = "warning"
            reasons.append(f"cpu={snap.cpu_percent}% throttle")
            if temp is not None:
                reasons.append(f"temp={temp}C throttle")
        elif snap.ram_percent >= t.ram_critical or snap.swap_percent >= t.swap_critical:
            decision = GovernorDecision.DEFER
            action = GovernorAction.THROTTLE
            severity = "critical"
            reasons.append(f"ram={snap.ram_percent}% critical")
            reasons.append(f"swap={snap.swap_percent}% critical")
        elif snap.ram_percent >= t.ram_throttle or snap.swap_percent >= t.swap_throttle:
            if decision == GovernorDecision.ALLOW:
                decision = GovernorDecision.THROTTLE
                action = GovernorAction.THROTTLE
                severity = "warning"
            reasons.append(f"ram={snap.ram_percent}% high")
            reasons.append(f"swap={snap.swap_percent}% high")
        elif snap.disk_percent >= t.disk_throttle:
            if decision == GovernorDecision.ALLOW:
                decision = GovernorDecision.DEFER
                action = GovernorAction.THROTTLE
                severity = "warning"
            reasons.append(f"disk={snap.disk_percent}% high")
        elif snap.cpu_percent >= t.cpu_warn or snap.ram_percent >= t.ram_warn:
            if decision == GovernorDecision.ALLOW:
                decision = GovernorDecision.ALLOW
                action = GovernorAction.WARN
                severity = "info"
            reasons.append(f"cpu={snap.cpu_percent}% warn")
            reasons.append(f"ram={snap.ram_percent}% warn")
        return decision, action, reasons, severity

    def evaluate(self) -> GovernorReport:
        snap = self.collector.snapshot()
        decision, action, reasons, severity = self._classify(snap)
        with self._lock:
            self._last_eval = time.time()
            self._last_decision = decision
            self._last_action = action
            affected = []
            for wl in self._workloads.values():
                wl.updated_at = time.time()
                if decision == GovernorDecision.PAUSE:
                    wl.state = "paused"
                elif decision == GovernorDecision.THROTTLE:
                    wl.state = "throttled"
                elif decision == GovernorDecision.DEFER:
                    wl.state = "deferred"
                else:
                    wl.state = "running"
                affected.append(wl.workload_id)
            report = GovernorReport(
                timestamp=time.time(),
                snapshot=snap,
                thresholds=self.thresholds,
                policy=self.policy,
                decision=decision,
                action=action,
                severity=severity,
                reasons=reasons,
                affected_workloads=affected,
                avg_cpu_5m=self.collector.avg_cpu(5),
                avg_ram_5m=self.collector.avg_ram(5),
            )
            self._history.append(report)
            if self.on_action:
                try:
                    self.on_action(report)
                except Exception as exc:
                    logger.warning("on_action callback failed: %s", exc)
            return report


class _GovernorState:
    """Thread-safe singleton state for the governor engine."""

    def __init__(self):
        self.engine: Optional[GovernorEngine] = None
        self.lock = threading.RLock()

    def get(self) -> GovernorEngine:
        with self.lock:
            if self.engine is None:
                self.engine = GovernorEngine()
            return self.engine

    def reset(self) -> None:
        with self.lock:
            self.engine = None

    def set(self, engine: GovernorEngine) -> None:
        with self.lock:
            self.engine = engine


_state = _GovernorState()


def get_governor() -> GovernorEngine:
    return _state.get()


def reset_governor() -> None:
    _state.reset()


def set_governor(engine: GovernorEngine) -> None:
    _state.set(engine)


def enable_autostart(interval_s: float = 2.0) -> GovernorEngine:
    """Enable periodic background evaluation of the governor engine."""
    engine = get_governor()
    engine.set_thresholds(GovernorThresholds(sample_interval_s=interval_s))

    def _loop():
        while not _stop_event.is_set():
            try:
                engine.evaluate()
            except Exception as exc:
                logger.warning("governor evaluate failed: %s", exc)
            time.sleep(max(0.2, interval_s))

    global _stop_event
    _stop_event = threading.Event()
    t = threading.Thread(target=_loop, daemon=True, name="governor-autostart")
    t.start()
    return engine


def disable_autostart() -> None:
    global _stop_event
    if "_stop_event" in globals() and _stop_event is not None:
        _stop_event.set()


_stop_event: Optional[threading.Event] = None


# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------

from fastapi import APIRouter, HTTPException  # noqa: E402

router = APIRouter(prefix="/api/telemetry", tags=["telemetry-governor"])


@router.get("/resources", summary="Current hardware snapshot")
async def get_resources():
    gov = get_governor()
    snap = gov.collector.snapshot()
    return snap.to_dict()


@router.get("/resources/history", summary="Recent hardware snapshots")
async def get_resources_history(limit: int = 20):
    gov = get_governor()
    limit = max(1, min(limit, 200))
    items = list(gov.collector._snapshots)[-limit:]
    return {"count": len(items), "items": [s.to_dict() for s in items]}


@router.get("/workloads", summary="Registered workloads")
async def list_workloads():
    gov = get_governor()
    return {"workloads": [w.to_dict() for w in gov.get_workloads()]}


@router.post("/workloads", summary="Register a workload")
async def register_workload(item: WorkloadItem):
    gov = get_governor()
    gov.register_workload(item)
    return {"registered": item.workload_id}


@router.delete("/workloads/{workload_id}", summary="Unregister a workload")
async def unregister_workload(workload_id: str):
    gov = get_governor()
    gov.unregister_workload(workload_id)
    return {"unregistered": workload_id}


@router.get("/policy", summary="Current governor policy")
async def get_policy():
    gov = get_governor()
    return gov.policy.to_dict()


@router.put("/policy", summary="Update governor policy")
async def update_policy(policy: GovernorPolicy):
    gov = get_governor()
    gov.set_policy(policy)
    return {"updated": True, "policy": gov.policy.to_dict()}


@router.get("/thresholds", summary="Current governor thresholds")
async def get_thresholds():
    gov = get_governor()
    return gov.thresholds.to_dict()


@router.put("/thresholds", summary="Update governor thresholds")
async def update_thresholds(thresholds: GovernorThresholds):
    gov = get_governor()
    gov.set_thresholds(thresholds)
    return {"updated": True, "thresholds": gov.thresholds.to_dict()}


@router.post("/evaluate", summary="Force a governor evaluation")
async def evaluate_now():
    gov = get_governor()
    report = gov.evaluate()
    return report.to_dict()


@router.get("/decisions", summary="Recent governor decisions")
async def recent_decisions(limit: int = 20):
    gov = get_governor()
    limit = max(1, min(limit, 200))
    items = list(gov._history)[-limit:]
    return {"count": len(items), "decisions": [d.to_dict() for d in items]}


@router.get("/status", summary="Governor engine status")
async def governor_status():
    gov = get_governor()
    return {
        "enabled": True,
        "workloads": len(gov._workloads),
        "last_decision": gov._last_decision.value,
        "last_action": gov._last_action.value,
        "history_size": len(gov._history),
        "policy": gov.policy.to_dict(),
        "thresholds": gov.thresholds.to_dict(),
    }
