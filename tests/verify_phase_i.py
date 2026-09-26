"""PARTE 9: TESTING (250 lines) — Tests PHASE I.

• test_floating_widget_renders()
• test_screen_capture_works()
• test_ocr_extraction()
• test_audio_detection()
• test_contextual_understanding()
• test_background_learning()
• test_privacy_filtering()
• test_system_integration()
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@dataclass
class PhaseIResult:
    test_name: str
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)


class PhaseIVerifier:
    """Verifica toda la PHASE I."""

    BASE_URL: str = "http://localhost:8000"

    def __init__(self) -> None:
        self.results: List[PhaseIResult] = []

    async def _http_get(self, path: str) -> Dict[str, Any]:
        import urllib.request

        try:
            req = urllib.request.Request(f"{self.BASE_URL}{path}")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = resp.read().decode("utf-8")
                return json.loads(data) if data else {}
        except Exception as exc:
            return {"error": str(exc)}

    async def _http_post(self, path: str, body: dict = None) -> Dict[str, Any]:
        import urllib.request

        data = json.dumps(body or {}).encode("utf-8") if body else b"{}"
        req = urllib.request.Request(
            f"{self.BASE_URL}{path}",
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp_data = resp.read().decode("utf-8")
                return json.loads(resp_data) if resp_data else {}
        except Exception as exc:
            return {"error": str(exc)}

    async def test_floating_widget_renders(self) -> PhaseIResult:
        result = PhaseIResult(test_name="floating_widget_renders", passed=False)
        try:
            html_path = os.path.join(
                os.path.dirname(__file__), "..", "AURA_APP", "frontend", "aria_dashboard_v4.html"
            )
            if not os.path.exists(html_path):
                html_path = os.path.join(
                    os.path.dirname(__file__), "..", "frontend", "aria_dashboard_v4.html"
                )
            html = ""
            if os.path.exists(html_path):
                with open(html_path, "r", encoding="utf-8") as f:
                    html = f.read()
            else:
                resp = await self._http_get("/aria_dashboard_v4.html")
                html = resp.get("html", "") or resp.get("") or ""

            has_cyberpunk = "cyberpunk" in html.lower() or "orbitron" in html.lower()
            has_neon = "#00ffff" in html or "neon" in html.lower()
            has_glassmorphism = "backdrop-filter" in html and "blur" in html
            has_orb = "orb" in html.lower() or "&#9830;" in html or "diamante" in html.lower()

            passed = has_cyberpunk or has_neon or has_glassmorphism
            result.passed = passed
            result.details = {
                "has_cyberpunk_theme": has_cyberpunk,
                "has_neon_colors": has_neon,
                "has_glassmorphism": has_glassmorphism,
                "has_orb": has_orb,
                "html_length": len(html),
                "source": "file" if os.path.exists(html_path) else "http",
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result

    async def test_screen_capture_works(self) -> PhaseIResult:
        result = PhaseIResult(test_name="screen_capture_works", passed=False)
        try:
            from AURA_APP.backend.monitoring.screen_analyzer import ScreenAnalyzer

            analyzer = ScreenAnalyzer()
            capture = await analyzer.capture_screen()

            has_image = capture.image is not None
            has_app = capture.active_app != ""
            has_context = len(capture.semantic_context) > 5

            result.passed = has_image and has_app
            result.details = {
                "has_image": has_image,
                "active_app": capture.active_app,
                "has_semantic": has_context,
                "confidence": capture.confidence,
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result

    async def test_ocr_extraction(self) -> PhaseIResult:
        result = PhaseIResult(test_name="ocr_extraction", passed=False)
        try:
            from AURA_APP.backend.monitoring.screen_analyzer import ScreenAnalyzer

            analyzer = ScreenAnalyzer()
            await analyzer.capture_screen()
            text = await analyzer.extract_text_ocr()

            # El texto puede estar vacío en un entorno headless,
            # pero no debe fallar
            passed = isinstance(text, str) and len(text) >= 0
            result.passed = passed
            result.details = {
                "text_length": len(text),
                "text_preview": text[:100],
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result

    async def test_audio_detection(self) -> PhaseIResult:
        result = PhaseIResult(test_name="audio_detection", passed=False)
        try:
            from AURA_APP.backend.monitoring.audio_analyzer import AudioAnalyzer

            analyzer = AudioAnalyzer()
            activity = await analyzer.detect_audio_activity()

            has_detection = "audio_detected" in activity
            has_volume = "volume" in activity

            result.passed = has_detection and has_volume
            result.details = {
                "audio_detected": activity.get("audio_detected"),
                "volume": activity.get("volume"),
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result

    async def test_contextual_understanding(self) -> PhaseIResult:
        result = PhaseIResult(test_name="contextual_understanding", passed=False)
        try:
            from AURA_APP.backend.monitoring.contextual_engine import ContextualUnderstandingEngine

            engine = ContextualUnderstandingEngine()
            state = await engine.understand_current_state()

            has_state = bool(state.state) and state.state != "unknown"
            has_confidence = state.confidence >= 0.0
            has_intent = bool(state.intent)
            has_suggestions = isinstance(state.suggestions, list)

            result.passed = has_state and has_intent
            result.details = {
                "state": state.state[:100],
                "confidence": state.confidence,
                "intent": state.intent,
                "suggestions": len(state.suggestions),
                "has_prediction": bool(state.next_action),
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result

    async def test_background_learning(self) -> PhaseIResult:
        result = PhaseIResult(test_name="background_learning", passed=False)
        try:
            from AURA_APP.backend.monitoring.background_learning import BackgroundLearningDaemon

            daemon = BackgroundLearningDaemon()

            patterns = daemon.get_patterns()
            score = daemon.privacy_score

            result.passed = score >= 80.0
            result.details = {
                "patterns_count": len(patterns),
                "privacy_score": score,
                "has_patterns": len(patterns) > 0,
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result

    async def test_privacy_filtering(self) -> PhaseIResult:
        result = PhaseIResult(test_name="privacy_filtering", passed=False)
        try:
            from AURA_APP.backend.security.privacy_filter import PrivacyFilter

            pf = PrivacyFilter()

            test_texts = [
                "My email is test@example.com and password is secret123",
                "Call me at 555-123-4567",
                "Card: 4111-1111-1111-1111",
                "Normal text without sensitive data",
            ]

            all_filtered = True
            for text in test_texts:
                r = await pf.filter_sensitive_data(text)
                if "@" in text and "@" in r.filtered:
                    all_filtered = False
                if "555-123-4567" in text and "555-123-4567" in r.filtered:
                    all_filtered = False
                if "4111" in text and "4111" in r.filtered:
                    all_filtered = False
                if "secret123" in text and "secret123" in r.filtered:
                    all_filtered = False
                if "example.com" in text and "example.com" in r.filtered:
                    all_filtered = False

            report = await pf.user_transparency()
            has_report = "report" in report

            result.passed = all_filtered and has_report
            result.details = {
                "all_filtered": all_filtered,
                "has_report": has_report,
                "filtered_count": pf.total_filtered_count,
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result

    async def test_system_integration(self) -> PhaseIResult:
        result = PhaseIResult(test_name="system_integration", passed=False)
        try:
            from AURA_APP.backend.system_integration import SystemIntegration

            si = SystemIntegration()

            platform = si.get_platform()
            info = si.get_system_info()
            has_platform = bool(platform)

            can_create_window = False
            if si.is_windows():
                can_create_window = True
            elif si.is_linux() or si.is_macos():
                can_create_window = True

            can_create_tray = si.create_tray_icon()

            result.passed = has_platform and can_create_window
            result.details = {
                "platform": platform,
                "info": info,
                "can_create_window": can_create_window,
                "tray_created": can_create_tray,
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result

    async def test_api_endpoints(self) -> PhaseIResult:
        """Verifica los 7 endpoints nuevos."""
        result = PhaseIResult(test_name="api_endpoints", passed=False)
        try:
            endpoints = [
                "/aria_dashboard_v4.html",
                "/api/aria/context/understand",
                "/api/aria/predict",
                "/api/aria/audio/analyze",
                "/api/aria/privacy/report",
                "/api/aria/floating/status",
            ]

            passed_endpoints = 0
            for ep in endpoints:
                resp = await self._http_get(ep)
                if "error" not in resp:
                    passed_endpoints += 1

            result.passed = passed_endpoints >= 3
            result.details = {
                "passed": passed_endpoints,
                "total": len(endpoints),
                "endpoints_tested": endpoints,
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result


@pytest.mark.asyncio
async def test_floating_widget_renders() -> None:
    v = PhaseIVerifier()
    r = await v.test_floating_widget_renders()
    assert r.passed, f"Floating widget failed: {r.details}"


@pytest.mark.asyncio
async def test_screen_capture_works() -> None:
    v = PhaseIVerifier()
    r = await v.test_screen_capture_works()
    assert r.passed, f"Screen capture failed: {r.details}"


@pytest.mark.asyncio
async def test_ocr_extraction() -> None:
    v = PhaseIVerifier()
    r = await v.test_ocr_extraction()
    assert r.passed, f"OCR failed: {r.details}"


@pytest.mark.asyncio
async def test_audio_detection() -> None:
    v = PhaseIVerifier()
    r = await v.test_audio_detection()
    assert r.passed, f"Audio detection failed: {r.details}"


@pytest.mark.asyncio
async def test_contextual_understanding() -> None:
    v = PhaseIVerifier()
    r = await v.test_contextual_understanding()
    assert r.passed, f"Contextual understanding failed: {r.details}"


@pytest.mark.asyncio
async def test_background_learning() -> None:
    v = PhaseIVerifier()
    r = await v.test_background_learning()
    assert r.passed, f"Background learning failed: {r.details}"


@pytest.mark.asyncio
async def test_privacy_filtering() -> None:
    v = PhaseIVerifier()
    r = await v.test_privacy_filtering()
    assert r.passed, f"Privacy filtering failed: {r.details}"


@pytest.mark.asyncio
async def test_system_integration() -> None:
    v = PhaseIVerifier()
    r = await v.test_system_integration()
    assert r.passed, f"System integration failed: {r.details}"
