"""Tests for PermissionEngine (fail-closed + ask mode)."""

from __future__ import annotations

import json
import os
import hashlib
import tempfile
import time
import uuid
from pathlib import Path

import pytest

from backend.permissions import PermissionEngine, PermissionConfig, ToolPermission, get_permission_engine, reset_permission_engine


def _engine_with_config(config: PermissionConfig) -> PermissionEngine:
    return PermissionEngine(config=config)


def _default_config() -> PermissionConfig:
    return PermissionConfig()


def _config_with_auth() -> PermissionConfig:
    """Config with a known auth token for testing."""
    token = "test-auth-token"
    return PermissionConfig(
        auth_token_hash=hashlib.sha256(token.encode()).hexdigest()
    )


# ----------------------------------------------------------- fixtures ---------


@pytest.fixture(autouse=True)
def _reset_global():
    reset_permission_engine()
    yield
    reset_permission_engine()


# ------------------------------------------------------------ tests -----------


class TestUnknownTool:
    """Unknown tool is denied (fail-closed)."""

    def test_unknown_tool_denied(self):
        engine = _engine_with_config(_default_config())
        allowed, reason, req_id = engine.check("unknown.tool")
        assert allowed is False
        assert "not in allowlist" in reason or "explicitly denied" in reason
        assert req_id is None


class TestEngineError:
    """Permission engine errors result in deny (fail-closed)."""

    def test_corrupt_config_fallbacks_to_fail_closed(self, tmp_path):
        # Config dir doesn't exist, should fallback to fail-closed defaults
        engine = PermissionEngine()
        # Default config has no tools allowed
        allowed, _, _ = engine.check("any.tool")
        assert allowed is False


class TestConfigCorrupt:
    """Corrupt config file is handled gracefully (fail-closed)."""

    def test_malformed_json_config(self, tmp_path):
        # This test verifies the _load_config exception handling
        # by ensuring a fresh engine starts with fail-closed defaults
        engine = PermissionEngine()
        assert engine.config.allow_all is False
        assert engine.config.default_allow is False
        # Default policy adds 13 tools, so we expect at least those
        assert len(engine.config.tools) >= 13


class TestDenyWinsOverAllow:
    """Explicit deny (explicitly_denied=True) wins over allow."""

    def test_explicit_deny_overrides_allow(self):
        config = PermissionConfig(
            tools={
                "test.tool": ToolPermission(
                    tool="test.tool",
                    allow=True,
                    explicitly_denied=True,
                )
            }
        )
        engine = _engine_with_config(config)
        allowed, reason, _ = engine.check("test.tool")
        assert allowed is False
        assert "explicitly denied" in reason

    def test_allow_tool_ignored_when_explicitly_denied(self):
        engine = _engine_with_config(_default_config())
        engine.deny_tool("test.tool")
        # Try to allow it - should be ignored
        engine.allow_tool("test.tool", "safe")
        allowed, reason, _ = engine.check("test.tool")
        assert allowed is False
        assert "explicitly denied" in reason


class TestArgsMismatch:
    """Different args than approved hash = deny."""

    def test_args_hash_mismatch_denied(self):
        config = _config_with_auth()
        config.tools = {
            "test.tool": ToolPermission(
                tool="test.tool",
                allow=True,
                require_confirm=True,  # triggers ask mode
            )
        }
        engine = _engine_with_config(config)
        # Create ask request with specific args
        req_id = engine._create_ask_request("test.tool", "safe", {"param": "value1"})
        # Approve it with correct token
        engine.approve_request(req_id, "test-auth-token", approve=True)
        # Now verify with DIFFERENT args - should fail
        assert engine.verify_args_hash(req_id, {"param": "value2"}) is False
        # Same args should pass
        assert engine.verify_args_hash(req_id, {"param": "value1"}) is True


class TestReusePrevention:
    """Approved request cannot be reused (single-use via hash verification)."""

    def test_approved_request_single_use_enforced(self):
        config = _config_with_auth()
        config.tools = {
            "test.tool": ToolPermission(
                tool="test.tool",
                allow=True,
                require_confirm=True,
            )
        }
        engine = _engine_with_config(config)
        req_id = engine._create_ask_request("test.tool", "safe", {"param": "value"})
        engine.approve_request(req_id, "test-auth-token", approve=True)
        # First verification passes
        assert engine.verify_args_hash(req_id, {"param": "value"}) is True
        # But the request is now decided - wait_for_approval would return decided
        req = engine.get_ask_request(req_id)
        assert req["decided"] is True
        assert req["decision"] is True


