"""BLOQUE 85 - unit tests for encrypted snapshot + recovery engine (offline)."""

import os

import pytest

from backend.recovery.snapshot import RecoveryEngine, SnapshotMetadata


@pytest.fixture
def eng(tmp_path, monkeypatch):
    d = tmp_path / "store"
    monkeypatch.setenv("AURA_RECOVERY_DIR", str(d))
    return RecoveryEngine(store_dir=str(d))


@pytest.fixture
def srcdir(tmp_path):
    s = tmp_path / "src"
    s.mkdir()
    (s / "a.txt").write_text("hola aura", encoding="utf-8")
    sub = s / "sub"
    sub.mkdir()
    (sub / "b.txt").write_text("backup test", encoding="utf-8")
    return s


def test_metadata_defaults():
    m = SnapshotMetadata(label="t")
    assert m.snapshot_id and m.kind == "full" and m.to_dict()["offline_only"] is True


def test_metadata_rejects_kind():
    import pytest as _p

    with _p.raises(ValueError):
        SnapshotMetadata(kind="nope")


def test_create_verify_roundtrip(eng, srcdir, tmp_path):
    m = eng.create_snapshot({"docs": str(srcdir)}, label="r1")
    assert m.files == 2 and m.size_bytes > 0 and m.sha256
    v = eng.verify(m.snapshot_id)
    assert v["verified"] is True
    out = tmp_path / "out"
    r = eng.restore(m.snapshot_id, str(out), overwrite=True)
    assert r["restored"] is True and r["files"] == 2
    assert (out / "docs" / "a.txt").read_text(encoding="utf-8") == "hola aura"


def test_restore_no_overwrite(eng, srcdir, tmp_path):
    m = eng.create_snapshot({"d": str(srcdir)})
    out = tmp_path / "o2"
    out.mkdir()
    (out / "d").mkdir()
    (out / "d" / "a.txt").write_text("custom", encoding="utf-8")
    r = eng.restore(m.snapshot_id, str(out), overwrite=False)
    assert r["restored"] is True
    assert (out / "d" / "a.txt").read_text(encoding="utf-8") == "custom"


def test_verify_missing(eng):
    assert eng.verify("nope")["verified"] is False


def test_delete(eng, srcdir):
    m = eng.create_snapshot({"d": str(srcdir)})
    assert eng.delete(m.snapshot_id) is True
    assert eng.get(m.snapshot_id) is None
    assert eng.delete(m.snapshot_id) is False


def test_tamper_detected(eng, srcdir):
    m = eng.create_snapshot({"d": str(srcdir)})
    p = tmp_path_not_used = None
    from pathlib import Path

    Path(m.archive_path).write_bytes(b"tampered")
    assert eng.verify(m.snapshot_id)["verified"] is False


def test_recovery_callback(eng, srcdir, tmp_path):
    seen = []
    eng.on_recovery(lambda e: seen.append(e))
    m = eng.create_snapshot({"d": str(srcdir)})
    eng.restore(m.snapshot_id, str(tmp_path / "o3"), overwrite=True)
    assert len(seen) == 1 and seen[0]["snapshot_id"] == m.snapshot_id


def test_singleton_isolated(tmp_path, monkeypatch):
    from backend.recovery.snapshot import get_recovery_engine, reset_recovery_engine

    monkeypatch.setenv("AURA_RECOVERY_DIR", str(tmp_path / "s2"))
    reset_recovery_engine()
    assert get_recovery_engine() is get_recovery_engine()
    reset_recovery_engine()
