"""
Tests for BLOQUE 51 - AURA 3D Core Visualizer & Lightweight Unrestricted Cognition Engine

Tests cover:
1. Local AI Bridge (backend/local_ai_bridge.py) - Model configs, profiles, data structures
2. Browser Automation Agent (backend/automation/browser_agent.py) - Config, data structures
3. Integration tests for file existence
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, patch

import pytest


# Test Local AI Bridge - Core Data Structures
class TestLocalAIBridge:
    """Tests for LocalAIBridge class - data structures and config."""

    def test_model_config_from_profile_dolphin_7b(self):
        from backend.local_ai_bridge import ModelConfig, ModelProfile

        config = ModelConfig.from_profile(
            ModelProfile.DOLPHIN_7B, base_url="http://localhost:11434"
        )

        assert config.profile == ModelProfile.DOLPHIN_7B
        assert config.model == "dolphin-2.6-mistral-7b"
        assert config.temperature == 0.7
        assert config.top_p == 0.95
        assert config.num_ctx == 8192
        assert "sin censura" in config.system_prompt.lower()

    def test_model_config_from_profile_dolphin_14b(self):
        from backend.local_ai_bridge import ModelConfig, ModelProfile

        config = ModelConfig.from_profile(ModelProfile.DOLPHIN_14B)

        assert config.profile == ModelProfile.DOLPHIN_14B
        assert config.model == "dolphin-2.6-mixtral-8x7b"
        assert config.num_ctx == 8192

    def test_model_config_from_profile_codellama(self):
        from backend.local_ai_bridge import ModelConfig, ModelProfile

        config = ModelConfig.from_profile(ModelProfile.CODELLAMA_7B)

        assert config.profile == ModelProfile.CODELLAMA_7B
        assert config.model == "codellama-7b-instruct"
        assert config.temperature == 0.2
        assert config.num_ctx == 16384

    def test_model_config_custom_overrides(self):
        from backend.local_ai_bridge import ModelConfig, ModelProfile

        config = ModelConfig.from_profile(
            ModelProfile.DOLPHIN_7B,
            base_url="http://custom:11434",
            temperature=0.9,
            max_tokens=4096,
        )

        assert config.base_url == "http://custom:11434"
        assert config.temperature == 0.9
        assert config.max_tokens == 4096

    def test_inference_request_creation(self):
        from backend.local_ai_bridge import InferenceRequest

        request = InferenceRequest(
            prompt="Test prompt",
            system_prompt="System prompt",
            max_tokens=1024,
            temperature=0.8,
            stream=True,
            context=[{"role": "user", "content": "Previous"}],
        )

        assert request.prompt == "Test prompt"
        assert request.system_prompt == "System prompt"
        assert request.max_tokens == 1024
        assert request.temperature == 0.8
        assert request.stream is True
        assert len(request.context) == 1

    def test_inference_response_creation(self):
        from backend.local_ai_bridge import InferenceResponse

        response = InferenceResponse(
            message="Generated text",
            model="test-model",
            provider="test-provider",
            tokens_generated=100,
            tokens_per_second=50.0,
            total_time=2.0,
            prompt_tokens=50,
            finish_reason="stop",
        )

        assert response.message == "Generated text"
        assert response.tokens_generated == 100
        assert response.tokens_per_second == 50.0

    def test_local_ai_bridge_initialization_with_config(self):
        from backend.local_ai_bridge import LocalAIBridge, ModelConfig, ModelProfile

        config = ModelConfig.from_profile(ModelProfile.DOLPHIN_7B)

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "test_config.json"
            bridge = LocalAIBridge(config=config, config_file=str(config_file))

            assert bridge.config.profile == ModelProfile.DOLPHIN_7B
            assert bridge.config_file == config_file
            # Save config manually
            bridge.save_config()
            assert config_file.exists()
            saved_data = json.loads(config_file.read_text())
            assert saved_data["model"] == "dolphin-2.6-mistral-7b"

    def test_local_ai_bridge_load_config(self):
        from backend.local_ai_bridge import LocalAIBridge, ModelConfig, ModelProfile

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "test_config.json"
            # Pre-create config file
            config_data = {
                "name": "Test Model",
                "base_url": "http://localhost:11434",
                "model": "test-model",
                "profile": "dolphin-7b",
                "api_key": "",
                "timeout": 60.0,
                "max_tokens": 2048,
                "temperature": 0.7,
                "top_p": 0.9,
                "top_k": 40,
                "repeat_penalty": 1.1,
                "num_ctx": 4096,
                "num_gpu_layers": -1,
                "seed": -1,
                "stop_sequences": [],
                "system_prompt": "Test prompt",
                "enabled": True,
            }
            config_file.write_text(json.dumps(config_data))

            bridge = LocalAIBridge(config_file=str(config_file))

            assert bridge.config.model == "test-model"
            assert bridge.config.name == "Test Model"

    def test_model_profile_enum_values(self):
        from backend.local_ai_bridge import ModelProfile

        profiles = [p.value for p in ModelProfile]
        assert "dolphin-7b" in profiles
        assert "dolphin-14b" in profiles
        assert "mistral-7b-instruct" in profiles
        assert "codellama-7b" in profiles
        assert "codellama-13b" in profiles
        assert "neural-chat-7b" in profiles
        assert "zephyr-7b" in profiles
        assert "openchat-7b" in profiles
        assert "custom" in profiles


# Test Browser Automation Agent - Core Data Structures
class TestBrowserAgent:
    """Tests for BrowserAgent class - data structures and config."""

    def test_browser_config_defaults(self):
        from backend.automation.browser_agent import BrowserConfig, BrowserEngine

        config = BrowserConfig()

        assert config.engine == BrowserEngine.CHROMIUM
        assert config.headless is True
        assert config.viewport == {"width": 1280, "height": 720}
        assert config.locale == "es-ES"
        assert config.timezone_id == "Europe/Madrid"
        assert "--disable-blink-features=AutomationControlled" in config.args
        assert "--no-sandbox" in config.args

    def test_browser_config_custom(self):
        from backend.automation.browser_agent import BrowserConfig, BrowserEngine

        config = BrowserConfig(
            engine=BrowserEngine.FIREFOX,
            headless=False,
            viewport={"width": 1920, "height": 1080},
            slow_mo=100,
        )

        assert config.engine == BrowserEngine.FIREFOX
        assert config.headless is False
        assert config.viewport == {"width": 1920, "height": 1080}
        assert config.slow_mo == 100

    def test_action_result_creation(self):
        from backend.automation.browser_agent import ActionResult

        result = ActionResult(
            success=True,
            action="click",
            selector="#submit",
            duration_ms=150.5,
        )

        assert result.success is True
        assert result.action == "click"
        assert result.selector == "#submit"
        assert result.duration_ms == 150.5

    def test_navigation_result_creation(self):
        from backend.automation.browser_agent import NavigationResult

        result = NavigationResult(
            success=True,
            url="https://example.com",
            status=200,
            duration_ms=500.0,
            redirects=["https://example.com/redirect"],
        )

        assert result.success is True
        assert result.url == "https://example.com"
        assert result.status == 200
        assert len(result.redirects) == 1

    def test_wait_strategy_enum(self):
        from backend.automation.browser_agent import WaitStrategy

        strategies = [s.value for s in WaitStrategy]
        assert "networkidle" in strategies
        assert "domcontentloaded" in strategies
        assert "load" in strategies
        assert "selector" in strategies
        assert "function" in strategies
        assert "timeout" in strategies

    def test_browser_engine_enum(self):
        from backend.automation.browser_agent import BrowserEngine

        engines = [e.value for e in BrowserEngine]
        assert "chromium" in engines
        assert "firefox" in engines
        assert "webkit" in engines

    def test_rollercoin_bot_class_exists(self):
        from backend.automation.browser_agent import RollerCoinBot

        assert RollerCoinBot is not None
        assert hasattr(RollerCoinBot, "login")
        assert hasattr(RollerCoinBot, "start_mining")
        assert hasattr(RollerCoinBot, "collect_rewards")

    def test_create_browser_agent_factory(self):
        from backend.automation.browser_agent import create_browser_agent

        assert callable(create_browser_agent)


# Test REST endpoints - Basic routing
class TestLocalAIRoutes:
    """Tests for Local AI REST endpoints - basic routing."""

    @patch("backend.routes_local_ai.LOCAL_AI_AVAILABLE", True)
    @patch("backend.routes_local_ai.get_local_bridge")
    def test_local_ai_health_endpoint(self, mock_get_bridge):
        from fastapi.testclient import TestClient

        from backend.main import app

        mock_bridge = Mock()
        mock_bridge.health_check = AsyncMock(
            return_value={
                "healthy": True,
                "endpoint": "http://localhost:11434",
                "configured_model": "dolphin-2.6-mistral-7b",
                "available_models": ["dolphin-2.6-mistral-7b:latest"],
                "model_available": True,
                "profile": "dolphin-7b",
            }
        )
        mock_bridge.get_config.return_value = {
            "name": "Dolphin 7B",
            "model": "dolphin-2.6-mistral-7b",
            "profile": "dolphin-7b",
        }
        mock_get_bridge.return_value = mock_bridge

        client = TestClient(app)
        response = client.get("/api/local-ai/health")

        assert response.status_code == 200
        data = response.json()
        assert data["available"] is True
        assert data["health"]["healthy"] is True

    @patch("backend.routes_local_ai.BROWSER_AUTOMATION_AVAILABLE", True)
    def test_browser_health_endpoint(self):
        from fastapi.testclient import TestClient

        import backend.routes_local_ai as routes_module
        from backend.main import app

        routes_module._browser_agent = None

        client = TestClient(app)
        response = client.get("/api/browser/health")

        assert response.status_code == 200
        data = response.json()
        assert data["available"] is True
        assert data["initialized"] is False


# Integration test for full flow
class TestBlock51Integration:
    """Integration tests for BLOQUE 51 components - file existence and basic structure."""

    def test_core_visualizer_component_exists(self):
        """Verify CoreVisualizer.tsx component was created."""
        component_path = Path("frontend/components/CoreVisualizer.tsx")
        assert component_path.exists(), "CoreVisualizer.tsx should exist"

        content = component_path.read_text()
        assert "CoreVisualizer" in content
        assert "CoreState" in content
        assert "listening" in content
        assert "thinking" in content
        assert "speaking" in content
        assert "processing" in content
        assert "ParticleField" in content
        assert "CoreSphere" in content
        assert "STATE_COLORS" in content
        assert "useFrame" in content
        assert "Canvas" in content

    def test_local_ai_bridge_exists(self):
        """Verify local_ai_bridge.py was created."""
        bridge_path = Path("backend/local_ai_bridge.py")
        assert bridge_path.exists(), "local_ai_bridge.py should exist"

        content = bridge_path.read_text()
        assert "LocalAIBridge" in content
        assert "ModelProfile" in content
        assert "DOLPHIN_7B" in content
        assert "generate_unrestricted" in content
        assert "InferenceRequest" in content
        assert "InferenceResponse" in content
        assert "ModelConfig" in content
        assert "from_profile" in content

    def test_browser_agent_exists(self):
        """Verify browser_agent.py was created."""
        agent_path = Path("backend/automation/browser_agent.py")
        assert agent_path.exists(), "browser_agent.py should exist"

        content = agent_path.read_text()
        assert "BrowserAgent" in content
        assert "BrowserConfig" in content
        assert "RollerCoinBot" in content
        assert "execute_workflow" in content
        assert "async_playwright" in content
        assert "WaitStrategy" in content
        assert "BrowserEngine" in content

    def test_routes_local_ai_exists(self):
        """Verify routes_local_ai.py was created."""
        routes_path = Path("backend/routes_local_ai.py")
        assert routes_path.exists(), "routes_local_ai.py should exist"

        content = routes_path.read_text()
        assert "local_ai_router" in content
        assert "browser_router" in content
        assert "/generate" in content
        assert "/generate/stream" in content
        assert "/rollercoin/login" in content
        assert "WebSocket" in content

    def test_main_py_includes_new_routes(self):
        """Verify main.py includes the new routers."""
        main_path = Path("backend/main.py")
        content = main_path.read_text(encoding="utf-8", errors="ignore")

        assert "local_ai_new_router" in content
        assert "browser_router" in content
        assert "routes_local_ai" in content

    def test_core_visualizer_uses_react_three_fiber(self):
        """Verify CoreVisualizer uses React Three Fiber."""
        component_path = Path("frontend/components/CoreVisualizer.tsx")
        content = component_path.read_text()

        assert "@react-three/fiber" in content
        assert "@react-three/drei" in content
        assert "three" in content.lower()

    def test_local_ai_bridge_supports_profiles(self):
        """Verify local_ai_bridge supports Dolphin and other profiles."""
        bridge_path = Path("backend/local_ai_bridge.py")
        content = bridge_path.read_text()

        assert "DOLPHIN_7B" in content
        assert "DOLPHIN_14B" in content
        assert "CODELLAMA_7B" in content
        assert "CODELLAMA_13B" in content
        assert "MISTRAL_7B_INSTRUCT" in content
        assert "NEURAL_CHAT_7B" in content
        assert "ZEPHYR_7B" in content
        assert "OPENCHAT_7B" in content

    def test_browser_agent_supports_workflows(self):
        """Verify browser_agent supports multi-step workflows."""
        agent_path = Path("backend/automation/browser_agent.py")
        content = agent_path.read_text()

        assert "execute_workflow" in content
        assert "navigate" in content
        assert "click" in content
        assert "fill" in content
        assert "type_text" in content
        assert "screenshot" in content
        assert "evaluate" in content
        assert "get_cookies" in content
        assert "set_cookies" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
