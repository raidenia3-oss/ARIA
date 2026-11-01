"""Tests for backend.agents.llm_cli.redact."""

from __future__ import annotations

import re

from backend.agents.llm_cli.redact import (
    _PATTERNS,
    redact_prompt,
    redaction_report,
)


def test_redact_api_key_value_only():
    prompt = "key=abc123def456 please use it"
    out = redact_prompt(prompt)
    assert "abc123def456" not in out
    assert "key=" in out  # label preserved
    assert "[REDACTED]" in out


def test_redact_private_key_block():
    prompt = (
        "here is the key\n"
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEpAIBAAKCAQEA...\n"
        "-----END RSA PRIVATE KEY-----\n"
        "use it"
    )
    out = redact_prompt(prompt)
    assert "BEGIN RSA PRIVATE KEY" not in out
    assert "[REDACTED]" in out


def test_redact_email():
    out = redact_prompt("contact me at user@example.com thanks")
    assert "user@example.com" not in out
    assert "[REDACTED]" in out


def test_redact_url_with_secret_query():
    url = "https://api.example.com/v1?key=secret123&token=abc"
    out = redact_prompt(f"call {url} now")
    assert "secret123" not in out
    assert "abc" not in out
    assert "[REDACTED_QUERY]" in out


def test_redact_no_change_for_clean_prompt():
    clean = "what is the weather in Madrid today?"
    assert redact_prompt(clean) == clean


def test_redact_empty_returns_empty():
    assert redact_prompt("") == ""


def test_redact_extra_patterns():
    out = redact_prompt(
        "phone 555-1234",
        extra_patterns={"phone": r"\d{3}-\d{4}"},
    )
    assert "555-1234" not in out
    assert "[REDACTED]" in out


def test_redact_extra_pattern_invalid_regex_is_skipped():
    out = redact_prompt("hello [unclosed", extra_patterns={"bad": "["})
    assert out == "hello [unclosed"


def test_report_counts_matches():
    prompt = "key=abc123def456 and user@example.com"
    report = redaction_report(prompt)
    assert isinstance(report, dict)
    assert report.get("api_key", 0) >= 1
    assert report.get("email", 0) >= 1


def test_report_empty_for_clean():
    assert redaction_report("nothing here") == {}


def test_patterns_present():
    names = [n for n, _ in _PATTERNS]
    assert "api_key" in names
    assert "private_key" in names
    assert "email" in names
    assert "url_with_secret" in names