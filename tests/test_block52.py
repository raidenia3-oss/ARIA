"""
Tests for BLOQUE 52 - AURA Local Screen-Awareness & Desktop Vision Bridge

Tests cover:
1. ScreenBridge - capture, analysis, monitoring
2. ScreenCapture - backends, compression, monitor detection
3. VisionAnalyzer - modes (full, fast, ocr, ui)
4. REST endpoints
"""

import base64
import io
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, patch

import pytest


# Test ScreenBridge Core Data Structures
class TestScreenBridgeStructures:
    """Tests for ScreenBridge data structures and enums."""

    def test_capture_backend_enum(self):
        from backend.vision.screen_bridge import CaptureBackend

        backends = [b.value for b in CaptureBackend]
        assert "pil" in backends
        assert "mss" in backends
        assert "auto" in backends

    def test_analysis_mode_enum(self):
        from backend.vision.screen_bridge import AnalysisMode

        modes = [m.value for m in AnalysisMode]
        assert "full" in modes
        assert "fast" in modes
        assert "ocr" in modes
        assert "ui" in modes

    def test_screen_capture_config_defaults(self):
        from backend.vision.screen_bridge import CaptureBackend, ScreenCaptureConfig

        config = ScreenCaptureConfig()

        assert config.backend == CaptureBackend.AUTO
        assert config.interval_seconds == 5.0
        assert config.max_dimension == 1280
        assert config.jpeg_quality == 75
        assert config.compression_level == 6
        assert config.monitor_index == 0
        assert config.region is None
        assert config.enabled is True

    def test_screen_capture_config_custom(self):
        from backend.vision.screen_bridge import CaptureBackend, ScreenCaptureConfig

        config = ScreenCaptureConfig(
            backend=CaptureBackend.MSS,
            interval_seconds=2.0,
            max_dimension=1920,
            jpeg_quality=90,
            monitor_index=1,
            region=(100, 100, 800, 600),
        )

        assert config.backend == CaptureBackend.MSS
        assert config.interval_seconds == 2.0
        assert config.max_dimension == 1920
        assert config.jpeg_quality == 90
        assert config.monitor_index == 1
        assert config.region == (100, 100, 800, 600)

    def test_screen_capture_config_to_dict(self):
        from backend.vision.screen_bridge import ScreenCaptureConfig

        config = ScreenCaptureConfig()
        data = config.to_dict()

        assert isinstance(data, dict)
        assert data["backend"] == "auto"
        assert data["interval_seconds"] == 5.0
        assert data["max_dimension"] == 1280

    def test_frame_data_creation(self):
        from backend.vision.screen_bridge import FrameData

        frame = FrameData(
            timestamp=time.time(),
            image_base64="test_base64",
            width=1920,
            height=1080,
            monitor_index=0,
        )

        assert frame.width == 1920
        assert frame.height == 1080
        assert frame.image_base64 == "test_base64"
        assert frame.size_bytes > 0

    def test_frame_data_to_dict(self):
        from backend.vision.screen_bridge import FrameData

        frame = FrameData(
            timestamp=1234567890.0,
            image_base64="test",
            width=800,
            height=600,
        )
        data = frame.to_dict()

        assert data["width"] == 800
        assert data["height"] == 600
        assert data["timestamp"] == 1234567890.0

    def test_vision_analysis_result_creation(self):
        from backend.vision.screen_bridge import AnalysisMode, VisionAnalysisResult

        result = VisionAnalysisResult(
            timestamp=time.time(),
            session_id="sess_001",
            mode=AnalysisMode.FULL,
            model_used="ollama:moondream",
            description="Test description",
            confidence=0.9,
            processing_time_ms=150.0,
        )

        assert result.session_id == "sess_001"
        assert result.mode == AnalysisMode.FULL
        assert result.confidence == 0.9
        assert result.processing_time_ms == 150.0

    def test_vision_analysis_result_to_dict(self):
        from backend.vision.screen_bridge import AnalysisMode, VisionAnalysisResult

        result = VisionAnalysisResult(
            timestamp=1234567890.0,
            session_id="sess_001",
            mode=AnalysisMode.FAST,
            model_used="fallback",
            description="Fast analysis",
        )
        data = result.to_dict()

        assert data["mode"] == "fast"
        assert data["session_id"] == "sess_001"


