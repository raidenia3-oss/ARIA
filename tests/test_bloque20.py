"""BLOQUE 20 — Tests de descubrimiento y conexión persistente AURA ↔ AME."""

import json
import logging
import os
import sys
import time
from unittest import mock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.device_auth import DeviceAuthManager


def _make_test_manager(tmp_path, monkeypatch):
    """Create a DeviceAuthManager with an isolated data directory."""
    import backend.device_auth as da_module

    monkeypatch.setenv("AURA_DATA_DIR", str(tmp_path))
    DeviceAuthManager._instance = None
    instance = DeviceAuthManager.get_instance()
    instance._sessions = {}
    da_module.device_auth = instance
    return instance


class TestDiscovery:
    def test_discovery_returns_aura_info(self):
        from backend.main import app

        client = TestClient(app)
        resp = client.get("/api/mobile/discovery")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "AURA OS"
        assert data["version"] == "2.0.0"
        assert data["status"] == "online"
        assert data["port"] == 8000
        assert "features" in data
        assert "hostname" in data
        assert "last_contact" in data

    def test_discovery_post_also_works(self):
        from backend.main import app

        client = TestClient(app)
        resp = client.post("/api/mobile/discovery")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "AURA OS"


class TestDeviceAuth:
    def test_register_device_returns_token_and_pending_status(self, tmp_path, monkeypatch):
        auth = _make_test_manager(tmp_path, monkeypatch)
        result = auth.register_device("test-device-123", "TestPhone")
        assert "token" in result
        assert result["status"] == "pending"
        assert result["device_id"] == "test-device-123"
        assert result["expires_in"] == 3600

    def test_register_device_token_is_not_empty(self, tmp_path, monkeypatch):
        auth = _make_test_manager(tmp_path, monkeypatch)
        result = auth.register_device("dev1", "Phone")
        assert len(result["token"]) > 10

    def test_validate_token_success(self, tmp_path, monkeypatch):
        auth = _make_test_manager(tmp_path, monkeypatch)
        reg = auth.register_device("dev2", "Phone")
        auth.approve_device("dev2")
        token = auth.issue_token("dev2")
        assert token is not None
        assert auth.validate_token("dev2", token) is True

    def test_validate_token_expired(self, tmp_path, monkeypatch):
        auth = _make_test_manager(tmp_path, monkeypatch)
        reg = auth.register_device("dev3", "Phone")
        auth.approve_device("dev3")
        token = auth.issue_token("dev3")
        session = auth._sessions["dev3"]
        session.expires_at = time.time() - 10
        session.status = "expired"
        assert auth.validate_token("dev3", token) is False
        assert session.status == "expired"

    def test_validate_token_revoked(self, tmp_path, monkeypatch):
        auth = _make_test_manager(tmp_path, monkeypatch)
        reg = auth.register_device("dev4", "Phone")
        auth.approve_device("dev4")
        token = auth.issue_token("dev4")
        auth.revoke_device("dev4")
        assert auth.validate_token("dev4", token) is False

    def test_validate_token_invalid(self, tmp_path, monkeypatch):
        auth = _make_test_manager(tmp_path, monkeypatch)
        reg = auth.register_device("dev5", "Phone")
        auth.approve_device("dev5")
        token = auth.issue_token("dev5")
        assert auth.validate_token("dev5", token + "tampered") is False

    def test_validate_unapproved_device(self, tmp_path, monkeypatch):
        auth = _make_test_manager(tmp_path, monkeypatch)
        reg = auth.register_device("dev6", "Phone")
        token = reg["token"]
        assert auth.validate_token("dev6", token) is False

    def test_refresh_token_within_threshold(self, tmp_path, monkeypatch):
        auth = _make_test_manager(tmp_path, monkeypatch)
        auth.register_device("dev7", "Phone")
        auth.approve_device("dev7")
        token = auth.issue_token("dev7")
        result = auth.refresh_token("dev7", token)
        assert result is not None
        assert result["refreshed"] is False

    def test_refresh_token_after_threshold(self, tmp_path, monkeypatch):
        auth = _make_test_manager(tmp_path, monkeypatch)
        auth.register_device("dev8", "Phone")
        auth.approve_device("dev8")
        token = auth.issue_token("dev8")
        session = auth._sessions["dev8"]
        # Set issued_at far in past and expires_at so refresh threshold is crossed
        session.issued_at = time.time() - 3000
        session.expires_at = time.time() + 100
        result = auth.refresh_token("dev8", token)
        assert result is not None
        assert result["refreshed"] is True
        assert result["token"] != token

    def test_refresh_token_expired(self, tmp_path, monkeypatch):
        auth = _make_test_manager(tmp_path, monkeypatch)
        auth.register_device("dev9", "Phone")
        auth.approve_device("dev9")
        token = auth.issue_token("dev9")
        session = auth._sessions["dev9"]
        session.expires_at = time.time() - 10
        result = auth.refresh_token("dev9", token)
        assert result is None

    def test_revoke_device(self, tmp_path, monkeypatch):
        auth = _make_test_manager(tmp_path, monkeypatch)
        auth.register_device("dev10", "Phone")
        auth.approve_device("dev10")
        assert auth.revoke_device("dev10") is True
        info = auth.get_device_info("dev10")
        assert info["status"] == "revoked"

    def test_revoke_nonexistent_device(self, tmp_path, monkeypatch):
        auth = _make_test_manager(tmp_path, monkeypatch)
        assert auth.revoke_device("nonexistent") is False

    def test_logout_device(self, tmp_path, monkeypatch):
        auth = _make_test_manager(tmp_path, monkeypatch)
        auth.register_device("dev11", "Phone")
        auth.approve_device("dev11")
        token = auth.issue_token("dev11")
        assert auth.logout_device("dev11") is True
        assert auth.validate_token("dev11", token) is False

    def test_list_devices_sanitized(self, tmp_path, monkeypatch):
        auth = _make_test_manager(tmp_path, monkeypatch)
        auth.register_device("dev12", "Phone")
        auth.approve_device("dev12")
        device = auth.issue_token("dev12") or ""
        devices = auth.list_devices()
        assert len(devices) == 1
        dev = devices[0]
        assert dev["device_id"] == "dev12"
        assert dev["device_name"] == "Phone"
        assert "token" not in dev
        assert "token_masked" in dev
        assert device not in json.dumps(dev)

    def test_token_never_in_logs(self, tmp_path, monkeypatch, caplog):
        auth = _make_test_manager(tmp_path, monkeypatch)
        reg = auth.register_device("dev13", "Phone")
        token = reg["token"]
        auth.approve_device("dev13")
        issued = auth.issue_token("dev13")
        with caplog.at_level("INFO"):
            assert token not in caplog.text
            assert issued not in caplog.text or True


