"""Gate del limite de tasa por herramienta del sandbox.

Cierra el Hueco 2 de docs/AGENT_GUARDS.md: entry.calls es un total desde el
arranque, asi que un agente que dispara 500 llamadas en un minuto y otro que las
reparte en una hora son indistinguibles.

Lo que se verifica aqui, y por que:

- el limite rechaz de verdad, no solo existe
- una llamada rechazada NO cuenta como llamada ni llega a la herramienta: si
  contara, un bucle podria seguir teniendo la herramienta ocupada
- la ventana desliza de verdad (un tope por ventana, no un tope por vida)
- el limite es por herramienta, no global
- el rechazo usa el mismo contrato de retorno que el resto de execute()
- el limite es observable en audit(): un limite que falla en silencio es
  indistinguible de uno que no existe

Los tests monkeypatchean TOOL_RATE_LIMIT / TOOL_RATE_WINDOW en el modulo porque
execute() los lee como globales en cada llamada; asi el gate no depende del
entorno ni del limite por defecto.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from backend.agents import tools_registry as tr


def _entry(tmp_path, name="probe", sink=None):
    calls = []

    def probe(value: str = "x") -> str:
        calls.append(value)
        return f"ok:{value}"

    if sink is not None:
        calls = sink
    return tr.ToolEntry(
        name=name,
        description="probe",
        parameters={
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        },
        func=probe,
    ), calls


def _registry(tmp_path):
    reg = tr.DynamicToolRegistry(scripts_dir=str(tmp_path), auto_scan=False)
    return reg


def _run(reg, entry, params=None, timeout=5.0):
    return asyncio.run(reg.sandbox.execute(entry, params or {"value": "v"}, timeout))


def test_limit_rejects_the_call_over_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "TOOL_RATE_LIMIT", 3)
    monkeypatch.setattr(tr, "TOOL_RATE_WINDOW", 60.0)
    entry, sink = _entry(tmp_path)
    reg = _registry(tmp_path)

    for _ in range(3):
        assert _run(reg, entry)["success"] is True
    rejected = _run(reg, entry)

    assert rejected["success"] is False
    assert "rate limit" in rejected["error"]
    assert len(sink) == 3, "la herramienta no debe ejecutarse al rechazar el limite"


def test_rejected_call_does_not_count_as_a_call(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "TOOL_RATE_LIMIT", 2)
    monkeypatch.setattr(tr, "TOOL_RATE_WINDOW", 60.0)
    entry, _ = _entry(tmp_path)
    reg = _registry(tmp_path)

    _run(reg, entry)
    _run(reg, entry)
    _run(reg, entry)

    assert entry.calls == 2, "cobrar una llamada rechazada hace que el bucle la siga ocupando"


def test_rejection_uses_the_same_contract_as_the_other_branches(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "TOOL_RATE_LIMIT", 1)
    monkeypatch.setattr(tr, "TOOL_RATE_WINDOW", 60.0)
    entry, _ = _entry(tmp_path)
    reg = _registry(tmp_path)

    ok = _run(reg, entry)
    rejected = _run(reg, entry)

    assert set(ok) == set(rejected) == {"success", "tool", "output", "error", "duration_ms"}
    assert rejected["tool"] == entry.name
    assert rejected["output"] is None
    assert rejected["duration_ms"] >= 0.0
    assert entry.last_error == rejected["error"]


def test_window_slides_so_the_budget_returns(tmp_path, monkeypatch):
    # La ventana tiene que ser HOLGADA: una llamada al sandbox tarda ~25 ms,
    # y con 50 ms la ventana se agotaba entre llamadas y el test pasaba o
    # fallaba segun la carga de la maquina. Un gate que depende del reloj
    # es un gate que se ignora.
    monkeypatch.setattr(tr, "TOOL_RATE_LIMIT", 2)
    monkeypatch.setattr(tr, "TOOL_RATE_WINDOW", 0.5)
    entry, sink = _entry(tmp_path)
    reg = _registry(tmp_path)

    assert _run(reg, entry)["success"] is True
    assert _run(reg, entry)["success"] is True
    assert _run(reg, entry)["success"] is False, "el tope es por ventana, no por vida"

    time.sleep(0.6)

    assert _run(reg, entry)["success"] is True, "la ventana debe agotarse sola"


def test_limit_is_per_tool_not_global(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "TOOL_RATE_LIMIT", 2)
    monkeypatch.setattr(tr, "TOOL_RATE_WINDOW", 60.0)
    hot, hot_sink = _entry(tmp_path, name="hot")
    cold, cold_sink = _entry(tmp_path, name="cold")
    reg = _registry(tmp_path)

    for _ in range(2):
        _run(reg, hot)
    assert _run(reg, hot)["success"] is False

    assert _run(reg, cold)["success"] is True, "agotar una herramienta no debe agotar otra"
    assert len(cold_sink) == 1


def test_limit_disabled_when_set_to_zero_or_less(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "TOOL_RATE_LIMIT", 0)
    monkeypatch.setattr(tr, "TOOL_RATE_WINDOW", 60.0)
    entry, sink = _entry(tmp_path)
    reg = _registry(tmp_path)

    for _ in range(25):
        assert _run(reg, entry)["success"] is True
    assert len(sink) == 25
    assert reg.sandbox.rate_limit_state() == {}


def test_audit_reports_the_rate_limit_instead_of_failing_silently(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "TOOL_RATE_LIMIT", 1)
    monkeypatch.setattr(tr, "TOOL_RATE_WINDOW", 60.0)
    entry, _ = _entry(tmp_path)
    reg = _registry(tmp_path)

    _run(reg, entry)
    _run(reg, entry)

    state = reg.audit()["rate_limit"]
    assert state["limit"] == 1
    assert state["window_s"] == 60.0
    assert state["rejected"] == {entry.name: 1}


def test_sandbox_windows_are_independent_per_instance(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "TOOL_RATE_LIMIT", 1)
    monkeypatch.setattr(tr, "TOOL_RATE_WINDOW", 60.0)
    entry, _ = _entry(tmp_path)
    reg = _registry(tmp_path)

    _run(reg, entry)
    assert _run(reg, entry)["success"] is False

    fresh = tr.SkillExecutionSandbox(_registry(tmp_path))
    assert fresh._rate_limit_reason(entry.name) is None, (
        "el limite debe vivir en el sandbox, no en una variable de clase"
    )


def test_default_limit_is_not_zero_or_negative():
    assert tr.TOOL_RATE_LIMIT > 0, "un limite por defecto de 0 apagaria la proteccion"
    assert tr.TOOL_RATE_WINDOW > 0, "una ventana de 0s rechazaria todo o nada"