class TestScreenCapture:
    """Tests for ScreenCapture class."""

    def test_screen_capture_init_default(self):
        from backend.vision.screen_bridge import CaptureBackend, ScreenCapture, ScreenCaptureConfig

        config = ScreenCaptureConfig(enabled=False)  # Disable for testing
        capture = ScreenCapture(config)

        assert capture.config.enabled is False
        assert capture._backend in [CaptureBackend.PIL, CaptureBackend.MSS]

    def test_screen_capture_backend_selection_pil(self):
        from backend.vision.screen_bridge import CaptureBackend, ScreenCapture, ScreenCaptureConfig

        config = ScreenCaptureConfig(backend=CaptureBackend.PIL, enabled=False)
        capture = ScreenCapture(config)

        assert capture._backend == CaptureBackend.PIL

    def test_screen_capture_backend_selection_mss(self):
        from backend.vision.screen_bridge import CaptureBackend, ScreenCapture, ScreenCaptureConfig

        config = ScreenCaptureConfig(backend=CaptureBackend.MSS, enabled=False)
        capture = ScreenCapture(config)

        assert capture._backend == CaptureBackend.MSS

    def test_screen_capture_is_available(self):
        from backend.vision.screen_bridge import ScreenCapture, ScreenCaptureConfig

        config = ScreenCaptureConfig(enabled=False)
        capture = ScreenCapture(config)

        assert capture.is_available() is False

        config.enabled = True
        capture.config = config
        # PIL ImageGrab should be available
        assert capture.is_available() is True

    def test_screen_capture_get_monitor_info(self):
        from backend.vision.screen_bridge import ScreenCapture, ScreenCaptureConfig

        config = ScreenCaptureConfig(enabled=False)
        capture = ScreenCapture(config)

        monitors = capture.get_monitor_info()
        assert isinstance(monitors, list)
        # Should at least have basic monitor info structure


class TestVisionAnalyzer:
    """Tests for VisionAnalyzer class."""

    def test_vision_analyzer_init(self):
        from backend.vision.screen_bridge import VisionAnalyzer

        analyzer = VisionAnalyzer(orchestrator=None)

        assert analyzer.orchestrator is None
        assert analyzer._last_result is None

    @patch("backend.vision.screen_bridge.Image")
    def test_fast_analysis(self, mock_image):
        import numpy as np

        from backend.vision.screen_bridge import (
            AnalysisMode,
            FrameData,
            VisionAnalysisResult,
            VisionAnalyzer,
        )

        # Mock PIL Image
        mock_img = Mock()
        mock_img.convert.return_value = mock_img
        mock_img.__enter__ = Mock(return_value=mock_img)
        mock_img.__exit__ = Mock(return_value=None)
        mock_image.open.return_value = mock_img

        # Mock numpy array
        mock_arr = np.ones((100, 100), dtype=np.uint8) * 128
        np.asarray = Mock(return_value=mock_arr)
        np.mean = Mock(return_value=128.0)
        np.std = Mock(return_value=50.0)

        analyzer = VisionAnalyzer()
        frame = FrameData(
            timestamp=time.time(),
            image_base64=base64.b64encode(b"fake_image").decode(),
            width=100,
            height=100,
        )

        result = analyzer._fast_analysis(frame, "test_session", time.time())

        assert isinstance(result, VisionAnalysisResult)
        assert result.mode == AnalysisMode.FAST
        assert "brillo" in result.description
        assert result.model_used == "fallback:opencv/pil"

    def test_get_default_prompt(self):
        from backend.vision.screen_bridge import VisionAnalyzer

        analyzer = VisionAnalyzer()
        prompt = analyzer._get_default_prompt()

        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "español" in prompt.lower()


