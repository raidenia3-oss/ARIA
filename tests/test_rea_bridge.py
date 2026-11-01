import asyncio
import json
from unittest.mock import patch, MagicMock, mock_open, AsyncMock
from pathlib import Path

import pytest

from backend.reverse_engineer.rea_bridge import REABridge, get_rea_bridge
from backend.autonomy.supervisor import AutonomousSupervisor


def test_rea_bridge_singleton():
    a = get_rea_bridge()
    b = get_rea_bridge()
    assert a is b


def test_rea_bridge_initial_state():
    bridge = REABridge()
    assert bridge._port == "8843"
    assert hasattr(bridge, "_rea_path")
    assert bridge._rea_path.exists() or str(bridge._rea_path) is not None
    assert bridge._available is None
    assert bridge._client is None


def test_extract_youtube_id():
    bridge = REABridge()
    assert bridge._extract_youtube_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert bridge._extract_youtube_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert bridge._extract_youtube_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&feature=youtu.be") == "dQw4w9WgXcQ"


@pytest.mark.asyncio
async def test_analyze_website_rea_unavailable_fallback():
    bridge = REABridge()
    with patch.object(REABridge, "is_available", return_value=False):
        with patch.object(REABridge, "_fallback_web_analysis", new_callable=AsyncMock) as mock_fb:
            mock_fb.return_value = {
                "url": "https://example.com",
                "source": "local-fallback",
                "available": False,
                "fetched": True,
            }
            result = await bridge.analyze_website("https://example.com")
            assert result["source"] == "local-fallback"
            assert result["available"] is False
            mock_fb.assert_called_once()


@pytest.mark.asyncio
async def test_analyze_website_rea_available():
    bridge = REABridge()
    with patch.object(REABridge, "is_available", return_value=True):
        with patch.object(REABridge, "_call_mcp_tool", new_callable=AsyncMock) as mock_tool:
            mock_tool.return_value = {
                "structure": {"title": "Test"},
                "scripts": [],
            }
            result = await bridge.analyze_website("https://example.com")
            assert result["available"] is True
            assert result["structure"]["title"] == "Test"
            assert result["scripts"] == []
            mock_tool.assert_awaited()


@pytest.mark.asyncio
async def test_fuse_game_mod_missing_paths():
    bridge = REABridge()
    result = await bridge.fuse_game_mod("/nonexistent/source", "/nonexistent/target", "Mario")
    assert "error" in result
    assert "no existen" in result["error"].lower()


@pytest.mark.asyncio
async def test_fuse_game_mod_rea_unavailable():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        source = Path(tmpdir) / "source_game"
        target = Path(tmpdir) / "target_game"
        source.mkdir()
        target.mkdir()

        bridge = REABridge()
        with patch.object(REABridge, "is_available", return_value=False):
            result = await bridge.fuse_game_mod(str(source), str(target), "Mario")
            assert result["available"] is False
            assert "no disponible" in result["error"].lower()


@pytest.mark.asyncio
async def test_analyze_youtube_video_no_yt_dlp():
    bridge = REABridge()
    with patch.object(bridge, "_yt_dlp_path", None, create=True):
        result = await bridge.analyze_youtube_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert result["yt_dlp_available"] is False
        assert "error" in result


def test_generate_mod_code():
    bridge = REABridge()
    mock_mission = MagicMock()
    mock_mission.knowledge_map = {"concepts": {"model": 5, "texture": 3}}

    code = bridge._generate_mod_code("Mario", "/source", "/target", mock_mission)
    assert "cpp_mod" in code
    assert "lua_mod" in code
    assert "python_bridge" in code
    assert "Mario" in code["cpp_mod"]


def test_get_providers_returns_all_native():
    bridge = REABridge()
    providers = bridge.get_providers()
    assert "ghidra" in providers
    assert "hopper" in providers
    assert "ida" in providers
    for name, info in providers.items():
        assert "name" in info
        assert "binary" in info
        assert "configured" in info


def test_connect_provider_unknown_returns_false():
    bridge = REABridge()
    assert bridge.connect_provider("unknown_provider") is False


@pytest.mark.asyncio
async def test_connect_account_success():
    bridge = REABridge()
    with patch.object(REABridge, "save_provider_config", return_value=True):
        result = await bridge.connect_account("ghidra", path="/opt/ghidra", binary="ghidra")
        assert result["connected"] is True
        assert "ghidra" in result["providers"]
        assert bridge.get_providers()["ghidra"]["configured"] is True


@pytest.mark.asyncio
async def test_clone_software_not_available():
    bridge = REABridge()
    with patch.object(REABridge, "is_available", return_value=False):
        result = await bridge.clone_software("https://example.com/app", "/tmp/clone")
        assert result["available"] is False
        assert "error" in result


@pytest.mark.asyncio
async def test_clone_software_success(tmp_path):
    bridge = REABridge()
    with patch.object(REABridge, "is_available", return_value=True):
        with patch.object(REABridge, "_call_mcp_tool", new_callable=AsyncMock) as mock_tool:
            mock_tool.return_value = {
                "findings": [],
                "functions": [],
                "strings": ["test"],
                "evidence": {"tool": "Ghidra"},
                "available": True,
            }
            with patch.object(REABridge, "analyze_binary", new_callable=AsyncMock) as mock_bin:
                mock_bin.return_value = {
                    "available": True,
                    "findings": [],
                    "functions": [],
                    "strings": ["test"],
                    "evidence": {"tool": "Ghidra"},
                    "overview": {"findings": [], "functions": [], "strings": ["test"]},
                }
                mock_mission = MagicMock()
                mock_mission.mission_id = "test-mission"
                mock_mission.knowledge_map = {"concepts": {"binary": 3, "function": 5}}
                with patch("backend.agent.deep_research.get_research_engine") as mock_engine:
                    mock_engine_instance = mock_engine.return_value
                    mock_engine_instance.start_mission.return_value = mock_mission
                    result = await bridge.clone_software("https://example.com/app", str(tmp_path))
                    assert result["available"] is True
                    assert "analysis" in result
                    assert "generated_files" in result


def test_generate_clone_code():
    bridge = REABridge()
    mock_mission = MagicMock()
    mock_mission.knowledge_map = {"concepts": {"function": 5, "class": 3}}
    analysis = {"functions": [{"name": "main", "params": "void", "purpose": "Entry point"}], "strings": ["hello"]}

    code = bridge._generate_clone_code("/path/to/software", analysis, mock_mission)
    assert "ClonedSoftware" in code
    assert "hello" in code
    assert "main" in code


def test_generate_clone_report():
    bridge = REABridge()
    analysis = {"findings": [{"description": "Test finding"}], "functions": [], "strings": [], "calls": []}
    report = bridge._generate_clone_report("https://example.com/app", analysis)
    assert "Reporte de Clon" in report
    assert "Test finding" in report
