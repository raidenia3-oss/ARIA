"""BLOQUE 103 - Runner de estres concurrente del enjambre (parte 2/2)."""
from __future__ import annotations

import concurrent.futures as cf
import threading
import time
from typing import Dict, List, Optional

from backend.testing.engine import MAX_AGENTS, MAX_OPS_PER_AGENT
from backend.testing.models import StressReport, _utcnow_iso

try:
    import psutil as _PSUTIL  # type: ignore
except Exception:  # pragma: no cover
    _PSUTIL = None  # type: ignore


def _avail_mb() -> float:
    try:
        if _PSUTIL is not None:
            return float(_PSUTIL.virtual_memory().available) / (1024 * 1024)
    except Exception:
        pass
    return 2048.0


def safe_max_agents(requested: int) -> int:
    avail = _avail_mb()
    budget = max(1, int((avail * 0.5) // 8))
    return max(1, min(int(requested), MAX_AGENTS, budget))


class SwarmStressRunner:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._last: Optional[StressReport] = None
        self._history: List[StressReport] = []

    def run(self, agents: int = 8, ops_per_agent: int = 10,
            inject_faults: bool = False,
            timeout_s: float = 10.0) -> StressReport:
        n_agents = safe_max_agents(agents)
        ops = max(1, min(int(ops_per_agent), MAX_OPS_PER_AGENT))
        rep = StressReport(agents=n_agents, ops_per_agent=ops)
        lat: List[float] = []
        ok = 0
        fail = 0
        deadlocks = 0
        faults = 0
        t0 = time.perf_counter()

        def _agent_op(seed: int) -> Dict:
            t = time.perf_counter()
            try:
                from backend.fusion.sensory import get_fusion_engine
                get_fusion_engine().ingest(
                    source="system", kind="stress.ping",
                    payload={"agent": seed}, severity="info")
                from backend.refactoring.integration import governor_gate
                governor_gate()
                from backend.core.aura_master_runtime import (
                    get_master_runtime)
                get_master_runtime().status()
                if inject_faults and (seed % 7 == 0):
                    raise RuntimeError("synthetic_fault_injected")
                return {"ok": True,
                        "lat": (time.perf_counter() - t) * 1000.0}
            except RuntimeError:
                raise
            except Exception:
                return {"ok": False,
                        "lat": (time.perf_counter() - t) * 1000.0}

        workers = max(1, min(n_agents, 32))
        with cf.ThreadPoolExecutor(max_workers=workers,
                                   thread_name_prefix="swarm103") as pool:
            futs = [pool.submit(_agent_op, i)
                    for i in range(n_agents * ops)]
            for f in cf.as_completed(futs, timeout=timeout_s * max(1, ops)):
                try:
                    r = f.result(timeout=timeout_s)
                    lat.append(float(r.get("lat", 0.0)))
                    if r.get("ok"):
                        ok += 1
                    else:
                        fail += 1
                except Exception as exc:
                    fail += 1
                    if "synthetic_fault" in str(exc):
                        faults += 1
                    elif "Timeout" in type(exc).__name__:
                        deadlocks += 1

        dt = max(0.001, time.perf_counter() - t0)
        rep.total_ops = n_agents * ops
        rep.ok_ops = ok
        rep.failed_ops = fail
        rep.deadlocks = deadlocks
        rep.faults_injected = faults if inject_faults else 0
        if lat:
            rep.avg_latency_ms = sum(lat) / len(lat)
            rep.p95_latency_ms = float(
                sorted(lat)[min(len(lat) - 1, int(len(lat) * 0.95))])
        rep.throughput_ops = rep.total_ops / dt
        rep.finished_at = _utcnow_iso()
        rep.status = ("passed" if fail == 0 else
                      ("partial" if ok > 0 else "failed"))
        with self._lock:
            self._last = rep
            self._history.append(rep)
            self._history = self._history[-20:]
        try:
            from backend.refactoring.integration import emit_fusion
            emit_fusion("testing.stress_done",
                        {"report": rep.report_id, "status": rep.status,
                         "ok": ok, "failed": fail,
                         "deadlocks": deadlocks}, severity="info")
        except Exception:
            pass
        return rep

    def last(self) -> Optional[StressReport]:
        with self._lock:
            return self._last

    def history(self, limit: int = 10) -> List[StressReport]:
        with self._lock:
            return list(self._history[-max(1, limit):])

    def reset(self) -> None:
        with self._lock:
            self._last = None
            self._history.clear()


_stress = SwarmStressRunner()


def get_stress() -> SwarmStressRunner:
    return _stress


def reset_stress() -> None:
    _stress.reset()


__all__ = ["SwarmStressRunner", "get_stress", "reset_stress",
           "safe_max_agents"]
