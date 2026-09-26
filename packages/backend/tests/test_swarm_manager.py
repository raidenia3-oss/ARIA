"""Tests for Swarm Orchestrator - multi-agent coordination."""

from __future__ import annotations

import asyncio
import time

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.services.swarm_orchestrator import SwarmOrchestrator


@pytest.fixture
def swarm_orchestrator():
    return SwarmOrchestrator()


def test_swarm_init(swarm_orchestrator):
    assert swarm_orchestrator is not None
    assert swarm_orchestrator._context is not None
    assert "memory" in swarm_orchestrator._context
    assert "vision" in swarm_orchestrator._context
    assert "tools" in swarm_orchestrator._context


def test_set_system_prompt(swarm_orchestrator):
    swarm_orchestrator.set_system_prompt("New prompt")
    assert swarm_orchestrator._system_prompt == "New prompt"


def test_update_context(swarm_orchestrator):
    swarm_orchestrator.update_context("memory", [{"text": "m1"}])
    assert swarm_orchestrator._context["memory"] == [{"text": "m1"}]


def test_append_context_list(swarm_orchestrator):
    swarm_orchestrator.append_context("memory", {"text": "m1"})
    swarm_orchestrator.append_context("memory", {"text": "m2"})
    assert len(swarm_orchestrator._context["memory"]) == 2


def test_append_context_non_list(swarm_orchestrator):
    swarm_orchestrator._context["new_key"] = "not_a_list"
    swarm_orchestrator.append_context("new_key", "value")
    assert isinstance(swarm_orchestrator._context["new_key"], list)
    assert swarm_orchestrator._context["new_key"] == ["value"]


def test_build_system_prompt_empty(swarm_orchestrator):
    prompt = swarm_orchestrator.build_system_prompt()
    assert isinstance(prompt, str)
    assert len(prompt) > 0


def test_build_system_prompt_with_context(swarm_orchestrator):
    swarm_orchestrator.update_context("memory", [{"text": "user likes jazz"}])
    swarm_orchestrator.update_context("telemetry", {"cpu_percent": 10.0, "ram_percent": 20.0})
    prompt = swarm_orchestrator.build_system_prompt()
    assert "[Memoria relevante]" in prompt
    assert "[Telemetria]" in prompt


def test_build_system_prompt_with_vision(swarm_orchestrator):
    swarm_orchestrator.append_context("vision", {"description": "screen with code editor"})
    prompt = swarm_orchestrator.build_system_prompt()
    assert "[Vision]" in prompt


def test_select_model_first(swarm_orchestrator):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(swarm_orchestrator.select_model())
    finally:
        loop.close()
        asyncio.set_event_loop(None)
    assert len(swarm_orchestrator._fallback_history) == 1
    assert "selected" in swarm_orchestrator._fallback_history[0]


def test_select_model_with_high_latency(swarm_orchestrator):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(swarm_orchestrator.select_model(latency_hint=0.5))
        loop.run_until_complete(swarm_orchestrator.select_model(latency_hint=2.0))
    finally:
        loop.close()
        asyncio.set_event_loop(None)
    assert len(swarm_orchestrator._fallback_history) >= 2


def test_record_model_result(swarm_orchestrator):
    swarm_orchestrator.record_model_result({"provider": "ollama", "model": "llama3"}, success=True, latency=0.5)
    status = swarm_orchestrator.get_status()
    assert len(status["fallback_history"]) >= 1


def test_get_status(swarm_orchestrator):
    status = swarm_orchestrator.get_status()
    assert "current_model" in status
    assert "fallback_history" in status
    assert "context_keys" in status
    assert "system_prompt_length" in status


def test_reset_clears_context(swarm_orchestrator):
    swarm_orchestrator.update_context("memory", [{"text": "m1"}])
    swarm_orchestrator.update_context("vision", [{"description": "v1"}])
    swarm_orchestrator.reset()
    assert swarm_orchestrator._context["memory"] == []
    assert swarm_orchestrator._context["vision"] == []


def test_reset_clears_fallback_history(swarm_orchestrator):
    swarm_orchestrator.record_model_result({"provider": "ollama"}, success=True, latency=0.1)
    swarm_orchestrator.reset()
    assert len(swarm_orchestrator._fallback_history) == 0


def test_build_prompt_with_pending_actions(swarm_orchestrator):
    swarm_orchestrator.append_context("actions", {
        "tool_name": "delete_path",
        "requires_confirmation": True,
        "confirmation_prompt": "Delete file?",
    })
    prompt = swarm_orchestrator.build_system_prompt()
    assert "Acciones pendientes de confirmacion" in prompt


def test_build_prompt_without_pending_actions(swarm_orchestrator):
    swarm_orchestrator._context["actions"] = [{"tool_name": "list_directory", "requires_confirmation": False}]
    prompt = swarm_orchestrator.build_system_prompt()
    assert "Acciones pendientes" not in prompt


def test_global_orchestrator_instance():
    from backend.services.swarm_orchestrator import orchestrator
    assert isinstance(orchestrator, SwarmOrchestrator)
