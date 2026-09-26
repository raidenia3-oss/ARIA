"""BLOQUE 18 — Tests de configuración y diagnóstico Discord (sin secretos)."""

import os
import sys
from unittest import mock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import discord_diagnostics as dd


def test_mask_token_absent():
    assert dd._mask_token("") == "[ausente]"


def test_mask_token_short():
    assert dd._mask_token("short") == "****"


def test_mask_token_never_returns_full_token():
    token = "MTUzMTUzMTUzMTUzNTUzMTUz.NnQzXQ.abcdef1234567890"
    masked = dd._mask_token(token)
    assert token not in masked
    assert masked.startswith("MTUz") and masked.endswith("7890")


def test_validate_token_states():
    assert dd._validate_token("") == dd.VALIDATION_ABSENT
    assert dd._validate_token("abc") == dd.VALIDATION_INVALID
    assert dd._validate_token("no-dots-here") == dd.VALIDATION_INVALID
    assert dd._validate_token("MTUzMTUz.NnQzXQ.abcdef123456") == dd.VALIDATION_CONFIGURED


def test_sanitize_url_strips_credentials():
    url = dd._sanitize_url("redis://user:secretpass@localhost:6379/0")
    assert "secretpass" not in url
    assert url.startswith("redis://localhost:6379")


def test_sanitize_url_keeps_plain_url():
    assert dd._sanitize_url("redis://localhost:6379/0") == "redis://localhost:6379/0"


def test_run_diagnostics_never_exposes_token():
    fake = "MTUzMTUzMTUzMTUzNTUzMTUz.NnQzXQ.abcdef1234567890"
    with mock.patch.dict(
        os.environ,
        {
            "DISCORD_BOT_TOKEN": fake,
            "DISCORD_CLIENT_ID": "123456789012345678",
            "AURA_BACKEND_URL": "http://localhost:8000",
            "REDIS_URL": "redis://localhost:6379/0",
        },
    ):
        result = dd.run_diagnostics()
    blob = str(result)
    assert fake not in blob
    assert result["status"] in {"healthy", "degraded", "not_configured", "offline", "error"}
    checks = result["checks"]
    assert checks["token_configured"] is True
    assert checks["token_validation"] == "configured"
    assert fake not in checks["token_masked"]
    assert checks["configuration_source"].endswith(".env")


def test_run_diagnostics_not_configured(monkeypatch):
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.delenv("DISCORD_CLIENT_ID", raising=False)
    result = dd.run_diagnostics()
    assert result["status"] == "not_configured"
    assert result["checks"]["token_configured"] is False
    assert result["checks"]["token_masked"] == "[ausente]"


def test_run_diagnostics_invalid_token_is_error(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "bad")
    monkeypatch.setenv("DISCORD_CLIENT_ID", "123")
    result = dd.run_diagnostics()
    assert result["status"] == "error"
    assert result["checks"]["token_validation"] == "invalid"


def test_record_connection_error_redacts_token(caplog):
    fake = "MTUzMTUzMTUzMTUzNTUzMTUz.NnQzXQ.abcdef1234567890"
    with mock.patch.dict(os.environ, {"DISCORD_BOT_TOKEN": fake}):
        with caplog.at_level("ERROR", logger="AURADiscordDiag"):
            dd.record_connection_error(f"auth failed with {fake}")
    assert fake not in caplog.text