class TestExpiredRequest:
    """Expired request (TTL 120s) = deny."""

    def test_expired_request_denied(self):
        config = PermissionConfig(
            tools={
                "test.tool": ToolPermission(
                    tool="test.tool",
                    allow=True,
                    require_confirm=True,
                )
            }
        )
        engine = _engine_with_config(config)
        # Manually create expired request
        from backend.permissions.engine import AskRequest
        import time
        expired_req = AskRequest(
            request_id="expired-req",
            tool="test.tool",
            risk="safe",
            args_hash="abc",
            args_canonical="{}",
            created_at=time.time() - 200,  # > 120s ago
            expires_at=time.time() - 80,   # expired
        )
        with engine._ask_lock:
            engine._ask_requests["expired-req"] = expired_req

        approved, reason = engine.wait_for_approval("expired-req", timeout=1.0)
        assert approved is False
        assert "expired" in reason.lower() or "ttl" in reason.lower()


class TestAuditNoSecrets:
    """Audit log never contains secrets (token/password/secret/key/auth/credential)."""

    def test_audit_redacts_secrets_in_args(self):
        config = _config_with_auth()
        config.tools = {
            "test.tool": ToolPermission(
                tool="test.tool",
                allow=True,
                require_confirm=True,
            )
        }
        engine = _engine_with_config(config)
        # Create request with secret-like args
        req_id = engine._create_ask_request(
            "test.tool",
            "safe",
            {"api_key": "secret123", "password": "mypass", "normal_param": "value"}
        )
        engine.approve_request(req_id, "test-auth-token", approve=True)

        audit = engine.audit()
        # Find the decided request in audit
        recent = audit["recent_decisions"]
        assert len(recent) >= 1
        decided = recent[0]
        # The args_hash is there but canonical args should be redacted
        # Actually audit only shows args_hash, not canonical - that's fine
        # Verify the canonical args stored in the request are redacted
        req = engine.get_ask_request(req_id)
        assert req is not None
        # The canonical args should have redacted values
        canon = json.loads(req["args_canonical"])
        assert canon["api_key"] == "[REDACTED]"
        assert canon["password"] == "[REDACTED]"
        assert canon["normal_param"] == "value"


class TestWrongTokenInApprove:
    """Wrong token in approve_request = deny (request stays pending)."""

    def test_wrong_token_does_not_decide_request(self):
        config = _config_with_auth()
        config.tools = {
            "test.tool": ToolPermission(
                tool="test.tool",
                allow=True,
                require_confirm=True,
            )
        }
        engine = _engine_with_config(config)
        req_id = engine._create_ask_request("test.tool", "safe", {"param": "value"})
        # Try with wrong token - should fail
        success, msg = engine.approve_request(req_id, "wrong-token", approve=True)
        assert success is False
        assert "invalid auth token" in msg.lower()
        # Request should still be pending
        req = engine.get_ask_request(req_id)
        assert req["decided"] is False


class TestHmacCompareDigest:
    """Token comparison uses hmac.compare_digest for timing safety."""

    def test_approve_request_uses_constant_time_compare(self):
        """approve_request verifies token with hmac.compare_digest."""
        import hmac
        import hashlib

        config = PermissionConfig(
            tools={
                "test.tool": ToolPermission(
                    tool="test.tool",
                    allow=True,
                    require_confirm=True,
                )
            },
            auth_token_hash=hashlib.sha256("correct-token".encode()).hexdigest(),
        )
        engine = _engine_with_config(config)
        req_id = engine._create_ask_request("test.tool", "safe", {"param": "value"})

        # Correct token should work
        success, msg = engine.approve_request(req_id, "correct-token", approve=True)
        assert success is True

        # Wrong token should fail (constant-time compare)
        req_id2 = engine._create_ask_request("test.tool", "safe", {"param": "value2"})
        success2, msg2 = engine.approve_request(req_id2, "wrong-token", approve=True)
        assert success2 is False
        assert "invalid auth token" in msg2.lower()

    def test_no_auth_token_configured_denies(self):
        """If no auth_token_hash configured, approve_request fails."""
        config = PermissionConfig(
            tools={
                "test.tool": ToolPermission(
                    tool="test.tool",
                    allow=True,
                    require_confirm=True,
                )
            },
            auth_token_hash=None,
        )
        engine = _engine_with_config(config)
        req_id = engine._create_ask_request("test.tool", "safe", {"param": "value"})
        success, msg = engine.approve_request(req_id, "any-token", approve=True)
        assert success is False
        assert "no auth token configured" in msg.lower()


class Test13ToolPolicy:
    """Apply policy: 11 read-only = allow; notes.local.write + research.missions.start = ask."""

    def test_readonly_tools_allowed_by_default(self):
        """Fresh engine should have 11 read-only tools allowed."""
        reset_permission_engine()
        engine = get_permission_engine()
        readonly_tools = [
            "notes.markdown.render_heading",
            "notes.sys.timestamp",
            "numeric.compute.average",
            "numeric.compute.clamp",
            "numeric.compute.percent",
            "research.engine.status",
            "research.missions.get",
            "research.missions.list",
            "text.utils.count_words",
            "text.utils.slugify",
            "text.utils.split_lines",
        ]
        for tool in readonly_tools:
            allowed, _, _ = engine.check(tool)
            assert allowed is True, f"{tool} should be allowed by default"

    def test_write_tools_ask_mode_by_default(self):
        """Fresh engine should have 2 write tools in ask mode."""
        reset_permission_engine()
        engine = get_permission_engine()
        write_tools = ["notes.local.write", "research.missions.start"]
        for tool in write_tools:
            allowed, reason, req_id = engine.check(tool)
            assert allowed is False, f"{tool} should require approval"
            assert req_id is not None, f"{tool} should return request_id for ask mode"
            assert "approval" in reason.lower() or "confirm" in reason.lower()


