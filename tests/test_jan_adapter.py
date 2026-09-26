"""Tests Bloque 30 — Adaptador Jan (motor LLM local-first).

Valida que el proveedor 'jan' se registra, se enruta por el camino
OpenAI-compatible y queda disponible sin API key (local-first).
"""

from __future__ import annotations

import os
from unittest import mock

import pytest

from backend.ai_router import AIRouter, ProviderConfig


def _make_router(monkeypatch, env=None):
    env = env or {}
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    # Forzar recálculo de providers tras setear env.
    return AIRouter(state_file=os.path.join(os.path.dirname(__file__), "_test_router_state.json"))


def test_jan_provider_registered_by_default(monkeypatch):
    router = _make_router(monkeypatch)
    names = [p.name for p in router._providers]
    assert "jan" in names, f"jan no está entre los proveedores: {names}"


def test_jan_provider_local_first_no_key_required(monkeypatch):
    router = _make_router(monkeypatch)
    jan = next(p for p in router._providers if p.name == "jan")
    assert jan.enabled is True
    assert jan.base_url == "http://localhost:1337/v1"
    assert jan.model == "gemma-3-1b-it"


def test_jan_provider_env_override(monkeypatch):
    router = _make_router(
        monkeypatch,
        env={
            "JAN_BASE_URL": "http://192.168.1.42:1337/v1",
            "JAN_MODEL": "gemma-3-4b-it",
            "JAN_TIMEOUT": "90",
            "JAN_PRIORITY": "2",
        },
    )
    jan = next(p for p in router._providers if p.name == "jan")
    assert jan.base_url == "http://192.168.1.42:1337/v1"
    assert jan.model == "gemma-3-4b-it"
    assert jan.timeout == 90.0
    assert jan.priority == 2


def test_jan_routes_through_openai_compatible(monkeypatch):
    """Jan debe enrutar por _call_openai_compatible (camino OpenAI-compat)."""
    router = _make_router(monkeypatch)
    jan = next(p for p in router._providers if p.name == "jan")

    called = {}

    async def fake_openai(provider, prompt, system_prompt, max_tokens, temperature):
        called["provider"] = provider.name
        called["base"] = provider.base_url
        return {"message": "ok-jan", "history": [["hi", "ok-jan"]]}

    async def fake_ollama(*a, **kw):
        raise AssertionError("Jan no debe enrutar por ollama")

    with (
        mock.patch.object(router, "_call_openai_compatible", side_effect=fake_openai),
        mock.patch.object(router, "_call_ollama", side_effect=fake_ollama),
    ):
        import asyncio

        result = asyncio.run(router.generate_response(prompt="hola", context={}))

    # Jan tiene priority=0 (mayor prioridad) → debe ser el elegido.
    assert called.get("provider") == "jan"
    assert called.get("base") == "http://localhost:1337/v1"
    assert result["message"] == "ok-jan"
    assert result["provider"] == "jan"


def test_jan_skips_when_circuit_open(monkeypatch):
    """Con el circuito de Jan abierto, el router debe fallback al siguiente proveedor."""
    router = _make_router(monkeypatch)
    jan = next(p for p in router._providers if p.name == "jan")
    router._state["circuit_until"] = {jan.name: float("inf")}

    reached = []

    async def fake_openai(provider, *a, **kw):
        reached.append(provider.name)
        return {"message": f"via-{provider.name}", "history": []}

    with mock.patch.object(router, "_call_openai_compatible", side_effect=fake_openai):
        import asyncio

        result = asyncio.run(router.generate_response(prompt="hola", context={}))

    assert "jan" not in reached
    assert result["provider"] != "jan"


def teardown_module(module):
    # Limpieza del estado de router de test.
    p = os.path.join(os.path.dirname(__file__), "_test_router_state.json")
    if os.path.exists(p):
        os.remove(p)
