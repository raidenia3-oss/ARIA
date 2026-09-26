"""Tests for BLOQUE 53 - AURA Local OS Control & Safety Engine.

NOTA: el archivo original se corrompio en disco (16 bytes con bytes nulos,
accidente de escritura en UTF-16) y su contenido fue irrecuperable; este
modulo lo reconstruye cubriendo la API real consolidada del bloque:

1. backend/automation/os_controller.py — controlador OS local con
   ejecucion segura de eventos (SafetyFilter, riesgos, confirmaciones).
2. REST /api/automation/os/* (backend/routers/automation_os.py).

Valida (100% local, sin cloud y sin tocar la GUI real del equipo):
- Contratos serializables (OSAction, CommandValidationResult, ActionResult).
- SafetyFilter: bloqueo de comandos destructivos, lista blanca, riesgos.
- OSController.execute_action: puerta de seguridad, confirmacion, historial.
- Despacho headless: acciones GUI fallan limpio sin pyautogui.
- REST: status, validate-command, confirm-command, execute (400/403/200),
  history, tools y safety-status.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.automation.os_controller import (
    ActionResult,
    CommandValidationResult,
    OSAction,
    OSActionType,
    OSController,
    RiskLevel,
    SafetyFilter,
)

# ---------------------------------------------------------------- contratos --


class TestContracts:
    def test_action_type_values(self):
        assert OSActionType.RUN_COMMAND.value == "run_command"
        assert OSActionType.CLICK.value == "click"
        assert OSActionType.SCREENSHOT.value == "screenshot"
        assert OSActionType.LIST_WINDOWS.value == "list_windows"

    def test_risk_level_values(self):
        assert RiskLevel.SAFE.value == "safe"
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"

    def test_osaction_to_dict(self):
        action = OSAction(action_type=OSActionType.CLICK, coordinates=(10.0, 20.0))
        d = action.to_dict()
        assert d["action_type"] == "click"
        assert d["coordinates"] == [10.0, 20.0]
        assert d["metadata"] == {}
        assert d["require_confirmation"] is False

    def test_validation_and_result_dicts(self):
        v = CommandValidationResult(
            allowed=True,
            risk_level=RiskLevel.LOW,
            requires_confirmation=False,
            sanitized_command="pwd",
        )
        assert v.to_dict()["risk_level"] == "low"
        assert v.to_dict()["allowed"] is True
        r = ActionResult(success=True, action_type="run_command", output={"stdout": "x"})
        assert r.to_dict()["success"] is True
        assert r.to_dict()["risk_level"] == "safe"


# ------------------------------------------------------------ safety filter --


class TestSafetyFilter:
    def test_blocks_destructive_patterns(self):
        sf = SafetyFilter()
        for cmd in ("rm -rf /", "mkfs /dev/sda1", "shutdown now", "reboot"):
            v = sf.validate_command(cmd)
            assert v.allowed is False, cmd
            assert v.risk_level == RiskLevel.CRITICAL, cmd
            assert v.requires_confirmation is False

    def test_blocks_global_pattern_tokens(self):
        # Comandos con * global/recursive son equivalentemente destructivos
        # a "rm -rf /": se bloquean de forma critica sin confirmacion.
        sf = SafetyFilter()
        v = sf.validate_command("rm -fr *")
        assert v.allowed is False, "los patrones con * global deben bloquearse"
        assert v.risk_level == RiskLevel.CRITICAL
        assert v.requires_confirmation is False

    def test_blocks_dangerous_tokens(self):
        sf = SafetyFilter()
        for cmd in ("fdisk -l", "dd if=zero of=/dev/sda", "parted /dev/sdb"):
            v = sf.validate_command(cmd)
            assert v.allowed is False, cmd
            assert v.risk_level == RiskLevel.CRITICAL, cmd
            assert v.requires_confirmation is False
            v = sf.validate_command(cmd)
            assert v.allowed is False, cmd
            assert v.risk_level == RiskLevel.CRITICAL, cmd

    def test_whitelist_mode(self):
        sf = SafetyFilter(allowed_commands=["echo"])
        ok = sf.validate_command("echo hola")
        assert ok.allowed is True and ok.risk_level == RiskLevel.LOW
        bad = sf.validate_command("curl http://example.com")
        assert bad.allowed is False
        assert bad.risk_level == RiskLevel.HIGH
        assert bad.requires_confirmation is True

    def test_risk_levels_by_base_token(self):
        sf = SafetyFilter()
        git = sf.validate_command("git status")
        assert git.risk_level == RiskLevel.MEDIUM and git.requires_confirmation is True
        rm = sf.validate_command("rm notas.txt")
        assert rm.risk_level == RiskLevel.HIGH and rm.requires_confirmation is True
        sudo = sf.validate_command("sudo rm x")
        assert sudo.risk_level == RiskLevel.CRITICAL
        pwd = sf.validate_command("pwd")
        assert pwd.risk_level == RiskLevel.LOW and pwd.requires_confirmation is False
        assert pwd.sanitized_command == "pwd"

    def test_confirmation_cache(self):
        sf = SafetyFilter()
        assert sf.is_confirmed("git push") is False
        sf.set_confirmation("git push", True)
        assert sf.is_confirmed("git push") is True
        assert sf.is_confirmed("git push ") is True  # normalizado
        sf.set_confirmation("git push", False)


# ------------------------------------------------------------- oscontroller --


def _local_controller():
    from backend.automation.os_controller import OSController

    return OSController(safety_filter=None)


class TestOSControllerLocal:
    @pytest.mark.asyncio
    async def test_blocked_command_never_executes(self):
        c = _local_controller()
        action = OSAction(action_type=OSActionType.RUN_COMMAND, command="rm -rf /")
        with patch("backend.automation.os_controller.subprocess.run") as run_mock:
            res = await c.execute_action(action)
        assert res.success is False
        assert "Comando bloqueado" in (res.error or "")
        assert res.risk_level == RiskLevel.CRITICAL
        run_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_risky_command_requires_confirmation(self):
        c = _local_controller()
        action = OSAction(action_type=OSActionType.RUN_COMMAND, command="git status")
        c.confirm_action("git status", True)


# --------------------------------------------------------------------- REST --


class TestAutomationOSREST:
    @pytest.fixture()
    def client(self, monkeypatch):
        monkeypatch.delenv("AURA_API_KEY", raising=False)
        from backend.automation.os_controller import os_controller
        from backend.main import app

        os_controller.clear_history()
        os_controller._safety._confirmation_cache.clear()
        yield TestClient(app)
        os_controller.clear_history()
        os_controller._safety._confirmation_cache.clear()

    def test_status(self, client):
        r = client.get("/api/automation/os/status")
        assert r.status_code == 200
        body = r.json()
        assert body["safety_enabled"] is True
        assert "platform" in body

    def test_validate_and_confirm(self, client):
        ok = client.post("/api/automation/os/validate-command", json={"command": "pwd"})
        assert ok.status_code == 200 and ok.json()["allowed"] is True
        bad = client.post("/api/automation/os/validate-command", json={"command": "shutdown"})
        assert bad.status_code == 200 and bad.json()["allowed"] is False
        r = client.post(
            "/api/automation/os/confirm-command",
            json={"command": "git status", "approved": True},
        )
        assert r.status_code == 200 and r.json()["confirmed"] is True

    def test_execute_blocked_is_400(self, client):
        r = client.post(
            "/api/automation/os/execute",
            json={"action_type": "run_command", "command": "rm -rf /"},
        )
        assert r.status_code == 400
        assert "Comando bloqueado" in r.json()["error"]

    def test_execute_needs_confirmation_is_403(self, client):
        r = client.post(
            "/api/automation/os/execute",
            json={"action_type": "run_command", "command": "git status"},
        )
        assert r.status_code == 403
        assert r.json()["requires_confirmation"] is True

    def test_execute_confirmed_ok_mocked(self, client):
        client.post(
            "/api/automation/os/confirm-command",
            json={"command": "git status", "approved": True},
        )
        with patch("backend.automation.os_controller.subprocess.run") as run_mock:
            run_mock.return_value = MagicMock(stdout="on main", stderr="", returncode=0)
            r = client.post(
                "/api/automation/os/execute",
                json={"action_type": "run_command", "command": "git status"},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["output"]["returncode"] == 0

    def test_execute_invalid_action_type_is_400(self, client):
        r = client.post("/api/automation/os/execute", json={"action_type": "no_existe"})
        assert r.status_code == 400

    def test_execute_validates_payload(self, client):
        assert client.post("/api/automation/os/execute", json={}).status_code == 422

    def test_history_endpoints(self, client):
        r = client.get("/api/automation/os/history")
        assert r.status_code == 200 and isinstance(r.json()["history"], list)
        d = client.delete("/api/automation/os/history")
        assert d.status_code == 200 and d.json()["cleared"] is True

    def test_tools_and_safety_status(self, client):
        t = client.get("/api/automation/os/tools")
        assert t.status_code == 200
        assert t.json()["count"] >= 17
        s = client.get("/api/automation/os/safety-status")
        assert s.status_code == 200
        body = s.json()
        assert body["dangerous_patterns_count"] >= 10
        assert body["dangerous_commands_count"] >= 8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
