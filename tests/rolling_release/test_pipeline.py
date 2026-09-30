"""Tests for the rolling release pipeline."""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timezone

from aria_release import (
    Release, ReleaseChannel,
    ReleaseDetector, MetadataVerifier, verify_checksum,
    Updater, RollingReleasePipeline,
)


class TestReleaseModel:
    def test_version_comparison(self):
        r1 = Release("6.1.0", ReleaseChannel.STABLE, datetime.now(timezone.utc), "abc", "url")
        r2 = Release("6.0.0", ReleaseChannel.STABLE, datetime.now(timezone.utc), "def", "url")
        assert r1 > r2
        assert r2 < r1

    def test_version_tuple(self):
        r = Release("6.1.0", ReleaseChannel.STABLE, datetime.now(timezone.utc), "abc", "url")
        assert r.version_tuple == (6, 1, 0)

    def test_to_from_dict(self):
        r = Release("6.0.0", ReleaseChannel.STABLE, datetime.now(timezone.utc), "abc", "url")
        d = r.to_dict()
        r2 = Release.from_dict(d)
        assert r2.version == r.version
        assert r2.channel == r.channel


class TestReleaseChannel:
    def test_from_string(self):
        assert ReleaseChannel.from_string("stable") == ReleaseChannel.STABLE
        assert ReleaseChannel.from_string("testing") == ReleaseChannel.TESTING
        assert ReleaseChannel.from_string("unstable") == ReleaseChannel.UNSTABLE

    def test_invalid_channel(self):
        with pytest.raises(ValueError):
            ReleaseChannel.from_string("invalid")


class TestVerifyChecksum:
    def test_verify_correct_checksum(self, tmp_path):
        import hashlib
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        expected = hashlib.sha256(b"hello world").hexdigest()
        assert verify_checksum(f, expected) is True

    def test_verify_wrong_checksum(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        assert verify_checksum(f, "wronghash") is False

    def test_verify_nonexistent_file(self, tmp_path):
        assert verify_checksum(tmp_path / "nope.txt", "abc") is False

    def test_verify_empty_checksum(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        assert verify_checksum(f, "") is True


class TestMetadataVerifier:
    def test_verify_without_root(self, tmp_path):
        v = MetadataVerifier(tmp_path)
        data = {"signature": "test", "version": 1}
        assert v.verify_metadata("timestamp", data) is True

    def test_verify_with_root(self, tmp_path):
        import json, hashlib
        meta_dir = tmp_path / "metadata"
        meta_dir.mkdir()
        root_key = "my-secret-root-key"
        root = {"keys": {"root": {"keyval": {"public": root_key}}}}
        (meta_dir / "root.json").write_text(json.dumps(root))

        v = MetadataVerifier(meta_dir)
        # Compute signature over data WITHOUT the signature field
        data_for_sig = {"version": 1, "foo": "bar"}
        expected_sig = hashlib.sha256(
            (root_key + json.dumps(data_for_sig, sort_keys=True, separators=(",", ":"))).encode()
        ).hexdigest()
        data = {"version": 1, "foo": "bar", "signature": expected_sig}
        assert v.verify_metadata("timestamp", data) is True

    def test_verify_bad_signature(self, tmp_path):
        import json
        meta_dir = tmp_path / "metadata"
        meta_dir.mkdir()
        root = {"keys": {"root": {"keyval": {"public": "key"}}}}
        (meta_dir / "root.json").write_text(json.dumps(root))

        v = MetadataVerifier(meta_dir)
        data = {"signature": "bad", "version": 1}
        assert v.verify_metadata("timestamp", data) is False


class TestUpdater:
    def test_apply_update_success(self, tmp_path):
        aria_home = tmp_path / "aria"
        aria_home.mkdir()
        updater = Updater(aria_home)

        binary = tmp_path / "ARIA.exe"
        binary.write_bytes(b"fake binary content")

        release = Release(
            "6.1.0", ReleaseChannel.STABLE,
            datetime.now(timezone.utc), "", str(binary)
        )
        result = updater.apply_update(release, binary)
        assert result is True
        # On Windows without admin, symlink falls back to directory copy
        # Either way, the release directory should exist
        assert (aria_home / "releases" / "v6.1.0").exists()

    def test_rollback(self, tmp_path):
        aria_home = tmp_path / "aria"
        aria_home.mkdir()
        updater = Updater(aria_home)

        r1_path = aria_home / "releases" / "v6.0.0"
        r1_path.mkdir(parents=True)
        (r1_path / "ARIA.exe").write_bytes(b"v6.0.0 binary")

        r2_path = aria_home / "releases" / "v6.1.0"
        r2_path.mkdir(parents=True)
        (r2_path / "ARIA.exe").write_bytes(b"v6.1.0 binary")

        # Create a snapshot for rollback
        snapshot = aria_home / "snapshots" / "test-snap"
        snapshot.mkdir(parents=True)
        (snapshot / "previous_version.txt").write_text("v6.0.0")

        # Set current to v6.1.0 (may fail on Windows without admin)
        try:
            updater._atomic_symlink_update(r2_path)
        except OSError:
            pass

        # Rollback should work
        result = updater.rollback("6.1.0")
        assert result is True

    def test_get_current_version_no_link(self, tmp_path):
        updater = Updater(tmp_path / "aria")
        assert updater.get_current_version() is None


class TestRollingReleasePipeline:
    def test_init(self, tmp_path):
        pipeline = RollingReleasePipeline(tmp_path / "aria")
        assert pipeline.channel == ReleaseChannel.STABLE

    def test_check_only_no_network(self, tmp_path):
        pipeline = RollingReleasePipeline(
            tmp_path / "aria", current_version="6.0.0"
        )
        result = pipeline.check_only()
        assert result is None