"""Tests for backend.agents.llm_cli.provider (GeminiCLIService).

All subprocess interactions are mocked. No real CLI is invoked.
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path
from unittest import mock

import pytest

from backend.agents.llm_cli.provider import (
    CLICallResult,
    GeminiCLIService,
    PROVIDER_NAME,
    _binary_available,
    _build_env,
    _has_api_key_env,
    _parse_cli_output,
    _truncate_output,
    get_gemini_cli_service,
    reset_gemini_cli_service,
)
from backend.agents.llm_cli.quota import QuotaConfig, QuotaManager, reset_quota_manager


# --- helpers ----------------------------------------------------------------

def _fake_proc(returncode=0, stdout=b"", stderr=b""):
    proc = mock.MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


def _make_service(tmp_path, quota_limit=0, **kwargs):
    state_path = str(tmp_path / "quota.json")
    quota = QuotaManager(
        state_path=state_path,
        config=QuotaConfig(max_calls_per_day=quota_limit, cooldown_seconds=60.0),
    )
    return GeminiCLIService(quota=quota, **kwargs)


# --- unit tests for helpers ---

def test_build_env_excludes_api_keys(monkeypatch):
    monkeypatch.setenv("MY_SECRET_API_KEY", "should-not-leak")
    monkeypatch.setenv("GROQ_API_KEY", "also-secret")
    monkeypatch.setenv("PATH", "/usr/bin")
    env = _build_env()
    assert "MY_SECRET_API_KEY" not in env
    assert "GROQ_API_KEY" not in env
    assert env.get("PATH") == "/usr/bin"
    assert _has_api_key_env(env) is False


def test_build_env_allowlist_only(monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("SECRET_THING", "no")
    env = _build_env(extra={"SECRET_THING": "x", "PATH": "/custom"})
    assert "SECRET_THING" not in env
    assert env["PATH"] == "/custom"


def test_truncate_output_under_cap():
    raw = b"hello world"
    text, truncated = _truncate_output(raw, 1024)
    assert text == "hello world"
    assert truncated is False


def test_truncate_output_over_cap():
    raw = b"x" * 5000
    text, truncated = _truncate_output(raw, 100)
    assert len(text) == 100
    assert truncated is True


def test_parse_cli_output_text_passthrough():
    assert _parse_cli_output("plain text", "text") == "plain text"


def test_parse_cli_output_json_response_key():
    raw = '{"response": "hi"}'
    assert _parse_cli_output(raw, "json") == "hi"


def test_parse_cli_output_json_message_content():
    raw = '{"message": {"content": "nested"}}'
    assert _parse_cli_output(raw, "json") == "nested"


def test_parse_cli_output_json_fallback():
    raw = '{"foo": "bar"}'
    out = _parse_cli_output(raw, "json")
    assert "foo" in out


def test_parse_cli_output_invalid_json_returns_raw():
    raw = "not json at all"
    assert _parse_cli_output(raw, "json") == raw


def test_binary_available_uses_shutil_which():
    with mock.patch("backend.agents.llm_cli.provider.shutil.which", return_value="/usr/bin/gemini"):
        assert _binary_available() is True
    with mock.patch("backend.agents.llm_cli.provider.shutil.which", return_value=None):
        assert _binary_available() is False


# --- subprocess-mocked tests ---

def test_missing_cli_binary_reports_unavailable(tmp_path):
    """CLI not on PATH -> unavailable=True, no subprocess spawned."""
    svc = _make_service(tmp_path, cli_binary="nonexistent_gemini_cli_xyz")
    with mock.patch("backend.agents.llm_cli.provider.shutil.which", return_value=None):
        with mock.patch("backend.agents.llm_cli.provider.subprocess.run") as mocked:
            result = svc.invoke(prompt="hello")
    assert result.unavailable is True
    assert result.success is False
    assert "not found" in (result.error or "").lower()
    mocked.assert_not_called()


def test_timeout_returns_failure(tmp_path):
    svc = _make_service(tmp_path, timeout_s=0.05)

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=kwargs.get("args", ["gemini"]), timeout=0.05)

    with mock.patch("backend.agents.llm_cli.provider.shutil.which", return_value="/usr/bin/gemini"):
        with mock.patch("backend.agents.llm_cli.provider.subprocess.run", side_effect=fake_run):
            result = svc.invoke(prompt="hello")
    assert result.success is False
    assert "timed out" in (result.error or "").lower()


def test_nonzero_exit_returns_failure(tmp_path):
    svc = _make_service(tmp_path)
    proc = _fake_proc(returncode=1, stderr=b"some error")
    with mock.patch("backend.agents.llm_cli.provider.shutil.which", return_value="/usr/bin/gemini"):
        with mock.patch("backend.agents.llm_cli.provider.subprocess.run", return_value=proc):
            result = svc.invoke(prompt="hello")
    assert result.success is False
    assert result.exit_code == 1
    assert "exited with code 1" in (result.error or "")


def test_success_parses_json(tmp_path):
    svc = _make_service(tmp_path)
    proc = _fake_proc(returncode=0, stdout=b'{"response": "hello from gemini"}')
    with mock.patch("backend.agents.llm_cli.provider.shutil.which", return_value="/usr/bin/gemini"):
        with mock.patch("backend.agents.llm_cli.provider.subprocess.run", return_value=proc):
            result = svc.invoke(prompt="hello")
    assert result.success is True
    assert result.output == "hello from gemini"
    assert result.exit_code == 0


def test_huge_output_truncated(tmp_path):
    svc = _make_service(tmp_path, max_output_bytes=100)
    big = b'{"response": "' + b"A" * 5000 + b'"}'
    proc = _fake_proc(returncode=0, stdout=big)
    with mock.patch("backend.agents.llm_cli.provider.shutil.which", return_value="/usr/bin/gemini"):
        with mock.patch("backend.agents.llm_cli.provider.subprocess.run", return_value=proc):
            result = svc.invoke(prompt="hello")
    assert result.success is True
    assert result.truncated is True
    assert len(result.output) <= 100


def test_env_passed_to_subprocess_has_no_api_keys(tmp_path):
    """The env passed to subprocess.run must not contain *_API_KEY."""
    svc = _make_service(tmp_path)
    proc = _fake_proc(returncode=0, stdout=b'{"response": "ok"}')
    captured = {}

    def fake_run(args, **kwargs):
        captured["env"] = kwargs.get("env", {})
        return proc

    with mock.patch("backend.agents.llm_cli.provider.shutil.which", return_value="/usr/bin/gemini"):
        with mock.patch("backend.agents.llm_cli.provider.subprocess.run", side_effect=fake_run):
            svc.invoke(prompt="hello")
    env = captured["env"]
    for key in env:
        assert not key.upper().endswith("_API_KEY")
        assert key.upper() != "API_KEY"


def test_subprocess_called_with_list_not_shell(tmp_path):
    svc = _make_service(tmp_path)
    proc = _fake_proc(returncode=0, stdout=b'{"response": "ok"}')
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return proc

    with mock.patch("backend.agents.llm_cli.provider.shutil.which", return_value="/usr/bin/gemini"):
        with mock.patch("backend.agents.llm_cli.provider.subprocess.run", side_effect=fake_run):
            svc.invoke(prompt="hello", model="gemini-2.0-flash", read_only=True)
    assert isinstance(captured["args"], list)
    assert captured["kwargs"].get("shell") is False
    assert captured["args"][0] == "gemini"
    assert "--approval-mode" in captured["args"]
    assert "plan" in captured["args"]
    assert "--output-format" in captured["args"]
    assert "--model" in captured["args"]


def test_lock_serializes_calls(tmp_path):
    """Only one call at a time: concurrent invokes serialize on the Lock."""
    svc = _make_service(tmp_path)
    proc = _fake_proc(returncode=0, stdout=b'{"response": "ok"}')
    active = {"count": 0, "max_concurrent": 0}
    lock_events = []

    def fake_run(args, **kwargs):
        active["count"] += 1
        active["max_concurrent"] = max(active["max_concurrent"], active["count"])
        time.sleep(0.05)
        active["count"] -= 1
        return proc

    with mock.patch("backend.agents.llm_cli.provider.shutil.which", return_value="/usr/bin/gemini"):
        with mock.patch("backend.agents.llm_cli.provider.subprocess.run", side_effect=fake_run):
            threads = [
                threading.Thread(target=svc.invoke, kwargs={"prompt": f"hello {i}"})
                for i in range(5)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
    assert active["max_concurrent"] == 1


def test_injection_in_output_not_executed(tmp_path):
    """CLI output containing a shell injection string is never executed.

    The output is data, not code. We verify subprocess.run is only ever
    called once with the original args, never with a command derived from
    the output.
    """
    svc = _make_service(tmp_path)
    injection = b'{"response": "ok"; import os; os.system("echo pwned")}'
    proc = _fake_proc(returncode=0, stdout=injection)
    captured = []

    def fake_run(args, **kwargs):
        captured.append(list(args))
        return proc

    with mock.patch("backend.agents.llm_cli.provider.shutil.which", return_value="/usr/bin/gemini"):
        with mock.patch("backend.agents.llm_cli.provider.subprocess.run", side_effect=fake_run):
            result = svc.invoke(prompt="hello")
    assert result.success is True
    assert "os.system" in result.output  # it is data, preserved as text
    assert len(captured) == 1  # only the original call, never a second one
    assert "echo pwned" not in " ".join(captured[0])


def test_quota_counter_increments(tmp_path):
    """Each call increments the measured counter."""
    svc = _make_service(tmp_path, quota_limit=10)
    proc = _fake_proc(returncode=0, stdout=b'{"response": "ok"}')
    with mock.patch("backend.agents.llm_cli.provider.shutil.which", return_value="/usr/bin/gemini"):
        with mock.patch("backend.agents.llm_cli.provider.subprocess.run", return_value=proc):
            svc.invoke(prompt="hello")
            svc.invoke(prompt="hello again")
    assert svc.quota.state()["calls_measured"] == 2


def test_quota_exhausted_blocks_call(tmp_path):
    svc = _make_service(tmp_path, quota_limit=1)
    proc = _fake_proc(returncode=0, stdout=b'{"response": "ok"}')
    with mock.patch("backend.agents.llm_cli.provider.shutil.which", return_value="/usr/bin/gemini"):
        with mock.patch("backend.agents.llm_cli.provider.subprocess.run", return_value=proc):
            first = svc.invoke(prompt="hello")
            assert first.success is True
            second = svc.invoke(prompt="hello again")
    assert second.success is False
    assert "quota exhausted" in (second.error or "").lower()
    assert second.quota_state.get("in_cooldown") is True


def test_redaction_report_present(tmp_path):
    svc = _make_service(tmp_path)
    proc = _fake_proc(returncode=0, stdout=b'{"response": "ok"}')
    with mock.patch("backend.agents.llm_cli.provider.shutil.which", return_value="/usr/bin/gemini"):
        with mock.patch("backend.agents.llm_cli.provider.subprocess.run", return_value=proc):
            result = svc.invoke(prompt="my key=secret123 please use it")
    assert result.redaction.get("api_key", 0) >= 1


def test_redacted_prompt_sent_to_cli(tmp_path):
    """The prompt reaching subprocess.run must be the redacted one."""
    svc = _make_service(tmp_path)
    proc = _fake_proc(returncode=0, stdout=b'{"response": "ok"}')
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = list(args)
        return proc

    with mock.patch("backend.agents.llm_cli.provider.shutil.which", return_value="/usr/bin/gemini"):
        with mock.patch("backend.agents.llm_cli.provider.subprocess.run", side_effect=fake_run):
            svc.invoke(prompt="contact user@example.com key=abc123def456")
    prompt_arg = captured["args"][-1]
    assert "user@example.com" not in prompt_arg
    assert "abc123def456" not in prompt_arg


def test_provider_name_constant():
    assert PROVIDER_NAME == "official_cli"


def test_state_snapshot(tmp_path):
    svc = _make_service(tmp_path)
    st = svc.state()
    assert st["provider"] == "official_cli"
    assert "available" in st
    assert "quota" in st


def test_singleton_get_and_reset(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_GEMINI_CLI_QUOTA_STATE", str(tmp_path / "q.json"))
    reset_quota_manager()
    reset_gemini_cli_service()
    a = get_gemini_cli_service()
    b = get_gemini_cli_service()
    assert a is b
    reset_gemini_cli_service()
    c = get_gemini_cli_service()
    assert c is not a