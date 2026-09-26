"""Tests for backend.discord_diagnostics — env validation, masking, diagnostics & canon recording.

Aislables: no requieren bot real ni Redis. Mockan variables de entorno y la
cache global. El .env real del repo puede existir; los tests controlan el
estado de credenciales vía monkeypatch de process env.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path, PurePosixPath

import pytest

from backend import discord_diagnostics as diag
from backend.discord_diagnostics import (
    VALIDATION_ABSENT,
    VALIDATION_CONFIGURED,
    VALIDATION_INVALID,
    _mask_token,
    _validate_token,
    get_cached_diagnostics,
    record_canon_event,
    record_connection_error,
    record_successful_connection,
    run_diagnostics,
)


def _safe_join(*parts):
    """Reemplazo de os.path.join que NO usa os.path.join (evita recursión) y
    descarta componentes '.'/'..' para redirigir todo a tmp_path."""
    wanted = [str(p) for p in parts if p not in (".", "..", "")]
    return str(PurePosixPath(*wanted))


# --------------------------------------------------------------------------- #
# masking
# --------------------------------------------------------------------------- #
class TestMaskToken:
    def test_empty(self):
        assert _mask_token("") == "[ausente]"
        assert _mask_token("   ") == "[ausente]"

    def test_short(self):
        assert _mask_token("12345") == "****"

    def test_long_keeps_prefix_and_suffix(self):
        token = "MTUwMDY4NzQ1ODM5NDcwNjEwMQ.GR04ZG.eKmF3qEwKEAg9ITV8UbyElTvDoe8SeSQB1jjdg"
        masked = _mask_token(token)
        assert masked.startswith("MTUw")
        assert masked.endswith("jjdg")
        assert "GR04ZG" not in masked  # el cuerpo secreto NO aparece
        assert masked.count("*") == 4


# --------------------------------------------------------------------------- #
# token validation (formato 3 partes)
# --------------------------------------------------------------------------- #
class TestValidateToken:
    def test_absent(self):
        assert _validate_token("") == VALIDATION_ABSENT
        assert _validate_token("   ") == VALIDATION_ABSENT

    def test_invalid_short(self):
        assert _validate_token("abc") == VALIDATION_INVALID

    def test_invalid_two_parts(self):
        assert _validate_token("aa.bb") == VALIDATION_INVALID

    def test_invalid_empty_parts(self):
        assert _validate_token("..") == VALIDATION_INVALID

    def test_configured(self):
        assert _validate_token("MTAw.MTkx.GR04ZG") == VALIDATION_CONFIGURED


# --------------------------------------------------------------------------- #
# run_diagnostics — estados y shaping
# --------------------------------------------------------------------------- #
class TestRunDiagnostics:
    def test_not_configured(self, monkeypatch):
        monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
        monkeypatch.delenv("DISCORD_CLIENT_ID", raising=False)
        result = run_diagnostics()
        assert result["status"] == "not_configured"
        c = result["checks"]
        assert c["token_validation"] == VALIDATION_ABSENT
        assert c["token_masked"] == "[ausente]"
        src = c["configuration_source"].replace("\\", "/")
        assert src.endswith("services/discord-bot/.env")

    def test_status_is_valid_member(self, monkeypatch):
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "MTAw.MTkx.GR04ZG")
        monkeypatch.setenv("DISCORD_CLIENT_ID", "123")
        result = run_diagnostics()
        assert result["status"] in {"healthy", "degraded", "offline", "error", "not_configured"}
        c = result["checks"]
        assert c["token_validation"] == VALIDATION_CONFIGURED
        # el token real NUNCA aparece en la respuesta
        assert "GR04ZG" not in repr(c["token_masked"])
        assert c["token_masked"].startswith("MTAw")

    def test_never_exposes_token_in_last_error(self, monkeypatch):
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "MTAw.MTkx.GR04ZG_secret_tail")
        monkeypatch.setenv("DISCORD_CLIENT_ID", "123")
        monkeypatch.setenv("AURA_BACKEND_URL", "http://127.0.0.1:1")  # port closed -> error
        result = run_diagnostics()
        assert "GR04ZG_secret_tail" not in result["checks"]["last_error"]
        assert "MTAw" not in result["checks"]["last_error"]


# --------------------------------------------------------------------------- #
# cache de get_cached_diagnostics
# --------------------------------------------------------------------------- #
class TestDiagCache:
    def test_uses_cached_when_fresh(self, monkeypatch):
        diag.discord_diag_cache.clear()
        diag.discord_diag_cache["expires"] = time.time() + 25
        diag.discord_diag_cache["data"] = {"status": "cached_value"}
        result = get_cached_diagnostics()
        assert result["status"] == "cached_value"

    def test_refreshes_when_expired(self, monkeypatch):
        diag.discord_diag_cache.clear()
        diag.discord_diag_cache["expires"] = time.time() - 1  # expirada
        monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
        monkeypatch.delenv("DISCORD_CLIENT_ID", raising=False)
        result = get_cached_diagnostics()
        assert result["status"] == "not_configured"

    def test_cache_ttl_is_30s(self):
        assert diag._discord_diag_interval == 30


# --------------------------------------------------------------------------- #
# grabación de canon y conexión
# --------------------------------------------------------------------------- #
@pytest.fixture
def redirected_data(tmp_path, monkeypatch):
    """Redirige backend/data/ a tmp_path/data/ sin recursión en os.path.join
    ni corrupción del dirname global (que rompería makedirs interno)."""
    monkeypatch.setattr(diag.os.path, "join", _safe_join)
    _orig_dirname = diag.os.path.dirname

    def _redirected_dirname(p):
        if str(p) == str(Path(diag.__file__).resolve()):
            return str(tmp_path)
        return _orig_dirname(p)

    monkeypatch.setattr(diag.os.path, "dirname", _redirected_dirname)


class TestRecordCanon:
    def test_canon_event_persisted(self, redirected_data, tmp_path):
        ok = record_canon_event("work1", "evt123", "discord", "narrativa de prueba")
        assert ok is True
        canon_file = tmp_path / "data" / "discord_canon_feed.json"
        assert canon_file.exists()
        feed = json.loads(canon_file.read_text())
        assert isinstance(feed, list)
        assert feed[-1]["work_id"] == "work1"
        assert feed[-1]["event_id"] == "evt123"
        assert feed[-1]["description"] == "narrativa de prueba"

    def test_canon_event_truncates_long_description(self, redirected_data, tmp_path):
        long_desc = "x" * 300
        record_canon_event("work2", "evt456", "discord", long_desc)
        feed = json.loads((tmp_path / "data" / "discord_canon_feed.json").read_text())
        assert feed[-1]["description"] == "x" * 200
        assert len(feed[-1]["description"]) == 200

    def test_canon_event_does_not_crash_on_missing_desc(self, redirected_data, tmp_path):
        ok = record_canon_event("work3", "evt789", "discord", "")
        assert ok is True


class TestConnectionRecording:
    def test_successful_connection_writes_timestamp(self, redirected_data, tmp_path):
        record_successful_connection()
        conn_file = tmp_path / "data" / "discord_last_connection.txt"
        assert conn_file.exists()
        content = conn_file.read_text().strip()
        # ISO-8601 con tz: YYYY-MM-DDTHH:MM:SS+TZ
        assert content[:4].isdigit() and content[5:7].isdigit()

    def test_error_redacts_token(self, redirected_data, monkeypatch, caplog):
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "SECRET_TOKEN_XYZ")
        record_connection_error("Fallo con token SECRET_TOKEN_XYZ tail")
        assert "SECRET_TOKEN_XYZ" not in caplog.text
        assert "[redacted]" in caplog.text
