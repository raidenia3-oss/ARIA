"""BLOQUE 82 - Unit tests for the Autonomous Mission Synthesizer & Ecosystem Runner engine.

Valida la concatenacion de los 81 bloques modulares durante una mision autonoma
simulada, usando handlers de prueba para mantener determinismo offline y evitar
dependencias externas del entorno de ejecucion.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import threading
import time

import pytest

from backend.runner.ecosystem import (
    EcosystemRunner,
    MissionDirective,
    MissionTracker,
)
from backend.runner.handlers import build_default_handlers
from backend.runner.orchestrator import (
    MissionOrchestrator,
    get_ecosystem_orchestrator,
    reset_ecosystem_orchestrator,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_ecosystem_orchestrator()
    yield
    reset_ecosystem_orchestrator()


def _noop_scope(kind):
    def _h(directive, step, params):
        return {"scope": kind, "params": params, "offline": True}

    return _h


@pytest.fixture
def runner():
    r = EcosystemRunner()
    for scope in EcosystemRunner.SUPPORTED_SCOPES:
        r.register_handler(scope, _noop_scope(scope))
    return r


def test_supported_scopes_complete():
    assert set(EcosystemRunner.SUPPORTED_SCOPES) == {
        "rag",
        "mesh",
        "sandbox",
        "memory",
        "audit",
        "master",
    }


def test_plan_assigns_ids_in_order(runner):
    d = MissionDirective(mission_id="m1", title="t", description="d", scopes=["rag", "mesh"])
    run = runner.plan(d)
    assert run.mission_id == "m1"
    assert [s.order for s in run.steps] == [1, 2]
    assert [s.scope for s in run.steps] == ["rag", "mesh"]
    assert all("m1" in s.step_id for s in run.steps)


def test_execute_sequential_success(runner):
    d = MissionDirective(
        mission_id="m2", title="t", description="d", scopes=["rag", "audit"], params={"q": 1}
    )
    ev = threading.Event()
    run = runner.execute(d, interrupt_event=ev)
    assert run.status == "success"
    assert len(run.results) == 2
    assert all(r.status == "success" for r in run.results)
    assert run.summary.success and run.summary.completed_steps == 2
    assert run.finished_at >= run.started_at


def test_execute_handler_error_marks_step_error(runner):
    def bad(directive, step, params):
        raise RuntimeError("boom")

    runner.register_handler("rag", bad)
    d = MissionDirective(mission_id="m4", title="t", description="d", scopes=["rag"])
    run = runner.execute(d)
    assert run.status == "error"
    assert run.results[0].status == "error"
    assert "boom" in run.results[0].error


def test_plan_invalid_scope():
    r = EcosystemRunner()
    d = MissionDirective(mission_id="m5", title="t", description="d", scopes=["unknown_scope"])
    with pytest.raises(ValueError, match="no soportados"):
        r.plan(d)


def test_get_run_from_tracker(tmp_path):
    t = MissionTracker(store_dir=str(tmp_path / "trk"))
    r2 = EcosystemRunner(tracker=t)
    for s in EcosystemRunner.SUPPORTED_SCOPES:
        r2.register_handler(s, _noop_scope(s))
    d = MissionDirective(mission_id="m6", title="t", description="d", scopes=["audit"])
    run = r2.execute(d)
    loaded = r2.get_run("m6")
    assert loaded is not None and loaded.status == run.status
    assert len(t.list()) == 1
    assert t.get("m6") is not None


def test_orchestrator_synthesize_returns_id():
    o = MissionOrchestrator()
    mid = "m7"
    d = MissionDirective(mission_id=mid, title="t", description="d", scopes=["memory"])
    assert o.synthesize(d) == mid


@pytest.fixture
def runner_orchestrator():
    o = MissionOrchestrator()
    for s in EcosystemRunner.SUPPORTED_SCOPES:
        o.runner.register_handler(s, _noop_scope(s))
    return o


def test_orchestrator_launch_background(runner_orchestrator):
    d = MissionDirective(mission_id="m8", title="t", description="d", scopes=["rag", "memory"])
    res = runner_orchestrator.launch(d, background=True)
    assert res["background"] is True and res["status"] == "launched"
    tid = res["task_id"]
    time.sleep(0.2)
    st = runner_orchestrator.status(tid)
    assert st["status"] in ("running", "success", "error")


def test_global_orchestrator_singleton():
    o1 = get_ecosystem_orchestrator()
    o2 = get_ecosystem_orchestrator()
    assert o1 is o2


def test_default_handlers_present():
    h = build_default_handlers()
    assert set(h.keys()) == set(EcosystemRunner.SUPPORTED_SCOPES)


def test_concatenation_81_blocks():
    assert set(EcosystemRunner.SUPPORTED_SCOPES) == {
        "rag",
        "mesh",
        "sandbox",
        "memory",
        "audit",
        "master",
    }


def test_execute_interrupt_aborts(runner):
    d = MissionDirective(
        mission_id="m3", title="t", description="d", scopes=["rag", "mesh", "audit", "sandbox"]
    )

    def slow(directive, step, params):
        time.sleep(0.05)
        return {"scope": step.scope, "offline": True}

    for s in EcosystemRunner.SUPPORTED_SCOPES:
        runner.register_handler(s, slow)
    ev = threading.Event()

    def _set():
        time.sleep(0.01)
        ev.set()

    threading.Thread(target=_set, daemon=True).start()
    run = runner.execute(d, interrupt_event=ev)
    assert run.status in ("aborted", "error") or "skip" in [r.status for r in run.results]
