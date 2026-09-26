"""Integration tests for Tier 2 modules."""

from __future__ import annotations

import base64
from PIL import Image
import io

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_vision_memory_integration():
    from backend.services.vision_engine import VisionEngine
    from backend.services.memory_engine import MemoryEngine

    orchestrator = MagicMock()
    vision = VisionEngine(orchestrator=orchestrator)
    memory = MemoryEngine(orchestrator=orchestrator)

    img = Image.new("RGB", (10, 10), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_b64 = base64.b64encode(buf.getvalue()).decode()

    with patch.object(vision, "_ollama_vision", return_value="blue screen"):
        vision_result = vision.analyze_frame(img_b64, session_id="s1")
    assert vision_result.get("description") == "blue screen"

    with patch.object(memory._embedding_provider, "embed", return_value=[0.1, 0.2, 0.3]):
        memory.remember(vision_result.get("description", ""), memory_type="episodic")

    with patch.object(memory._store, "search", return_value=[]):
        context = memory.inject_context("screen", max_results=2)
    assert isinstance(context, list)


@pytest.mark.asyncio
async def test_swarm_orchestrator_context_building():
    from backend.services.swarm_orchestrator import SwarmOrchestrator

    swarm = SwarmOrchestrator()
    swarm.set_system_prompt("Eres AURA.")
    swarm.update_context("memory", [{"text": "user prefers dark mode"}])
    swarm.update_context("vision", [{"description": "IDE open"}])
    swarm.update_context("telemetry", {"cpu_percent": 25.0, "ram_percent": 40.0})
    swarm.append_context("tools", {"name": "read_file", "description": "Read a file"})

    prompt = swarm.build_system_prompt()
    assert "Eres AURA." in prompt
    assert "Memoria relevante" in prompt
    assert "Vision" in prompt
    assert "Telemetria" in prompt
    assert "Herramientas disponibles" in prompt


@pytest.mark.asyncio
async def test_swarm_model_fallback():
    from backend.services.swarm_orchestrator import SwarmOrchestrator

    swarm = SwarmOrchestrator()
    model = await swarm.select_model(latency_hint=2.0)
    assert model is not None
    assert "provider" in model
    assert "model" in model
    assert "timeout" in model


@pytest.mark.asyncio
async def test_memory_search_after_vision_context():
    from backend.services.vision_engine import VisionEngine
    from backend.services.memory_engine import MemoryEngine

    vision = VisionEngine()
    memory = MemoryEngine()

    with patch.object(memory._embedding_provider, "embed", return_value=[0.1, 0.2, 0.3]):
        memory.remember("User asked about Python code", memory_type="episodic")
        memory.remember("Server CPU spiked to 90%", memory_type="episodic")

    with patch.object(memory._store, "search", return_value=[]):
        results = memory.search("Python code", max_results=2)
    assert results.get("status") == "ok"


@pytest.mark.asyncio
async def test_action_engine_permissions():
    from backend.services.action_engine import ActionEngine

    engine = ActionEngine(orchestrator=None)
    tools = engine.list_tools()
    assert len(tools) > 0
    assert any(t["name"] == "run_command" for t in tools)
    assert any(t["name"] == "read_file" for t in tools)

    result = engine.execute("nonexistent_tool", {})
    assert result.success is False
    assert result.error == "tool_not_found"
