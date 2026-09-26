"""BLOQUE 81 - Unit tests for Local Omni-Diagnostic Suite."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from backend.diagnostics.omni import (
    CheckResult,
    DiagnosticConfig,
    OmniAuditor,
    OmniEngine,
    SovereigntyVerifier,
    get_omni_auditor,
    get_omni_engine,
    register_default_checks,
    reset_omni_auditor,
    reset_omni_engine,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_omni_auditor()
    yield
    reset_omni_auditor()


def _mk(tmpdir, **cfgkw):
    cfg = DiagnosticConfig(repo_root=str(tmpdir), **cfgkw)
    return OmniAuditor(config=cfg)


def test_check_result_to_dict():
    r = CheckResult(name="x", status="pass", latency_ms=5, details={"a": 1})
    d = r.to_dict()
    assert d["name"] == "x" and d["status"] == "pass" and d["latency_ms"] == 5
    assert d["details"] == {"a": 1}


def test_register_and_unregister_check():
    a = _mk(os.getcwd())
    a.register_check("foo", lambda: {"status": "pass"})
    assert "foo" in a.check_names()
    a.unregister_check("foo")
    assert "foo" not in a.check_names()


def test_run_all_passes_and_skips():
    a = _mk(os.getcwd())
    a.register_check("ok", lambda: {"status": "pass"})
    a.register_check("warn", lambda: {"status": "warn"})
    a.register_check("skip", lambda: {"status": "skip"})
    a.register_check("fail", lambda: {"status": "fail"})
    r = a.run_all()
    assert r["counts"] == {"pass": 1, "warn": 1, "skip": 1, "fail": 1}
    assert r["verdict"] == "action_required"
    assert r["checks_total"] == 4
    assert r["offline_only"] is True


def test_run_all_only_and_skip_filters():
    a = _mk(os.getcwd())
    a.register_check("a", lambda: {"status": "pass"})
    a.register_check("b", lambda: {"status": "pass"})
    a.register_check("c", lambda: {"status": "pass"})
    r = a.run_all(only=["a", "b"])
    assert r["checks_total"] == 2
    r2 = a.run_all(skip=["a"])
    assert r2["checks_total"] == 2


def test_run_all_records_history_and_last_report():
    a = _mk(os.getcwd())
    a.register_check("x", lambda: {"status": "pass"})
    a.run_all()
    a.run_all()
    assert len(a.history()) == 2
    assert a.last_report is not None
    assert a.last_report["checks_total"] == 1


def test_run_all_handles_exception():
    a = _mk(os.getcwd())

    def boom():
        raise RuntimeError("kaboom")

    a.register_check("boom", boom)
    r = a.run_all()
    res = r["results"][0]
    assert res["status"] == "fail"
    assert "kaboom" in res["error"]


def test_export_report_writes_file(tmp_path):
    a = _mk(str(tmp_path))
    a.register_check("x", lambda: {"status": "pass"})
    a.run_all()
    p = a.export_report(report_dir=str(tmp_path / "reports"))
    assert os.path.exists(p)
    assert p.endswith(".json")


def test_default_checks_registered():
    a = _mk(os.getcwd())
    names = register_default_checks(a)
    assert "filesystem" in names
    assert "encryption_integrity" in names
    assert "mesh_communication" in names
    assert "daemon_persistence" in names
    assert "offline_scan" in names
    assert "secrets_scan" in names


def test_default_checks_run_sovereign_ready():
    a = _mk(os.getcwd())
    register_default_checks(a)
    r = a.run_all()
    assert r["verdict"] == "sovereign_ready"
    assert r["counts"]["fail"] == 0


def test_sovereignty_verifier_scan_offline_clean():
    v = SovereigntyVerifier()
    res = v.scan_offline(["backend/daemon", "backend/master_control"])
    assert res["status"] in ("pass", "warn")
    assert res["scanned_files"] >= 0


def test_sovereignty_verifier_scan_offline_detects_external():
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "a.py"), "w", encoding="utf-8") as fh:
            fh.write('x = "https://api.evil.example.com/token"\n')
        v = SovereigntyVerifier()
        res = v.scan_offline([d])
        assert res["external_count"] >= 1
        assert res["status"] == "warn"


def test_sovereignty_verifier_scan_secrets_clean():
    v = SovereigntyVerifier()
    res = v.scan_secrets(["backend/daemon"])
    assert res["status"] in ("pass", "warn")


def test_singleton_isolation():
    reset_omni_auditor()
    e1 = get_omni_auditor()
    e2 = get_omni_auditor()
    assert e1 is e2
    reset_omni_auditor()
    e3 = get_omni_auditor()
    assert e3 is not e1


def test_omni_engine_alias():
    assert OmniEngine is OmniAuditor
    assert get_omni_engine is get_omni_auditor
    assert reset_omni_engine is reset_omni_auditor
