"""Tests for the ARIA plugin marketplace."""

import json
import tempfile
from pathlib import Path

import pytest

from aria_marketplace import (
    PluginRegistry,
    PluginMetadata,
    DependencyResolver,
    DependencyError,
    PluginInstaller,
    verify_checksum,
    verify_signature,
)


class TestVerifyChecksum:
    def test_correct_checksum(self):
        import hashlib
        data = b"hello world"
        expected = hashlib.sha256(data).hexdigest()
        assert verify_checksum(data, expected) is True

    def test_wrong_checksum(self):
        assert verify_checksum(b"hello", "wronghash") is False

    def test_empty_checksum(self):
        assert verify_checksum(b"anything", "") is True

    def test_nonexistent_file(self, tmp_path):
        from aria_marketplace.verifier import verify_file_checksum
        assert verify_file_checksum(tmp_path / "nope.txt", "abc") is False


class TestVerifySignature:
    def test_valid_signature(self):
        import hashlib, hmac, os, json
        secret = "test-secret"
        data = {"version": 1, "foo": "bar"}
        message = json.dumps(data, sort_keys=True, separators=(",", ":"))
        sig = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

        # Temporarily set env var
        old = os.environ.get("ARIA_REGISTRY_SECRET")
        os.environ["ARIA_REGISTRY_SECRET"] = secret
        try:
            assert verify_signature(data, sig) is True
        finally:
            if old:
                os.environ["ARIA_REGISTRY_SECRET"] = old
            else:
                del os.environ["ARIA_REGISTRY_SECRET"]

    def test_invalid_signature(self):
        assert verify_signature({"a": 1}, "bad") is False


class TestPluginMetadata:
    def test_from_dict(self):
        data = {
            "name": "test-plugin",
            "version": "1.0.0",
            "description": "Test",
            "author": "test",
        }
        meta = PluginMetadata.from_dict(data)
        assert meta.name == "test-plugin"
        assert meta.version == "1.0.0"
        assert meta.aria_min_version == "6.0.0"


class TestPluginRegistry:
    def test_init(self, tmp_path):
        registry = PluginRegistry(tmp_path / "cache")
        assert registry.cache_dir.exists()

    def test_search_empty_cache(self, tmp_path):
        registry = PluginRegistry(tmp_path / "cache")
        # No network - should return empty
        # We can't test network calls without mocking, so just test init
        assert registry.cache_dir == tmp_path / "cache"

    def test_clear_cache(self, tmp_path):
        registry = PluginRegistry(tmp_path / "cache")
        cache_file = registry.cache_dir / "index.json"
        cache_file.write_text('{"test": true}')
        registry.clear_cache()
        assert not cache_file.exists()


class TestDependencyResolver:
    def test_parse_dep(self):
        from aria_marketplace.resolver import _parse_dep
        name, constraint = _parse_dep("requests>=2.28")
        assert name == "requests"
        assert constraint == ">=2.28"

    def test_parse_dep_no_constraint(self):
        from aria_marketplace.resolver import _parse_dep
        name, constraint = _parse_dep("yt-dlp")
        assert name == "yt-dlp"
        assert constraint == ""


class TestPluginInstaller:
    def test_init(self, tmp_path):
        installer = PluginInstaller(tmp_path / "aria")
        assert installer.plugins_dir.exists()
        assert installer.manifest_path.exists()

    def test_list_installed_empty(self, tmp_path):
        installer = PluginInstaller(tmp_path / "aria")
        assert installer.list_installed() == []

    def test_list_installed_with_data(self, tmp_path):
        installer = PluginInstaller(tmp_path / "aria")
        manifest = {"plugins": [{"name": "test", "version": "1.0.0"}]}
        installer.manifest_path.write_text(json.dumps(manifest))
        result = installer.list_installed()
        assert len(result) == 1
        assert result[0]["name"] == "test"

    def test_uninstall_not_found(self, tmp_path):
        installer = PluginInstaller(tmp_path / "aria")
        result = installer.uninstall("nonexistent")
        assert result["status"] == "error"

    def test_uninstall_success(self, tmp_path):
        installer = PluginInstaller(tmp_path / "aria")
        plugin_dir = installer.plugins_dir / "test-plugin"
        plugin_dir.mkdir(parents=True)
        result = installer.uninstall("test-plugin")
        assert result["status"] == "success"
        assert not plugin_dir.exists()

    def test_topological_sort(self, tmp_path):
        installer = PluginInstaller(tmp_path / "aria")
        resolved = {
            "a": {"dependencies": ["b", "c"]},
            "b": {"dependencies": ["c"]},
            "c": {"dependencies": []},
        }
        order = installer._topological_sort(resolved)
        # c should come before b and a
        assert order.index("c") < order.index("b")
        assert order.index("b") < order.index("a")