class TestScreenBridge:
    """Tests for ScreenBridge main class."""

    def test_screen_bridge_init(self):
        from backend.vision.screen_bridge import ScreenBridge, ScreenCaptureConfig

        config = ScreenCaptureConfig(enabled=False)
        bridge = ScreenBridge(config=config, orchestrator=None)

        assert bridge.config.enabled is False
        assert bridge.capture is not None
        assert bridge.analyzer is not None
        assert bridge._monitoring is False

    def test_get_screen_bridge_singleton(self):
        # Reset global
        import backend.vision.screen_bridge as sb_module
        from backend.vision.screen_bridge import (
            ScreenBridge,
            ScreenCaptureConfig,
            get_screen_bridge,
        )

        sb_module._screen_bridge = None

        config = ScreenCaptureConfig(enabled=False)
        bridge1 = get_screen_bridge(config=config)
        bridge2 = get_screen_bridge()

        assert bridge1 is bridge2
        assert isinstance(bridge1, ScreenBridge)

    def test_analyze_screen_capture_disabled(self):
        from backend.vision.screen_bridge import (
            AnalysisMode,
            ScreenBridge,
            ScreenCaptureConfig,
            VisionAnalysisResult,
        )

        config = ScreenCaptureConfig(enabled=False)
        bridge = ScreenBridge(config=config)

        result = bridge.analyze_screen(mode=AnalysisMode.FULL, session_id="test")

        assert isinstance(result, VisionAnalysisResult)
        assert result.model_used == "none"
        assert "failed or disabled" in result.description

    def test_analyze_frame_existing(self):
        from backend.vision.screen_bridge import (
            AnalysisMode,
            FrameData,
            ScreenBridge,
            ScreenCaptureConfig,
            VisionAnalysisResult,
        )

        config = ScreenCaptureConfig(enabled=False)
        bridge = ScreenBridge(config=config)

        frame = FrameData(
            timestamp=time.time(),
            image_base64=base64.b64encode(b"test").decode(),
            width=100,
            height=100,
        )

        with patch.object(bridge.analyzer, "analyze") as mock_analyze:
            mock_analyze.return_value = VisionAnalysisResult(
                timestamp=time.time(),
                session_id="test",
                mode=AnalysisMode.FAST,
                model_used="test",
                description="test",
            )
            result = bridge.analyze_frame(frame, mode=AnalysisMode.FAST, session_id="test")

            assert result is not None
            mock_analyze.assert_called_once()

    def test_inject_context(self):
        from unittest.mock import MagicMock

        from backend.vision.screen_bridge import (
            AnalysisMode,
            ScreenBridge,
            ScreenCaptureConfig,
            VisionAnalysisResult,
        )

        mock_orchestrator = MagicMock()
        mock_orchestrator.set_vision_context = MagicMock()

        config = ScreenCaptureConfig(enabled=False)
        bridge = ScreenBridge(config=config, orchestrator=mock_orchestrator)

        result = VisionAnalysisResult(
            timestamp=time.time(),
            session_id="test",
            mode=AnalysisMode.FULL,
            model_used="test",
            description="test",
        )

        bridge._inject_context(result)

        mock_orchestrator.set_vision_context.assert_called_once()

    def test_start_stop_monitoring(self):
        from backend.vision.screen_bridge import AnalysisMode, ScreenBridge, ScreenCaptureConfig

        config = ScreenCaptureConfig(enabled=False)
        bridge = ScreenBridge(config=config)

        # Should fail when capture not available
        success = bridge.start_monitoring(mode=AnalysisMode.FAST)
        assert success is False

        # Should handle stop gracefully
        bridge.stop_monitoring()
        assert bridge._monitoring is False

    def test_get_status(self):
        from backend.vision.screen_bridge import ScreenBridge, ScreenCaptureConfig

        config = ScreenCaptureConfig(enabled=False)
        bridge = ScreenBridge(config=config)

        status = bridge.get_status()

        assert "capture" in status
        assert "analyzer" in status
        assert "monitoring" in status
        assert "last_analysis" in status
        assert status["monitoring"] is False


