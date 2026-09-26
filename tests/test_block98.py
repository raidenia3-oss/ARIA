"""BLOQUE 98 - unit tests for Sovereign Bootstrapper."""

import pytest

from backend.core.sovereign_bootstrapper import (
    ECOSYSTEM_BLOCKS,
    BlockAudit,
    BootEvent,
    BootSeverity,
    BootStatus,
    CrossBlockIntegrityValidator,
    HardeningLevel,
    HardeningReport,
    SovereignBootstrapper,
    SovereignHardening,
    get_sovereign_bootstrapper,
    reset_sovereign_bootstrapper,
)


@pytest.fixture(autouse=True)
def _clean():
    reset_sovereign_bootstrapper()
    yield
    reset_sovereign_bootstrapper()


def test_enums():
    assert BootSeverity.CRITICAL.value == "critical"
    assert BootStatus.PENDING.value == "pending"
    assert BootStatus.OK.value == "ok"
    assert HardeningLevel.OFF.value == 0
    assert HardeningLevel.STANDARD.value == 1
    assert HardeningLevel.STRICT.value == 2
    assert HardeningLevel.PARANOID.value == 3


def test_dataclasses():
    a = BlockAudit(
        block_id="b1",
        module="m",
        status=BootStatus.OK,
        severity=BootSeverity.HIGH,
        importable=True,
        sha256="abc",
    )
    d = a.to_dict()
    assert d["block_id"] == "b1"
    assert d["status"] == "ok"
    ev = BootEvent(stage="boot", message="hi")
    assert ev.event_id
    r = HardeningReport(level=HardeningLevel.STRICT)
    assert r.offline_only is True


def test_ecosystem_blocks_present():
    ids = [b["block"] for b in ECOSYSTEM_BLOCKS]
    assert "block_79" in ids
    assert "block_97" in ids
    assert "block_95" in ids


def test_validator_audit_ok():
    v = CrossBlockIntegrityValidator()
    a = v.audit_block(
        {
            "block": "block_97",
            "module": "backend.hud.omni_interaction",
            "severity": BootSeverity.HIGH,
        }
    )
    assert a.importable is True
    assert a.status == BootStatus.OK
    assert a.sha256


def test_validator_audit_missing():
    v = CrossBlockIntegrityValidator()
    a = v.audit_block(
        {"block": "block_fake", "module": "no.such.module", "severity": BootSeverity.HIGH}
    )
    assert a.importable is False
    assert a.status == BootStatus.FAILED


def test_validator_audit_all():
    v = CrossBlockIntegrityValidator()
    results = v.audit_all()
    assert len(results) >= 8
    assert all(isinstance(r, BlockAudit) for r in results)


def test_validator_health_summary():
    v = CrossBlockIntegrityValidator()
    v.audit_all()
    s = v.health_summary()
    assert s["blocks_total"] >= 8
    assert "ready" in s
    assert s["offline_only"] is True


def test_validator_critical_failures():
    v = CrossBlockIntegrityValidator()
    v.audit_block({"block": "x", "module": "no.such", "severity": BootSeverity.CRITICAL})
    fails = v.critical_failures()
    assert len(fails) == 1


def test_validator_clear():
    v = CrossBlockIntegrityValidator()
    v.audit_block(
        {"block": "b", "module": "backend.hud.omni_interaction", "severity": BootSeverity.LOW}
    )
    assert len(v._audits) == 1
    v.clear()
    assert len(v._audits) == 0


def test_hardening_scan():
    h = SovereignHardening(level=HardeningLevel.STRICT)
    r = h.scan()
    assert isinstance(r, HardeningReport)
    assert r.checks_total > 0
    assert r.offline_only is True


def test_hardening_set_level():
    h = SovereignHardening()
    lvl = h.set_level(HardeningLevel.PARANOID)
    assert lvl == HardeningLevel.PARANOID


def test_bootstrapper_run():
    bs = SovereignBootstrapper()
    snap = bs.run_bootstrapping()
    assert snap["status"] == "success"
    assert snap["booted"] is True
    assert "health_report" in snap
    assert "hardening" in snap
    assert snap["offline_only"] is True


def test_bootstrapper_status():
    bs = SovereignBootstrapper()
    bs.run_bootstrapping()
    s = bs.status()
    assert s["booted"] is True
    assert s["hardening"]["offline_only"] is True
    assert s["offline_only"] is True


def test_bootstrapper_audits():
    bs = SovereignBootstrapper()
    bs.run_bootstrapping()
    items = bs.audits()
    assert len(items) >= 8


def test_bootstrapper_events():
    bs = SovereignBootstrapper()
    bs.run_bootstrapping()
    evs = bs.events()
    assert len(evs) >= 1
    assert all(isinstance(e, BootEvent) for e in evs)


def test_bootstrapper_reset():
    bs = SovereignBootstrapper()
    bs.run_bootstrapping()
    assert bs.status()["booted"] is True
    bs.reset()
    assert bs.status()["booted"] is False


def test_bootstrapper_hardening_levels():
    bs = SovereignBootstrapper()
    rep = bs.harden(HardeningLevel.PARANOID)
    assert rep.level == HardeningLevel.PARANOID


def test_bootstrapper_singleton():
    a = get_sovereign_bootstrapper()
    b = get_sovereign_bootstrapper()
    assert a is b


def test_bootstrapper_orchestrator():
    bs = SovereignBootstrapper()
    dispatched = []

    class _Orch:
        def execute_omni_command(self, cmd):
            dispatched.append(cmd)

    bs.set_orchestrator(_Orch())
    assert bs._orchestrator is not None


def test_bootstrapper_snapshot():
    bs = SovereignBootstrapper()
    snap = bs.snapshot()
    assert "booted" in snap
    assert "offline_only" in snap
    assert snap["offline_only"] is True


def test_validator_subscribe():
    v = CrossBlockIntegrityValidator()
    received = []
    v.subscribe(lambda p: received.append(p))
    v.audit_block({"block": "x", "module": "no.such", "severity": BootSeverity.HIGH})
    assert any(p.get("type") == "block_failed" for p in received)
