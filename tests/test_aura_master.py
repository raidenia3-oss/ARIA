"""Tests Bloque 38 — AURA Master Launcher & Orchestration CLI.

Valida (sin levantar uvicorn real ni servicios cloud):
- Comprobación de puertos (free / in_use / check_port_free raise).
- Construcción de servicios (backend siempre incluido; Discord opcional).
- ServiceSupervisor: shutdown termina (TERM) y mata (KILL) hijos, limpiando procs.
- Health-Check Aggregator: degraded cuando todo caído; ok cuando todo responde.
- CLI --check retorna JSON y código de salida acorde al overall.
"""

from __future__ import annotations

import importlib.util
import json
import socket
import subprocess
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
AURA_MASTER = ROOT / "scripts" / "aura-master.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("aura_master", AURA_MASTER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


# -- Puertos ---------------------------------------------------------------------


def test_port_in_use_false_on_free_port():
    m = _load_module()
    assert m.port_in_use(_free_port()) is False


def test_check_port_free_ok_on_free_port():
    m = _load_module()
    # No debe lanzar en un puerto libre.
    m.check_port_free(_free_port())


def test_check_port_free_raises_when_used():
    m = _load_module()
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.listen(1)
    try:
        with pytest.raises(RuntimeError):
            m.check_port_free(port)
    finally:
        s.close()


# -- build_services --------------------------------------------------------------


def test_build_services_always_includes_backend():
    m = _load_module()
    services = m.build_services(_free_port(), include_discord=False)
    assert "backend" in services
    assert "uvicorn" in " ".join(services["backend"])


def test_build_services_omits_discord_when_not_available(monkeypatch):
    m = _load_module()
    monkeypatch.setattr(m, "discord_command", lambda: None)
    services = m.build_services(m.BACKEND_PORT_DEFAULT, include_discord=True)
    assert "discord" not in services


# -- ServiceSupervisor.shutdown --------------------------------------------------


def test_supervisor_shutdown_terminates_and_kills_when_timeout():
    m = _load_module()
    sup = m.ServiceSupervisor()
    fake = mock.MagicMock()
    fake.pid = 99999
    fake.poll.return_value = None
    stuck = mock.MagicMock()
    stuck.pid = 99998
    stuck.poll.return_value = None
    stuck.wait.side_effect = subprocess.TimeoutExpired(cmd="discord", timeout=1)
    sup.procs = {"backend": fake, "discord": stuck}
    sup.shutdown()
    fake.terminate.assert_called_once()
    stuck.terminate.assert_called_once()
    stuck.kill.assert_called_once()  # no terminó a tiempo → SIGKILL
    assert sup.procs == {}


# -- Health-Check Aggregator -----------------------------------------------------


def test_aggregate_health_degraded_when_backend_down(monkeypatch):
    m = _load_module()
    monkeypatch.setattr(m, "http_get_json", lambda url, timeout=5: None)
    report = m.aggregate_health(_free_port(), include_jan=False, include_discord=False)
    assert report["overall"] == "degraded"
    assert report["checks"][0]["service"] == "backend"
    assert report["checks"][0]["ok"] is False


def test_aggregate_health_ok_when_all_up(monkeypatch):
    m = _load_module()

    def fake(url, timeout=5):  # noqa: ARG001
        if "/health" in url:
            return {"status": "ok"}
        if "/v1/models" in url:
            return {"data": [{"id": "jan-model"}]}
        if "/api/discord/diagnostics" in url:
            return {"status": "ok"}
        return None

    monkeypatch.setattr(m, "http_get_json", fake)
    report = m.aggregate_health(8000, include_jan=True, include_discord=True)
    assert report["overall"] == "ok"
    assert all(r["ok"] for r in report["checks"])


# -- CLI --check -----------------------------------------------------------------


def test_main_check_outputs_json_and_exit_code(monkeypatch, capsys):
    m = _load_module()
    monkeypatch.setattr(
        m,
        "aggregate_health",
        lambda *a, **k: {
            "overall": "degraded",
            "checks": [{"service": "backend", "ok": False, "detail": "x"}],
        },
    )
    code = m.main(["--check"])
    assert code == 1
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["overall"] == "degraded"