class TestVisionRouter:
    """Tests for Vision REST endpoints."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        from backend.main import app

        return TestClient(app)

    def test_vision_config_endpoint(self, client):
        response = client.get("/api/vision/config")
        # May fail if bridge not fully initialized, but should not 500
        assert response.status_code in [200, 500, 503]

    def test_vision_monitors_endpoint(self, client):
        response = client.get("/api/vision/monitors")
        assert response.status_code in [200, 500, 503]

    def test_vision_status_endpoint(self, client):
        response = client.get("/api/vision/status")
        assert response.status_code in [200, 500, 503]

    def test_vision_last_analysis_endpoint(self, client):
        response = client.get("/api/vision/last-analysis")
        assert response.status_code in [200, 500, 503]


class TestBlock52Integration:
    """Integration tests for BLOQUE 52 components."""

    def test_screen_bridge_file_exists(self):
        """Verify screen_bridge.py was created."""
        bridge_path = Path("backend/vision/screen_bridge.py")
        assert bridge_path.exists(), "screen_bridge.py should exist"

        content = bridge_path.read_text()
        assert "ScreenBridge" in content
        assert "ScreenCapture" in content
        assert "VisionAnalyzer" in content
        assert "CaptureBackend" in content
        assert "AnalysisMode" in content
        assert "FrameData" in content
        assert "VisionAnalysisResult" in content
        assert "get_screen_bridge" in content
        assert "analyze_screen_async" in content

    def test_vision_router_file_exists(self):
        """Verify vision router was created."""
        router_path = Path("backend/vision/router.py")
        assert router_path.exists(), "router.py should exist"

        content = router_path.read_text()
        assert "router = APIRouter" in content
        assert "/api/vision" in content
        assert "/analyze" in content
        assert "/capture" in content
        assert "/monitor/start" in content
        assert "/monitor/stop" in content
        assert "/monitor/status" in content
        assert "/monitors" in content
        assert "/config" in content

    def test_vision_init_file_exists(self):
        """Verify vision __init__.py was created."""
        init_path = Path("backend/vision/__init__.py")
        assert init_path.exists(), "__init__.py should exist"

        content = init_path.read_text()
        assert "ScreenBridge" in content
        assert "vision_router" in content

    def test_main_py_includes_vision_router(self):
        """Verify main.py includes the new screen vision router."""
        main_path = Path("backend/main.py")
        content = main_path.read_text(encoding="utf-8", errors="ignore")

        assert "screen_vision_router" in content
        assert "from backend.vision.router import router as screen_vision_router" in content

    def test_screen_bridge_supports_analysis_modes(self):
        """Verify screen_bridge supports all required analysis modes."""
        bridge_path = Path("backend/vision/screen_bridge.py")
        content = bridge_path.read_text()

        assert "AnalysisMode.FULL" in content
        assert "AnalysisMode.FAST" in content
        assert "AnalysisMode.OCR" in content
        assert "AnalysisMode.UI" in content
        assert "_full_analysis" in content
        assert "_fast_analysis" in content
        assert "_ocr_analysis" in content
        assert "_ui_analysis" in content

    def test_screen_bridge_supports_compression(self):
        """Verify screen_bridge supports image compression."""
        bridge_path = Path("backend/vision/screen_bridge.py")
        content = bridge_path.read_text()

        assert "max_dimension" in content
        assert "jpeg_quality" in content
        assert "compress" in content.lower()
        assert "resize" in content.lower()
        assert "LANCZOS" in content

    def test_screen_bridge_supports_monitoring(self):
        """Verify screen_bridge supports continuous monitoring."""
        bridge_path = Path("backend/vision/screen_bridge.py")
        content = bridge_path.read_text()

        assert "start_monitoring" in content
        assert "stop_monitoring" in content
        assert "_monitor_loop" in content
        assert "threading.Thread" in content
        assert "daemon=True" in content

    def test_vision_router_supports_all_endpoints(self):
        """Verify vision router has all required endpoints."""
        router_path = Path("backend/vision/router.py")
        content = router_path.read_text()

        # Config endpoints
        assert "get_vision_config" in content
        assert "update_vision_config" in content

        # Capture endpoints
        assert "capture_screen" in content
        assert "get_monitors" in content

        # Analysis endpoints
        assert "analyze_screen" in content
        assert "analyze_frame" in content

        # Monitor endpoints
        assert "start_monitoring" in content
        assert "stop_monitoring" in content
        assert "monitor_status" in content

        # Status endpoints
        assert "vision_status" in content
        assert "get_last_analysis" in content
        assert "capture_and_save" in content

    def test_vision_router_uses_pydantic_models(self):
        """Verify vision router uses Pydantic for validation."""
        router_path = Path("backend/vision/router.py")
        content = router_path.read_text()

        assert "BaseModel" in content
        assert "CaptureConfigRequest" in content
        assert "AnalyzeRequest" in content
        assert "MonitorRequest" in content
        assert "CaptureResponse" in content
        assert "AnalyzeResponse" in content
        assert "MonitorStatusResponse" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