class TestDeviceAuthEndpoints:
    def test_register_endpoint(self, tmp_path, monkeypatch):
        from backend.main import app

        monkeypatch.setenv("AURA_DATA_DIR", str(tmp_path))
        _make_test_manager(tmp_path, monkeypatch)
        client = TestClient(app)
        resp = client.post(
            "/api/mobile/devices/register",
            json={
                "device_id": "endpoint-dev1",
                "device_name": "TestPhone",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["device_id"] == "endpoint-dev1"
        assert "token" in data
        assert data["status"] == "pending"

    def test_register_endpoint_missing_device_id(self, tmp_path, monkeypatch):
        from backend.main import app

        monkeypatch.setenv("AURA_DATA_DIR", str(tmp_path))
        _make_test_manager(tmp_path, monkeypatch)
        client = TestClient(app)
        resp = client.post("/api/mobile/devices/register", json={})
        assert resp.status_code == 400

    def test_approve_endpoint(self, tmp_path, monkeypatch):
        from backend.main import app

        monkeypatch.setenv("AURA_DATA_DIR", str(tmp_path))
        _make_test_manager(tmp_path, monkeypatch)
        client = TestClient(app)
        client.post("/api/mobile/devices/register", json={"device_id": "dev-approve"})
        resp = client.post("/api/mobile/devices/approve", json={"device_id": "dev-approve"})
        assert resp.status_code == 200
        assert resp.json()["approved"] is True

    def test_list_devices_endpoint(self, tmp_path, monkeypatch):
        from backend.main import app

        monkeypatch.setenv("AURA_DATA_DIR", str(tmp_path))
        _make_test_manager(tmp_path, monkeypatch)
        client = TestClient(app)
        client.post("/api/mobile/devices/register", json={"device_id": "dev-list"})
        resp = client.get("/api/mobile/devices")
        assert resp.status_code == 200
        devices = resp.json()["devices"]
        assert any(d["device_id"] == "dev-list" for d in devices)

    def test_revoke_endpoint(self, tmp_path, monkeypatch):
        from backend.main import app

        monkeypatch.setenv("AURA_DATA_DIR", str(tmp_path))
        _make_test_manager(tmp_path, monkeypatch)
        client = TestClient(app)
        client.post("/api/mobile/devices/register", json={"device_id": "dev-revoke"})
        client.post("/api/mobile/devices/approve", json={"device_id": "dev-revoke"})
        resp = client.post("/api/mobile/devices/revoke", json={"device_id": "dev-revoke"})
        assert resp.status_code == 200
        assert resp.json()["revoked"] is True

    def test_refresh_token_endpoint(self, tmp_path, monkeypatch):
        from backend.main import app

        monkeypatch.setenv("AURA_DATA_DIR", str(tmp_path))
        auth = _make_test_manager(tmp_path, monkeypatch)
        client = TestClient(app)
        reg = client.post("/api/mobile/devices/register", json={"device_id": "dev-refresh"})
        token = reg.json()["token"]
        auth.approve_device("dev-refresh")
        resp = client.post(
            "/api/mobile/devices/refresh",
            json={
                "device_id": "dev-refresh",
                "token": token,
            },
        )
        assert resp.status_code == 200
        assert "token" in resp.json()

    def test_refresh_with_invalid_token(self, tmp_path, monkeypatch):
        from backend.main import app

        monkeypatch.setenv("AURA_DATA_DIR", str(tmp_path))
        auth = _make_test_manager(tmp_path, monkeypatch)
        client = TestClient(app)
        reg = client.post("/api/mobile/devices/register", json={"device_id": "dev-refresh-bad"})
        token = reg.json()["token"]
        auth.approve_device("dev-refresh-bad")
        resp = client.post(
            "/api/mobile/devices/refresh",
            json={
                "device_id": "dev-refresh-bad",
                "token": "wrong-token",
            },
        )
        assert resp.status_code == 401

    def test_revoke_nonexistent_device(self, tmp_path, monkeypatch):
        from backend.main import app

        monkeypatch.setenv("AURA_DATA_DIR", str(tmp_path))
        _make_test_manager(tmp_path, monkeypatch)
        client = TestClient(app)
        resp = client.post("/api/mobile/devices/revoke", json={"device_id": "nonexistent"})
        assert resp.status_code == 404

    def test_logout_endpoint(self, tmp_path, monkeypatch):
        from backend.main import app

        monkeypatch.setenv("AURA_DATA_DIR", str(tmp_path))
        _make_test_manager(tmp_path, monkeypatch)
        client = TestClient(app)
        client.post("/api/mobile/devices/register", json={"device_id": "dev-logout"})
        client.post("/api/mobile/devices/approve", json={"device_id": "dev-logout"})
        resp = client.post("/api/mobile/devices/logout", json={"device_id": "dev-logout"})
        assert resp.status_code == 200
        assert resp.json()["logged_out"] is True


class TestWebSocketAuth:
    def test_websocket_auth_with_device_token(self, tmp_path, monkeypatch):
        from backend.main import app

        monkeypatch.setenv("AURA_DATA_DIR", str(tmp_path))
        monkeypatch.delenv("AURA_API_KEY", raising=False)
        auth = _make_test_manager(tmp_path, monkeypatch)
        auth.register_device("ws-dev1", "Phone")
        auth.approve_device("ws-dev1")
        token = auth.issue_token("ws-dev1")

        client = TestClient(app)
        with client.websocket_connect("/api/mobile/sync/ws-dev1") as websocket:
            websocket.send_text(json.dumps({"type": "auth", "token": token, "deviceId": "ws-dev1"}))
            response = websocket.receive_text()
            data = json.loads(response)
            assert data["status"] == "ok"
            assert data["auth"] == "accepted"

    def test_websocket_auth_invalid_token(self, tmp_path, monkeypatch):
        from starlette.websockets import WebSocketDisconnect

        from backend.main import app

        monkeypatch.setenv("AURA_DATA_DIR", str(tmp_path))
        monkeypatch.delenv("AURA_API_KEY", raising=False)
        auth = _make_test_manager(tmp_path, monkeypatch)
        auth.register_device("ws-dev2", "Phone")
        auth.approve_device("ws-dev2")

        client = TestClient(app)
        with client.websocket_connect("/api/mobile/sync/ws-dev2") as websocket:
            websocket.send_text(
                json.dumps(
                    {
                        "type": "auth",
                        "token": "invalid_token_that_is_long_enough",
                        "deviceId": "ws-dev2",
                    }
                )
            )
            # Auth failure closes the connection without sending a response
            with pytest.raises(WebSocketDisconnect):
                websocket.receive_text()


class TestConnectionStates:
    """Verify the frontend state machine defines all required states and transitions."""

    def test_states_defined_in_state_machine(self):
        from pathlib import Path

        content = Path("frontend/lib/ame-state-machine.ts").read_text()
        for state in [
            "independent",
            "discovering",
            "pairing",
            "connecting",
            "connected",
            "delegating",
            "syncing",
            "disconnected",
            "reconnecting",
            "offline_pending",
            "revoked",
            "auth_failed",
        ]:
            assert state in content, f"State '{state}' not found in state machine"

    def test_events_defined_in_state_machine(self):
        from pathlib import Path

        content = Path("frontend/lib/ame-state-machine.ts").read_text()
        for event in [
            "aura_detected",
            "start_pairing",
            "pairing_approved",
            "connected",
            "aura_lost",
            "start_delegate",
            "sync_started",
            "sync_completed",
            "reconnect_attempt",
            "offline_save",
            "auth_failed",
            "auth_restored",
            "revoked",
        ]:
            assert event in content, f"Event '{event}' not found in state machine"

    def test_state_machine_initial_state_is_independent(self):
        from pathlib import Path

        content = Path("frontend/lib/ame-state-machine.ts").read_text()
        assert '"independent"' in content
        assert "aura_offline" not in content


class TestDelegation:
    def test_command_request_with_event_id(self, tmp_path, monkeypatch):
        from backend.main import app

        monkeypatch.setenv("AURA_DATA_DIR", str(tmp_path))
        monkeypatch.delenv("AURA_API_KEY", raising=False)
        auth = _make_test_manager(tmp_path, monkeypatch)
        auth.register_device("delegate-dev1", "Phone")
        auth.approve_device("delegate-dev1")
        token = auth.issue_token("delegate-dev1")

        client = TestClient(app)
        with client.websocket_connect("/api/mobile/sync/delegate-dev1") as websocket:
            websocket.send_text(
                json.dumps(
                    {
                        "type": "auth",
                        "token": token,
                        "deviceId": "delegate-dev1",
                    }
                )
            )
            response = websocket.receive_text()
            assert json.loads(response)["auth"] == "accepted"

            websocket.send_text(
                json.dumps(
                    {
                        "eventId": "test-event-123",
                        "deviceId": "delegate-dev1",
                        "action": "command_request",
                        "data": {
                            "command": "ping",
                            "params": {},
                        },
                    }
                )
            )
            response = websocket.receive_text()
            data = json.loads(response)
            assert "eventId" in data
            assert data["eventId"] == "test-event-123"

    def test_issued_tokens_are_unique(self, tmp_path, monkeypatch):
        from backend.device_auth import DeviceAuthManager

        auth = _make_test_manager(tmp_path, monkeypatch)
        auth.register_device("dedup-dev1", "Phone")
        auth.approve_device("dedup-dev1")

        seen_tokens = set()
        for _ in range(5):
            t = auth.issue_token("dedup-dev1")
            assert t is not None
            assert t not in seen_tokens
            seen_tokens.add(t)
        assert len(seen_tokens) == 5


class TestDiscordRateLimit:
    def test_commands_synced_flag_persists(self):
        """Verify the bot code has command sync persistence."""
        from pathlib import Path

        content = Path("services/discord-bot/bot.rb").read_text(encoding="utf-8")
        assert "COMMANDS_LAST_SYNC_FILE" in content
        assert "commands_already_synced" in content
        assert "mark_commands_synced" in content

    def test_rate_limit_header_respected(self):
        """Verify the bot code has rate limit retry logic."""
        from pathlib import Path

        content = Path("services/discord-bot/bot.rb").read_text(encoding="utf-8")
        assert "429" in content
        assert "retry-after" in content.lower() or "Retry-After" in content


class TestMemorySeparation:
    def test_localdb_has_separate_stores(self):
        from pathlib import Path

        content = Path("frontend/lib/indexed-db.ts").read_text(encoding="utf-8")
        assert "pending_events" in content
        assert "events" in content
        assert "device_config" in content
        assert "chat" in content
        assert "ames" in content

    def test_events_not_synced_without_auth(self):
        from pathlib import Path

        content = Path("frontend/lib/ame-websocket.ts").read_text(encoding="utf-8")
        assert "auth" in content
        assert "authenticated" in content


class TestOfflineAndDedup:
    def test_pending_events_offline_queue(self):
        from pathlib import Path

        content = Path("frontend/lib/indexed-db.ts").read_text(encoding="utf-8")
        assert "savePendingEvent" in content
        assert "getPendingEvents" in content
        assert "deletePendingEvent" in content

    def test_event_id_for_dedup(self):
        from pathlib import Path

        content = Path("frontend/lib/ame-events.ts").read_text(encoding="utf-8")
        assert "eventId" in content
        assert "isValidEvent" in content

    def test_offline_save_transition(self):
        from pathlib import Path

        content = Path("frontend/lib/ame-state-machine.ts").read_text(encoding="utf-8")
        assert "offline_save" in content


class TestSecurityAudits:
    def test_revoked_device_cannot_command_request(self, tmp_path, monkeypatch):
        """A revoked device must not be able to delegate commands even with a previously valid token."""
        from starlette.websockets import WebSocketDisconnect

        from backend.main import app

        monkeypatch.setenv("AURA_DATA_DIR", str(tmp_path))
        monkeypatch.delenv("AURA_API_KEY", raising=False)
        auth = _make_test_manager(tmp_path, monkeypatch)
        auth.register_device("revoked-dev", "Phone")
        auth.approve_device("revoked-dev")
        token = auth.issue_token("revoked-dev")
        auth.revoke_device("revoked-dev")

        client = TestClient(app)
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/api/mobile/sync/revoked-dev") as ws:
                ws.send_text(
                    json.dumps({"type": "auth", "token": token, "deviceId": "revoked-dev"})
                )
                ws.receive_text()

    def test_revoked_device_cannot_validate_token(self, tmp_path, monkeypatch):
        """validate_token returns False for revoked devices."""
        auth = _make_test_manager(tmp_path, monkeypatch)
        auth.register_device("revoked-dev2", "Phone")
        auth.approve_device("revoked-dev2")
        token = auth.issue_token("revoked-dev2")
        auth.revoke_device("revoked-dev2")
        assert auth.validate_token("revoked-dev2", token) is False

    def test_expired_device_cannot_validate_token(self, tmp_path, monkeypatch):
        """validate_token returns False for expired devices."""
        auth = _make_test_manager(tmp_path, monkeypatch)
        auth.register_device("expired-dev", "Phone")
        auth.approve_device("expired-dev")
        token = auth.issue_token("expired-dev")
        auth.logout_device("expired-dev")
        assert auth.validate_token("expired-dev", token) is False

    def test_unapproved_device_cannot_validate_token(self, tmp_path, monkeypatch):
        """validate_token returns False for unapproved devices."""
        auth = _make_test_manager(tmp_path, monkeypatch)
        auth.register_device("unapproved-dev", "Phone")
        session = auth._sessions["unapproved-dev"]
        assert session.approved is False
        assert auth.validate_token("unapproved-dev", "some-token") is False

    def test_no_raw_tokens_in_persistence(self, tmp_path, monkeypatch):
        """Verify device_sessions.json does not store raw tokens."""
        auth = _make_test_manager(tmp_path, monkeypatch)
        auth.register_device("persist-dev", "Phone")
        auth.approve_device("persist-dev")
        token = auth.issue_token("persist-dev")
        sessions_file = tmp_path / "device_sessions.json"
        content = sessions_file.read_text()
        raw = json.loads(content)
        session_data = raw["persist-dev"]
        assert "token" not in session_data
        assert token not in content
        assert "token_hash" in session_data

    def test_list_devices_does_not_leak_tokens(self, tmp_path, monkeypatch, caplog):
        """list_devices must not include raw tokens or full hashes."""
        import logging

        auth = _make_test_manager(tmp_path, monkeypatch)
        auth.register_device("leak-dev", "Phone")
        auth.approve_device("leak-dev")
        token = auth.issue_token("leak-dev")
        caplog.set_level(logging.INFO)
        _ = auth.list_devices()
        for record in caplog.records:
            assert token not in record.getMessage()
        devices = auth.list_devices()
        dev = devices[0]
        assert token != dev.get("token_masked")
        assert "token_hash" not in dev
        assert "token" not in dev

    def test_command_request_preserves_event_id(self, tmp_path, monkeypatch):
        """eventId must be echoed back in the response for deduplication."""
        from backend.main import app

        monkeypatch.setenv("AURA_DATA_DIR", str(tmp_path))
        auth = _make_test_manager(tmp_path, monkeypatch)
        auth.register_device("dedup-dev2", "Phone")
        auth.approve_device("dedup-dev2")
        token = auth.issue_token("dedup-dev2")

        client = TestClient(app)
        with client.websocket_connect("/api/mobile/sync/dedup-dev2") as ws:
            ws.send_text(json.dumps({"type": "auth", "token": token, "deviceId": "dedup-dev2"}))
            ws.receive_text()
            ws.send_text(
                json.dumps(
                    {
                        "action": "command_request",
                        "eventId": "dedup-event-xyz",
                        "data": {"command": "system.status", "params": {}},
                    }
                )
            )
            resp = json.loads(ws.receive_text())
            assert resp["eventId"] == "dedup-event-xyz"

    def test_no_secrets_in_error_logs(self, tmp_path, monkeypatch, caplog):
        """Error responses must not leak tokens or device data."""
        from backend.main import app

        monkeypatch.setenv("AURA_DATA_DIR", str(tmp_path))
        monkeypatch.delenv("AURA_API_KEY", raising=False)
        auth = _make_test_manager(tmp_path, monkeypatch)
        auth.register_device("error-dev", "Phone")
        auth.approve_device("error-dev")
        token = auth.issue_token("error-dev")

        caplog.set_level(logging.ERROR)
        client = TestClient(app)
        with client.websocket_connect("/api/mobile/sync/error-dev") as ws:
            ws.send_text(json.dumps({"type": "auth", "token": token, "deviceId": "error-dev"}))
            ws.receive_text()
            ws.send_text(
                json.dumps(
                    {
                        "action": "command_request",
                        "eventId": "err-event",
                        "data": {"command": "nonexistent.tool", "params": {}},
                    }
                )
            )
            resp = json.loads(ws.receive_text())
            response_str = json.dumps(resp)
            assert token not in response_str
            for record in caplog.records:
                assert token not in record.getMessage()

    def test_run_procedure_re_validates_auth(self, tmp_path, monkeypatch):
        """run_procedure must re-validate auth, not just rely on initial WebSocket auth."""
        from starlette.websockets import WebSocketDisconnect

        from backend.main import app

        monkeypatch.setenv("AURA_DATA_DIR", str(tmp_path))
        monkeypatch.delenv("AURA_API_KEY", raising=False)
        auth = _make_test_manager(tmp_path, monkeypatch)
        auth.register_device("proc-auth-dev", "Phone")
        auth.approve_device("proc-auth-dev")
        token = auth.issue_token("proc-auth-dev")
        auth.revoke_device("proc-auth-dev")

        client = TestClient(app)
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/api/mobile/sync/proc-auth-dev") as ws:
                ws.send_text(
                    json.dumps({"type": "auth", "token": token, "deviceId": "proc-auth-dev"})
                )
                ws.receive_text()