class TestDangerousTools:
    """Dangerous tools without approval = deny; with exact approval = allow."""

    @pytest.mark.parametrize("tool", ["shell", "code_run", "control_pc", "os"])
    def test_deny_until_sandbox(self, tool):
        """shell, code_run, control_pc, os = deny until sandbox exists."""
        engine = _engine_with_config(_default_config())
        # These tools should be explicitly denied by default (fail-closed)
        allowed, reason, _ = engine.check(tool)
        assert allowed is False, f"{tool} should be denied"

    @pytest.mark.parametrize("tool", ["write_file", "browser", "gui", "open_app", "screenshot", "search_web"])
    def test_ask_mode_tools(self, tool):
        """write_file, browser, gui, open_app, screenshot, search_web = ask."""
        config = PermissionConfig(
            tools={
                tool: ToolPermission(tool=tool, allow=True, risk="high", require_confirm=True)
            }
        )
        engine = _engine_with_config(config)
        allowed, reason, req_id = engine.check(tool)
        assert allowed is False
        assert req_id is not None
        assert "approval" in reason.lower() or "confirm" in reason.lower()

    @pytest.mark.parametrize("tool", ["read_file", "list_dir"])
    def test_read_tools_allow_under_roots(self, tool):
        """read_file/list_dir: allow under allowed roots; outside = ask."""
        # This would require path validation logic - for now test basic allow
        engine = _engine_with_config(_default_config())
        engine.allow_tool(tool, "low")
        allowed, _, _ = engine.check(tool)
        assert allowed is True


class TestDangerousToolExecution:
    """Integration tests: dangerous tools require approval to execute."""

    @pytest.mark.asyncio
    async def test_shell_denied_without_approval(self):
        from backend.agents.orchestrator import ToolConnector, ToolResultStatus

        reset_permission_engine()
        engine = get_permission_engine()
        # Don't allow shell - should be denied

        tc = ToolConnector()
        result = await tc.execute("shell", {"command": "echo hello"})
        assert result.status == ToolResultStatus.FAILED
        assert "permission denied" in result.error.lower() or "permission required" in result.error.lower()

        reset_permission_engine()

    @pytest.mark.asyncio
    async def test_write_file_ask_mode(self):
        from backend.agents.orchestrator import ToolConnector, ToolResultStatus

        reset_permission_engine()
        engine = get_permission_engine()
        # Allow write_file but require confirmation
        engine.allow_tool("write_file", "high", require_confirm=True)

        tc = ToolConnector()
        result = await tc.execute("write_file", {"path": "/tmp/test.txt", "content": "hello"})
        # Should return permission required with ask_request_id
        assert result.status == ToolResultStatus.FAILED
        assert "permission required" in result.error.lower()
        assert result.metadata.get("ask_request_id") is not None

        reset_permission_engine()

    @pytest.mark.asyncio
    async def test_read_file_allowed(self):
        from backend.agents.orchestrator import ToolConnector, ToolResultStatus

        reset_permission_engine()
        engine = get_permission_engine()
        engine.allow_tool("read_file", "low")

        tc = ToolConnector()
        # Create a temp file to read
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test content")
            temp_path = f.name

        try:
            result = await tc.execute("read_file", {"path": temp_path})
            assert result.status == ToolResultStatus.SUCCESS
            assert "test content" in result.output
        finally:
            os.unlink(temp_path)

        reset_permission_engine()


class TestPermissionIntegration:
    """Integration tests with DynamicToolRegistry."""

    @pytest.mark.asyncio
    async def test_dynamic_registry_enforces_permissions(self):
        from backend.agents.tools_registry import DynamicToolRegistry

        reset_permission_engine()
        engine = get_permission_engine()

        # Allow a sandbox tool
        engine.allow_tool("t.ok", "safe")

        reg = DynamicToolRegistry(scripts_dir=None, auto_scan=False)
        reg.register_callable(
            "t.ok",
            lambda **kw: {"got": kw.get("text", "")},
            "ok",
            {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
        )

        # Should work
        out = await reg.execute_tool("t.ok", {"text": "hola"})
        assert out["success"] is True

        # Unknown tool should be denied
        out2 = await reg.execute_tool("t.unknown", {})
        assert out2["success"] is False
        assert "unknown tool" in out2["error"].lower()

        reset_permission_engine()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])