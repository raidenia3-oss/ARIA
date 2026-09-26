"""Tests for Vision Engine - image processing and analysis."""

from __future__ import annotations

import base64
import io
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from backend.services.vision_engine import VisionEngine


@pytest.fixture
def vision_engine():
    return VisionEngine(orchestrator=None)


@pytest.fixture
def sample_image_png():
    img = Image.new("RGB", (100, 100), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def sample_image_base64(sample_image_png):
    return base64.b64encode(sample_image_png).decode()


def test_vision_engine_init(vision_engine):
    assert vision_engine is not None
    assert vision_engine.orchestrator is None


def test_analyze_frame_valid(vision_engine, sample_image_base64):
    with patch.object(vision_engine, "_ollama_vision", return_value="red frame"):
        result = vision_engine.analyze_frame(sample_image_base64, session_id="s1")
    assert result is not None
    assert result.get("session_id") == "s1"
    assert "description" in result
    assert "model" in result


def test_analyze_frame_fallback(vision_engine, sample_image_base64):
    with patch.object(vision_engine, "_ollama_vision", side_effect=RuntimeError("ollama down")):
        result = vision_engine.analyze_frame(sample_image_base64, session_id="s1")
    assert result is not None
    assert result.get("model") == "fallback:opencv/pil"
    assert "description" in result


def test_analyze_frame_invalid_image(vision_engine):
    result = vision_engine.analyze_frame("not-an-image", session_id="s1")
    assert result is not None
    assert result.get("error") == "invalid_image"


def test_analyze_screenshot_alias(vision_engine, sample_image_base64):
    with patch.object(vision_engine, "_ollama_vision", return_value="screenshot"):
        result = vision_engine.analyze_screenshot(sample_image_base64, session_id="s2")
    assert result is not None
    assert result.get("session_id") == "s2"


def test_get_status(vision_engine):
    status = vision_engine.get_status()
    assert isinstance(status, dict)
    assert "model" in status
    assert "last_analysis" in status
    assert "last_analysis_time" in status


def test_fallback_analysis_pil():
    engine = VisionEngine()
    img = Image.new("RGB", (64, 64), color="blue")
    desc = engine._fallback_analysis(img)
    assert isinstance(desc, str)
    assert "64" in desc or "Frame" in desc


def test_fallback_analysis_numpy():
    engine = VisionEngine()
    arr = np.zeros((32, 32, 3), dtype=np.uint8)
    desc = engine._fallback_analysis(arr)
    assert isinstance(desc, str)


def test_inject_into_orchestrator(vision_engine):
    orchestrator = MagicMock()
    orchestrator.set_vision_context = MagicMock()
    engine = VisionEngine(orchestrator=orchestrator)
    engine._inject_into_orchestrator({"description": "test"})
    orchestrator.set_vision_context.assert_called_once()


def test_inject_into_orchestrator_without_target(vision_engine):
    engine = VisionEngine(orchestrator=object())
    engine._inject_into_orchestrator({"description": "test"})
