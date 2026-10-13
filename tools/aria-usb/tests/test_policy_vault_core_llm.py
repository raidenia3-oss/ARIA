import json
import os
import tempfile
from pathlib import Path

import pytest

from app.policy import Policy, AccessLevel, PathRisk, DEFAULT_POLICY
from app.vault import Vault, encrypt_blob, decrypt_blob
from app.core import create_registry, ToolResult, ToolStatus
from app.llm_local import LLMLocalClient


class TestPolicy:
    def setup_method(self):
        self.policy = Policy()
        self.policy.fs_roots = [str(Path.cwd())]
        self.policy.add_rule("work/**", AccessLevel.READ)
        self.policy.add_rule("work/**", AccessLevel.WRITE)

    def test_allow_work_read(self):
        allowed, reason = self.policy.check_path("work/file.txt", self.policy.fs_roots, PathRisk.READ)
        assert allowed
        assert "read" in reason.lower() or "meta" in reason.lower()

    def test_allow_work_write(self):
        allowed, reason = self.policy.check_path("work/file.txt", self.policy.fs_roots, PathRisk.WRITE)
        assert allowed

    def test_deny_outside_roots(self):
        allowed, reason = self.policy.check_path("../secret.txt", self.policy.fs_roots, PathRisk.READ)
        assert not allowed
        assert "outside" in reason.lower()

    def test_deny_traversal(self):
        allowed, reason = self.policy.check_path("work/../../etc/passwd", self.policy.fs_roots, PathRisk.READ)
        assert not allowed

    def test_deny_ads(self):
        allowed, reason = self.policy.check_path("work/file.txt:stream", self.policy.fs_roots, PathRisk.READ)
        assert not allowed
        assert "ads" in reason.lower()

    def test_deny_reserved_name(self):
        allowed, reason = self.policy.check_path("work/CON.txt", self.policy.fs_roots, PathRisk.READ)
        assert not allowed

    def test_sensitive_location_deny(self):
        allowed, reason = self.policy.check_path("C:\\Users\\test\\AppData\\Local\\file.txt", ["C:\\"], PathRisk.READ)
        assert not allowed

    def test_secret_file_meta_only(self):
        allowed, reason = self.policy.check_path("work/secret.key", self.policy.fs_roots, PathRisk.READ)
        assert allowed
        assert "meta" in reason.lower()

    def test_media_file_meta_default(self):
        allowed, reason = self.policy.check_path("work/photo.jpg", self.policy.fs_roots, PathRisk.READ)
        assert allowed
        assert "meta" in reason.lower()

    def test_media_override_allows_read(self):
        self.policy.add_rule("work/media/**", AccessLevel.READ, media_override=True)
        allowed, reason = self.policy.check_path("work/media/photo.jpg", self.policy.fs_roots, PathRisk.READ)
        assert allowed

    def test_deny_by_default_unknown(self):
        allowed, reason = self.policy.check_path("work/unknown.xyz", self.policy.fs_roots, PathRisk.READ)
        assert not allowed

    def test_case_insensitive(self):
        allowed, reason = self.policy.check_path("WORK/FILE.TXT", self.policy.fs_roots, PathRisk.READ)
        assert allowed

    def test_unc_path_denied(self):
        allowed, reason = self.policy.check_path("\\\\server\\share\\file.txt", self.policy.fs_roots, PathRisk.READ)
        assert not allowed

    def test_long_path_prefix(self):
        allowed, reason = self.policy.check_path("\\\\?\\C:\\work\\file.txt", self.policy.fs_roots, PathRisk.READ)
        assert not allowed

    def test_list_visible_filters_hidden(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "work"
            work.mkdir()
            (work / "visible.txt").write_text("x")
            (work / ".hidden").write_text("x")
            self.policy.fs_roots = [tmp]
            visible = self.policy.list_visible(str(work))
            assert "visible.txt" in visible
            assert ".hidden" not in visible


class TestVault:
    def test_roundtrip(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        try:
            vault = Vault(path)
            data = b"secret data"
            vault.create("passphrase123", data)
            result = vault.open("passphrase123")
            assert result == data
            vault.close()
        finally:
            os.unlink(path)

    def test_wrong_passphrase_fails(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        try:
            vault = Vault(path)
            vault.create("correct", b"data")
            with pytest.raises(ValueError, match="passphrase incorrecta"):
                vault.open("wrong")
        finally:
            os.unlink(path)

    def test_tampered_file_fails(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        try:
            vault = Vault(path)
            vault.create("pass", b"data")
            with open(path, "rb") as f:
                data = f.read()
            tampered = data.replace(b"ct", b"xx", 1)
            with open(path, "wb") as f:
                f.write(tampered)
            with pytest.raises(ValueError, match="passphrase incorrecta|manipulado"):
                vault.open("pass")
        finally:
            os.unlink(path)

    def test_salt_unique_per_creation(self):
        with tempfile.NamedTemporaryFile(delete=False) as f1, tempfile.NamedTemporaryFile(delete=False) as f2:
            path1, path2 = f1.name, f2.name
        try:
            Vault(path1).create("same", b"data")
            Vault(path2).create("same", b"data")
            with open(path1, "rb") as f:
                blob1 = json.loads(f.read())
            with open(path2, "rb") as f:
                blob2 = json.loads(f.read())
            assert blob1["salt"] != blob2["salt"]
        finally:
            os.unlink(path1)
            os.unlink(path2)


class TestCore:
    def setup_method(self):
        self.policy = Policy()
        self.policy.fs_roots = [str(Path.cwd())]
        self.policy.add_rule("work/**", AccessLevel.READ)
        self.policy.add_rule("work/**", AccessLevel.WRITE)
        self.registry = create_registry(self.policy)

    def test_register_and_run_ok(self):
        @self.registry.register("echo", {"type": "object", "properties": {"msg": {"type": "string"}}}, PathRisk.READ, [])
        def echo(msg: str) -> ToolResult:
            return ToolResult.ok("echo", {"echo": msg})

        result = self.registry.run("echo", {"msg": "hola"}, self.policy.fs_roots)
        assert result.status == ToolStatus.OK
        assert result.result == {"echo": "hola"}

    def test_invalid_return_type_fails(self):
        @self.registry.register("bad", {"type": "object"}, PathRisk.READ, [])
        def bad() -> str:
            return "not a ToolResult"

        result = self.registry.run("bad", {}, self.policy.fs_roots)
        assert result.status == ToolStatus.FAILED
        assert "tipo de retorno invalido" in result.error

    def test_policy_deny_on_path_arg(self):
        @self.registry.register("read_file", {"type": "object", "properties": {"path": {"type": "string"}}}, PathRisk.READ, ["path"])
        def read_file(path: str) -> ToolResult:
            return ToolResult.ok("read_file", {"path": path})

        result = self.registry.run("read_file", {"path": "../secret.txt"}, self.policy.fs_roots)
        assert result.status == ToolStatus.FAILED
        assert "policy deny" in result.error

    def test_unknown_tool_fails(self):
        result = self.registry.run("nonexistent", {}, self.policy.fs_roots)
        assert result.status == ToolStatus.FAILED
        assert "not found" in result.error


class TestLLMLocalClient:
    def test_schema_validation_ok(self):
        client = LLMLocalClient("http://127.0.0.1:9999")
        schema = {"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"]}
        valid_json = '{"answer": "42"}'
        result = client._validate_json(valid_json, schema)
        assert json.loads(result) == {"answer": "42"}

    def test_schema_validation_fail_missing_field(self):
        client = LLMLocalClient("http://127.0.0.1:9999")
        schema = {"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"]}
        invalid_json = '{}'
        with pytest.raises(ValueError, match="JSON no cumple schema"):
            client._validate_json(invalid_json, schema)

    def test_invalid_json_fails(self):
        client = LLMLocalClient("http://127.0.0.1:9999")
        schema = {"type": "object"}
        with pytest.raises(ValueError, match="no es JSON"):
            client._validate_json("not json", schema)


class TestCanaries:
    def test_canary_outside_roots_not_accessible(self):
        policy = Policy()
        policy.fs_roots = [str(Path.cwd())]
        policy.add_rule("work/**", AccessLevel.READ)

        with tempfile.TemporaryDirectory() as tmp:
            canary = Path(tmp) / "canary_secret.txt"
            canary.write_text("SECRET_CANARY_CONTENT")
            allowed, _ = policy.check_path(str(canary), policy.fs_roots, PathRisk.READ)
            assert not allowed

    def test_canary_not_listed(self):
        policy = Policy()
        policy.fs_roots = [str(Path.cwd())]
        policy.add_rule("work/**", AccessLevel.READ)

        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "work"
            work.mkdir()
            (work / "normal.txt").write_text("ok")
            canary = Path(tmp) / "canary.txt"
            canary.write_text("SECRET")
            policy.fs_roots = [tmp]
            visible = policy.list_visible(str(work))
            assert "normal.txt" in visible
            assert "canary.txt" not in visible


if __name__ == "__main__":
    pytest.main([__file__, "-v"])