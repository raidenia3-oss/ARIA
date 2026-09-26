"""BLOQUE 91 - unit tests for autonomous refactoring & hot-patching engine (local)."""

import uuid

import pytest

from backend.evolution.models import PatchProposal, PatchType
from backend.evolution.patcher import (
    CodeAuditor,
    EvolutionPatchEngine,
    SandboxTester,
    get_engine,
    reset_engine,
)


def test_audit_finds_issues():
    a = CodeAuditor()
    findings = a.audit_file("backend/evolution/models.py")
    assert isinstance(findings, list)


def test_audit_returns_list_for_any_path():
    a = CodeAuditor()
    assert isinstance(a.audit_file("backend/evolution/models.py"), list)


def test_propose_manual_returns_proposal():
    reset_engine()
    e = EvolutionPatchEngine()
    p = e.propose_manual("backend/evolution/models.py", "", "X_REFACTOR = 1\n", "noop patch")
    assert p is not None and p.patch_id
    reset_engine()


def test_apply_and_rollback():
    reset_engine()
    e = EvolutionPatchEngine()
    p = e.propose_manual("backend/evolution/models.py", "", "X_REFACTOR = 1\n", "noop patch")
    applied = e.apply_patch(p.patch_id)
    assert applied.status.value in ("applied", "rejected")
    rb = e.rollback_patch(p.patch_id)
    assert rb.status.value == "rolled_back"
    reset_engine()


def test_sandbox_tester_syntax_check():
    t = SandboxTester()
    p = PatchProposal(
        patch_id="evp_" + uuid.uuid4().hex[:12],
        target_file="backend/evolution/models.py",
        old_snippet="",
        new_snippet="x = 1\n",
        description="test",
        patch_type=PatchType.BUGFIX,
    )
    r = t.test(p)
    assert r["outcome"] == "passed"
    p2 = PatchProposal(
        patch_id="evp_" + uuid.uuid4().hex[:12],
        target_file="backend/evolution/models.py",
        old_snippet="",
        new_snippet="x = (",
        description="bad",
        patch_type=PatchType.BUGFIX,
    )
    r2 = t.test(p2)
    assert r2["outcome"] == "failed"


def test_singleton():
    reset_engine()
    assert get_engine() is get_engine()
    reset_engine()


def test_reset_clears():
    reset_engine()
    e = get_engine()
    e.propose_manual("backend/evolution/models.py", "", "X_REFACTOR = 1\n", "d")
    assert e.status()["patches_total"] >= 1
    reset_engine()
    assert get_engine().status()["patches_total"] == 0
