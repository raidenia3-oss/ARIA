"""Tests complementarios BLOQUE 52 - inyeccion de contexto y compresion de frames.

Cubre la integracion real entre el inyector de contexto visual
(ScreenBridge._inject_context) y el nucleo de razonamiento local
(ReactLoop.set_vision_context), ademas de la compresion adaptativa
de frames y la cadencia configurable del monitoreo continuo.
"""

from __future__ import annotations

import base64
import time
from unittest.mock import MagicMock, patch


class TestVisionContextText:
    def test_to_context_text_contains_textual_metadata(self):
        from backend.vision.screen_bridge import AnalysisMode, VisionAnalysisResult

        result = VisionAnalysisResult(
            timestamp=time.time(),
            session_id="s1",
            mode=AnalysisMode.FULL,
            model_used="jan:llava",
            description="Ventana de codigo con error resaltado en rojo",
            confidence=0.82,
            frame_info={"width": 1280, "height": 720},
        )

        text = result.to_context_text()

        assert isinstance(text, str)
        assert text
        assert "descripción" in text
        assert "modelo" in text
        assert "confianza" in text
        assert "1280x720" in text

    def test_to_context_text_without_optional_frame_info(self):
        from backend.vision.screen_bridge import AnalysisMode, VisionAnalysisResult

        result = VisionAnalysisResult(
            timestamp=time.time(),
            session_id="s1",
            mode=AnalysisMode.OCR,
            model_used="ollama:moondream",
            description="texto extraido",
        )

        assert "modo: ocr" in result.to_context_text()


class TestVisionContextInjection:
    def test_inject_context_passes_textual_context(self):
        from backend.vision.screen_bridge import (
            AnalysisMode,
            ScreenBridge,
            ScreenCaptureConfig,
            VisionAnalysisResult,
        )

        orchestrator = MagicMock()
        bridge = ScreenBridge(config=ScreenCaptureConfig(enabled=False), orchestrator=orchestrator)
        result = VisionAnalysisResult(
            timestamp=time.time(),
            session_id="s",
            mode=AnalysisMode.FULL,
            model_used="jan",
            description="panel con error",
            confidence=0.5,
        )

        bridge._inject_context(result)

        orchestrator.set_vision_context.assert_called_once()
        context = orchestrator.set_vision_context.call_args[0][0]
        assert "context_text" in context
        assert "descripción" in context["context_text"]

    def test_screen_bridge_injects_into_react_loop_core(self):
        from backend.agents.react_loop import ReactLoop
        from backend.vision.screen_bridge import (
            AnalysisMode,
            ScreenBridge,
            ScreenCaptureConfig,
            VisionAnalysisResult,
        )

        reasoning_core = ReactLoop()
        bridge = ScreenBridge(
            config=ScreenCaptureConfig(enabled=False), orchestrator=reasoning_core
        )
        result = VisionAnalysisResult(
            timestamp=time.time(),
            session_id="s",
            mode=AnalysisMode.FULL,
            model_used="jan",
            description="ventana con error",
            confidence=0.5,
        )

        bridge._inject_context(result)

        assert reasoning_core.get_vision_context_text()
        assert "descripción" in reasoning_core.get_vision_context_text()

    def test_react_loop_reasoning_consumes_stored_context(self):
        from backend.agents.react_loop import ReactLoop

        reasoning_core = ReactLoop()
        assert reasoning_core.get_vision_context_text() == ""
        reasoning_core.set_vision_context(
            {
                "context_text": "ventana con error",
                "description": "ventana",
            }
        )

        assert reasoning_core.get_vision_context_text() == "ventana con error"
        assert "ventana con error" in reasoning_core._fallback_response("hola")


class TestVisionCapturePipeline:
    def test_frame_compression_resizes_and_records_size(self):
        from PIL import Image

        from backend.vision.screen_bridge import ScreenCapture, ScreenCaptureConfig

        capture = ScreenCapture(
            ScreenCaptureConfig(enabled=False, max_dimension=256, jpeg_quality=60)
        )
        source = Image.new("RGB", (2000, 1000), (123, 45, 67))

        frame = capture._process_image(source, 0, 0)

        assert frame.width == 256
        assert frame.height <= 256
        assert frame.metadata["original_width"] == 2000
        assert frame.metadata["compressed_size_bytes"] > 0
        assert frame.size_bytes > 0

    def test_continuous_monitoring_uses_refresh_interval(self):
        from backend.vision.screen_bridge import (
            AnalysisMode,
            FrameData,
            ScreenBridge,
            ScreenCaptureConfig,
            VisionAnalysisResult,
        )

        bridge = ScreenBridge(config=ScreenCaptureConfig(enabled=True, interval_seconds=0.05))
        bridge.capture.is_available = lambda: True
        frame = FrameData(
            timestamp=time.time(),
            image_base64=base64.b64encode(b"x").decode(),
            width=10,
            height=10,
        )
        result = VisionAnalysisResult(
            timestamp=time.time(),
            session_id="s",
            mode=AnalysisMode.FAST,
            model_used="m",
            description="d",
        )

        with (
            patch.object(bridge.capture, "capture", return_value=frame),
            patch.object(bridge.analyzer, "analyze", return_value=result),
        ):
            seen = []
            assert (
                bridge.start_monitoring(
                    mode=AnalysisMode.FAST,
                    session_id="s",
                    callback=lambda item: seen.append(item),
                )
                is True
            )
            time.sleep(0.2)
            bridge.stop_monitoring()

        assert len(seen) >= 1
