"""BLOQUE 70 - Local Self-Evolution & Dynamic Code Patching Engine tests."""

import os

import pytest

from backend.evolution.models import PatchStatus, PatchType
from backend.evolution.patcher import (
    AuditFinding,
    CodeAuditor,
    EvolutionPatchEngine,
    PatchSynthesizer,
    SandboxTester,
    get_engine,
    reset_engine,
    set_engine,
)

_TARGET = os.path.join("backend", "_b70_test_mod.py")
_OUTSIDE = os.path.join("C:", os.sep, "outside.py")


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_EVOLUTION70_DIR", str(tmp_path / "ev70"))
    reset_engine()
    eng = EvolutionPatchEngine()
    set_engine(eng)
    with open(_TARGET, "w", encoding="utf-8") as fh:
        fh.write("def f():\n    return 1\n")
    yield eng
    reset_engine()
    if os.path.exists(_TARGET):
        os.remove(_TARGET)


def test_authorized_and_forbidden():
    synth = PatchSynthesizer()
    assert synth.synthesize_manual("backend/foo.py", "x", "y", "d") is not None
    assert synth.synthesize_manual("backend/main.py", "x", "y", "d") is None
    assert synth.synthesize_manual("backend/evolution/patcher.py", "x", "y", "d") is None
    assert synth.synthesize_manual(_OUTSIDE, "x", "y", "d") is None


def test_syntax_rejects_bad(engine):
    p = engine.propose_manual("backend/foo.py", "x", "def bad(:\n    pass", "d")
    assert p is None


def test_propose_and_sandbox(engine):
    p = engine.propose_manual(
        _TARGET, "def f():\n    return 1\n", "def f():\n    return 2\n", "fix", PatchType.BUGFIX
    )
    assert p is not None
    assert p.patch_type == PatchType.BUGFIX
    result = engine.test_patch(p.patch_id)
    assert result["outcome"] == "passed"
    assert p.status == PatchStatus.SANDBOX_PASSED


def test_apply_and_rollback(engine):
    p = engine.propose_manual(
        _TARGET, "def f():\n    return 1\n", "def f():\n    return 2\n", "fix"
    )
    engine.test_patch(p.patch_id)
    applied = engine.apply_patch(p.patch_id, run_sandbox=False)
    assert applied.status == PatchStatus.APPLIED
    assert open(_TARGET, encoding="utf-8").read() == "def f():\n    return 2\n"
    rolled = engine.rollback_patch(p.patch_id)
    assert rolled.status == PatchStatus.ROLLED_BACK
    assert open(_TARGET, encoding="utf-8").read() == "def f():\n    return 1\n"


def test_apply_rejects_when_old_missing(engine):
    p = engine.propose_manual(_TARGET, "NOT_PRESENT", "def f():\n    return 2\n", "fix")
    engine.test_patch(p.patch_id)
    applied = engine.apply_patch(p.patch_id, run_sandbox=False)
    assert applied.status == PatchStatus.REJECTED


def test_audit_finds_issues(engine, tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("eval('1+1')\nprint('x')\n", encoding="utf-8")
    findings = engine.audit(str(tmp_path), max_files=10)
    cats = {f.category for f in findings}
    assert "security" in cats
    assert "style" in cats


def test_audit_traces(engine):
    traces = [{"file": "backend/x.py", "line": 12, "message": "KeyError on foo"}]
    findings = engine.audit_traces(traces)
    assert len(findings) == 1
    assert findings[0].category == "logic"


def test_singleton_and_status(engine):
    assert get_engine() is engine
    st = engine.status()
    assert st["status"] == "ok"
    assert "patches_total" in st


def test_list_patches_filter(engine):
    p1 = engine.propose_manual(
        _TARGET, "def f():\n    return 1\n", "def f():\n    return 2\n", "f1"
    )
    p2 = engine.propose_manual(
        _TARGET, "def f():\n    return 2\n", "def f():\n    return 3\n", "f2"
    )
    engine.test_patch(p1.patch_id)
    applied = engine.apply_patch(p1.patch_id, run_sandbox=False)
    assert applied.status == PatchStatus.APPLIED
    all_p = engine.list_patches()
    assert len(all_p) == 2
    applied_p = engine.list_patches(status=PatchStatus.APPLIED)
    assert len(applied_p) == 1
    engine.rollback_patch(p1.patch_id)


def test_forbidden_target_not_applied(engine, tmp_path):
    target = tmp_path / "main.py"
    target.write_text("print('hi')\n", encoding="utf-8")
    p = engine.propose_manual(str(target), "print('hi')\n", "print('bye')\n", "x")
    assert p is None


def test_hotreload_snapshot_rollback(engine):
    snap = engine.reload.snapshot(_TARGET)
    assert snap is not None
    with open(_TARGET, "w", encoding="utf-8") as fh:
        fh.write("def f():\n    return 9\n")
    assert engine.reload.rollback(_TARGET) is True
    assert open(_TARGET, encoding="utf-8").read() == "def f():\n    return 1\n"
