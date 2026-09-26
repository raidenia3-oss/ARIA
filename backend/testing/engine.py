"""BLOQUE 103 - Motor E2E (parte 1/2): MatrixEngine."""
from __future__ import annotations

import concurrent.futures as cf
import logging
import threading
import time
from typing import Callable, Dict, List, Optional

from backend.testing.models import MatrixReport, StepResult
from backend.testing.steps import STEP_FNS

logger = logging.getLogger("AURA.Testing103")
DEFAULT_TIMEOUT_S = 10.0
MAX_AGENTS = 64
MAX_OPS_PER_AGENT = 50


def _timed(fn: Callable[[], Dict]) -> StepResult:
    t0 = time.perf_counter()
    try:
        detail = fn() or {}
        dt = (time.perf_counter() - t0) * 1000.0
        return StepResult(step="", ok=True, latency_ms=dt, detail=detail)
    except Exception as exc:
        dt = (time.perf_counter() - t0) * 1000.0
        return StepResult(step="", ok=False, latency_ms=dt,
                          error=str(exc)[:500])


class MatrixEngine:
    def __init__(self, timeout_s: float = DEFAULT_TIMEOUT_S) -> None:
        self.timeout_s = max(0.05, float(timeout_s))
        self._lock = threading.RLock()
        self._last: Optional[MatrixReport] = None
        self._history: List[MatrixReport] = []

    def run_chain(self, steps: Optional[List[str]] = None) -> MatrixReport:
        from backend.testing.models import ALL_CHAIN_STEPS
        wanted = steps or list(ALL_CHAIN_STEPS)
        rep = MatrixReport(chain="full_ecosystem")
        with cf.ThreadPoolExecutor(max_workers=1,
                                   thread_name_prefix="e2e103") as pool:
            for name in wanted:
                fn = STEP_FNS.get(name)
                if fn is None:
                    rep.steps.append(StepResult(step=name, ok=False,
                                               error="unknown_step"))
                    continue
                fut = pool.submit(_timed, fn)
                try:
                    sr = fut.result(timeout=self.timeout_s)
                except cf.TimeoutError:
                    fut.cancel()
                    sr = StepResult(step=name, ok=False,
                                    latency_ms=self.timeout_s * 1000.0,
                                    error="step_timeout")
                except Exception as exc:
                    sr = StepResult(step=name, ok=False,
                                    latency_ms=self.timeout_s * 1000.0,
                                    error=str(exc)[:300])
                sr.step = name
                rep.steps.append(sr)
        rep.finalize()
        with self._lock:
            self._last = rep
            self._history.append(rep)
            self._history = self._history[-20:]
        try:
            from backend.refactoring.integration import emit_fusion
            emit_fusion("testing.matrix_done",
                        {"report": rep.report_id, "status": rep.status,
                         "passed": rep.passed, "failed": rep.failed},
                        severity="info" if rep.failed == 0 else "medium")
        except Exception:
            pass
        return rep

    def last(self) -> Optional[MatrixReport]:
        with self._lock:
            return self._last

    def history(self, limit: int = 10) -> List[MatrixReport]:
        with self._lock:
            return list(self._history[-max(1, limit):])

    def reset(self) -> None:
        with self._lock:
            self._last = None
            self._history.clear()


_matrix = MatrixEngine()


def get_matrix() -> MatrixEngine:
    return _matrix


def reset_matrix() -> None:
    _matrix.reset()


__all__ = ["MatrixEngine", "get_matrix", "reset_matrix", "DEFAULT_TIMEOUT_S", "MAX_AGENTS",
           "MAX_OPS_PER_AGENT"]
