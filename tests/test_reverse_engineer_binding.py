import asyncio
from unittest.mock import patch, MagicMock

import pytest

from backend.reverse_engineer.launcher import (
    start_reverse_engineer,
    get_service_status,
    _resolve_rea_path,
    _SERVICE_NAME,
)
from backend.autonomy.supervisor import AutonomousSupervisor


def test_service_name_constant():
    assert _SERVICE_NAME == "reverse-engineer"


def test_get_service_status_returns_dict():
    status = get_service_status()
    assert isinstance(status, dict)
    assert status["name"] == "reverse-engineer"
    assert "found" in status
    assert "port" in status
    assert "enabled" in status


def test_resolve_rea_path_returns_none_when_missing(monkeypatch):
    monkeypatch.delenv("AURA_REA_PATH", raising=False)
    with patch("backend.reverse_engineer.launcher._DEFAULT_REA_PATH") as mock_path:
        mock_path.is_dir.return_value = False
        assert _resolve_rea_path() is None


@pytest.mark.asyncio
async def test_start_reverse_engineer_raises_when_not_found(monkeypatch):
    monkeypatch.setenv("AURA_REA_PATH", "/nonexistent/path/rea")
    with pytest.raises(FileNotFoundError, match="REA no encontrado"):
        await start_reverse_engineer()


@pytest.mark.asyncio
async def test_supervisor_restart_on_failure():
    """El supervisor debe reiniciar el servicio reverse-engineer tras un fallo."""
    sup = AutonomousSupervisor(backoff_base=0.01, max_backoff=0.05)
    attempts = {"n": 0}

    async def mock_launcher():
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise RuntimeError("simulated REA crash")
        await asyncio.Event().wait()

    sup.run("reverse-engineer", mock_launcher)
    await asyncio.sleep(0.15)

    assert attempts["n"] >= 2
    st = sup.status()
    assert st["reverse-engineer"]["running"] is True
    assert st["reverse-engineer"]["crashes"] >= 1
    assert "simulated REA crash" in (st["reverse-engineer"]["last_error"] or "")

    sup.cancel("reverse-engineer")
    await asyncio.sleep(0.1)
    assert sup.status()["reverse-engineer"]["running"] is False


@pytest.mark.asyncio
async def test_supervisor_status_reflects_reverse_engineer():
    sup = AutonomousSupervisor()

    async def eternal():
        await asyncio.Event().wait()

    sup.run("reverse-engineer", eternal)
    await asyncio.sleep(0.01)

    st = sup.status()
    assert "reverse-engineer" in st
    assert st["reverse-engineer"]["running"] is True
    assert st["reverse-engineer"]["crashes"] == 0

    sup.cancel("reverse-engineer")
    await asyncio.sleep(0.01)
    assert sup.status()["reverse-engineer"]["running"] is False
