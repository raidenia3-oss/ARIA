"""Tests for the ARIA snapshot system."""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from aria_snapshot import (
    Snapshot,
    SnapshotManager,
    SnapshotCreator,
    SnapshotRestorer,
)


class TestSnapshotModel:
    def test_to_from_json(self):
        snap = Snapshot(
            name="test-snap",
            timestamp=datetime.now(timezone.utc),
            aria_version="6.0.0",
            db_hash="abc123",
            env_hash="def456",
            git_tag="snapshot-test-snap",
            plugins=["plugin-a", "plugin-b"],
            description="Test snapshot",
        )
        d = snap.to_json()
        snap2 = Snapshot.from_json(d)
        assert snap2.name == snap.name
        assert snap2.aria_version == snap.aria_version
        assert snap2.db_hash == snap.db_hash
        assert snap2.plugins == snap.plugins

    def test_from_file(self, tmp_path):
        snap = Snapshot(
            name="file-snap",
            timestamp=datetime.now(timezone.utc),
            aria_version="6.0.0",
            db_hash="abc",
            env_hash="def",
            git_tag="snapshot-file-snap",
        )
        path = tmp_path / "file-snap.json"
        path.write_text(json.dumps(snap.to_json()))
        snap2 = Snapshot.from_file(path)
        assert snap2.name == "file-snap"


class TestSnapshotManager:
    def test_list_snapshots_empty(self, tmp_path):
        manager = SnapshotManager(tmp_path)
        assert manager.list_snapshots() == []

    def test_list_snapshots_with_data(self, tmp_path):
        manager = SnapshotManager(tmp_path)
        snap1 = Snapshot(
            name="snap1", timestamp=datetime(2026, 1, 1),
            aria_version="6.0.0", db_hash="a", env_hash="b",
            git_tag="snapshot-snap1",
        )
        snap2 = Snapshot(
            name="snap2", timestamp=datetime(2026, 6, 1),
            aria_version="6.1.0", db_hash="c", env_hash="d",
            git_tag="snapshot-snap2",
        )
        (tmp_path / "snapshots" / "snap1.json").write_text(json.dumps(snap1.to_json()))
        (tmp_path / "snapshots" / "snap2.json").write_text(json.dumps(snap2.to_json()))

        snapshots = manager.list_snapshots()
        assert len(snapshots) == 2
        # Newest first
        assert snapshots[0].name == "snap2"

    def test_get_snapshot_found(self, tmp_path):
        manager = SnapshotManager(tmp_path)
        snap = Snapshot(
            name="found", timestamp=datetime.now(timezone.utc),
            aria_version="6.0.0", db_hash="a", env_hash="b",
            git_tag="snapshot-found",
        )
        (tmp_path / "snapshots" / "found.json").write_text(json.dumps(snap.to_json()))
        result = manager.get_snapshot("found")
        assert result is not None
        assert result.name == "found"

    def test_get_snapshot_not_found(self, tmp_path):
        manager = SnapshotManager(tmp_path)
        assert manager.get_snapshot("nonexistent") is None

    def test_delete_snapshot(self, tmp_path):
        manager = SnapshotManager(tmp_path)
        snap = Snapshot(
            name="delete-me", timestamp=datetime.now(timezone.utc),
            aria_version="6.0.0", db_hash="a", env_hash="b",
            git_tag="snapshot-delete-me",
        )
        json_path = tmp_path / "snapshots" / "delete-me.json"
        json_path.write_text(json.dumps(snap.to_json()))
        assert json_path.exists()

        result = manager.delete_snapshot("delete-me")
        assert result is True
        assert not json_path.exists()

    def test_delete_snapshot_not_found(self, tmp_path):
        manager = SnapshotManager(tmp_path)
        assert manager.delete_snapshot("nonexistent") is False

    def test_cleanup_old_snapshots(self, tmp_path):
        manager = SnapshotManager(tmp_path)
        for i in range(7):
            snap = Snapshot(
                name=f"snap-{i}", timestamp=datetime(2026, 1, i + 1),
                aria_version="6.0.0", db_hash="a", env_hash="b",
                git_tag=f"snapshot-snap-{i}",
            )
            (tmp_path / "snapshots" / f"snap-{i}.json").write_text(json.dumps(snap.to_json()))

        deleted = manager.cleanup_old_snapshots(keep=3)
        assert deleted == 4
        remaining = manager.list_snapshots()
        assert len(remaining) == 3


class TestSnapshotCreator:
    def test_create_snapshot(self, tmp_path):
        aria_home = tmp_path / "aria"
        aria_home.mkdir()
        creator = SnapshotCreator(aria_home)
        snap = creator.create("test-snap", "Test description")

        assert snap.name == "test-snap"
        assert snap.description == "Test description"
        assert snap.git_tag == "snapshot-test-snap"
        json_path = aria_home / "snapshots" / "test-snap.json"
        assert json_path.exists()

    def test_create_snapshot_with_state_files(self, tmp_path):
        aria_home = tmp_path / "aria"
        aria_home.mkdir()
        # Create a state file in parent
        state_file = tmp_path / "brain_state.json"
        state_file.write_text('{"test": true}')

        creator = SnapshotCreator(aria_home)
        snap = creator.create("with-state")

        snap_dir = aria_home / "snapshots" / "with-state"
        assert (snap_dir / "brain_state.json").exists()
        assert "brain_state.json" in snap.state_files


class TestSnapshotRestorer:
    def test_restore_by_name(self, tmp_path):
        aria_home = tmp_path / "aria"
        aria_home.mkdir()
        creator = SnapshotCreator(aria_home)
        creator.create("restore-test", "Test restore")

        # Create a state file to be restored
        state_file = tmp_path / "brain_state.json"
        state_file.write_text('{"original": true}')

        # Modify it
        state_file.write_text('{"modified": true}')

        # Restore
        restorer = SnapshotRestorer(aria_home)
        result = restorer.restore_by_name("restore-test")
        assert result is True

    def test_restore_not_found(self, tmp_path):
        aria_home = tmp_path / "aria"
        aria_home.mkdir()
        restorer = SnapshotRestorer(aria_home)
        assert restorer.restore_by_name("nonexistent") is False