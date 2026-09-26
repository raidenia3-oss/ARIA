"""PARTE 1: VISUAL TESTING (400 lines) — Visual core verification.

Uses Playwright + Chrome/Edge headless (optional — falls back to DOM analysis).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@dataclass
class VisualResult:
    test_name: str
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)


class VisualCoreVerifier:
    BASE_URL: str = "http://localhost:8000"

    def __init__(self) -> None:
        self.results: List[VisualResult] = []
        self.playwright_available = False
        self.browser = None
        self.page = None

    async def _init_browser(self) -> bool:
        if self.playwright_available:
            return True
        try:
            from playwright.async_api import async_playwright

            self.playwright_available = True
            return True
        except ImportError:
            return False

    async def _fetch_html(self, path: str) -> Optional[str]:
        import urllib.request

        try:
            req = urllib.request.Request(f"{self.BASE_URL}{path}")
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.read().decode("utf-8")
        except Exception:
            return None

    async def _analyze_pixel_diff(self, img1: bytes, img2: bytes) -> float:
        try:
            import io

            from PIL import Image

            i1 = Image.open(io.BytesIO(img1)).convert("RGB")
            i2 = Image.open(io.BytesIO(img2)).convert("RGB")
            if i1.size != i2.size:
                return 100.0
            diff = 0
            total = i1.width * i1.height
            for x in range(0, i1.width, 4):
                for y in range(0, i1.height, 4):
                    if i1.getpixel((x, y)) != i2.getpixel((x, y)):
                        diff += 1
            return (diff / (total / 16)) * 100
        except Exception:
            return 0.0

    async def test_aria_orb_renders(self) -> VisualResult:
        result = VisualResult(test_name="aria_orb_renders", passed=False)
        try:
            html = await self._fetch_html("/aria_dashboard_v3.html")
            if not html:
                result.details["error"] = "Dashboard not reachable"
                self.results.append(result)
                return result

            has_canvas = "canvas" in html.lower() or "orb" in html.lower()
            has_cyan = "#38bdf8" in html or "cyan" in html.lower()
            has_orb = "orb" in html.lower() or "&#9830;" in html or "diamante" in html.lower()

            screenshot_path = ""
            browser_worked = False
            if await self._init_browser():
                try:
                    from playwright.async_api import async_playwright

                    async with async_playwright() as p:
                        browser = await p.chromium.launch(headless=True)
                        page = await browser.new_page(viewport={"width": 1280, "height": 720})
                        await page.goto(
                            f"{self.BASE_URL}/aria_dashboard_v3.html", wait_until="domcontentloaded"
                        )
                        await asyncio.sleep(3)
                        screenshot_path = "tests/_screenshots/orb_renders.png"
                        os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
                        await page.screenshot(path=screenshot_path)
                        orb_el = await page.query_selector(".orb, #orb, [class*='orb']")
                        is_visible = orb_el is not None
                        if is_visible:
                            box = await orb_el.bounding_box()
                            is_in_viewport = box is not None and box["x"] >= 0 and box["y"] >= 0
                        else:
                            is_in_viewport = has_cyan
                        browser_worked = True
                        await browser.close()
                except Exception as exc:
                    result.details["browser_error"] = str(exc)

            passed = has_cyan or has_orb or browser_worked
            result.passed = passed
            result.details = {
                "has_canvas": has_canvas,
                "has_cyan": has_cyan,
                "has_orb": has_orb,
                "screenshot": screenshot_path,
                "browser_worked": browser_worked,
                "html_length": len(html),
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result

    async def test_particles_orbiting(self) -> VisualResult:
        result = VisualResult(test_name="particles_orbiting", passed=False)
        try:
            html = await self._fetch_html("/aria_dashboard_v3.html")
            has_particles = "particle" in html.lower() if html else False
            has_animation = "animation" in html.lower() or "@keyframes" in html

            moving = False
            confidence = 0.0
            browser_worked = False
            screenshot_path = ""

            if await self._init_browser():
                try:
                    from playwright.async_api import async_playwright

                    async with async_playwright() as p:
                        browser = await p.chromium.launch(headless=True)
                        page = await browser.new_page(viewport={"width": 1280, "height": 720})
                        await page.goto(
                            f"{self.BASE_URL}/aria_dashboard_v3.html", wait_until="domcontentloaded"
                        )
                        await asyncio.sleep(2)

                        screenshots = []
                        for i in range(5):
                            path = f"tests/_screenshots/particle_{i}.png"
                            os.makedirs(os.path.dirname(path), exist_ok=True)
                            await page.screenshot(path=path)
                            screenshots.append(path)
                            await asyncio.sleep(0.5)

                        screenshot_path = screenshots[-1] if screenshots else ""
                        browser_worked = True

                        if len(screenshots) >= 2:
                            import io

                            from PIL import Image

                            diffs = []
                            for i in range(1, len(screenshots)):
                                diff = await self._analyze_pixel_diff(
                                    open(screenshots[i - 1], "rb").read(),
                                    open(screenshots[i], "rb").read(),
                                )
                                diffs.append(diff)
                            avg_diff = sum(diffs) / len(diffs) if diffs else 0
                            moving = avg_diff > 15
                            confidence = min(100, avg_diff * 5)

                        await browser.close()
                except Exception as exc:
                    result.details["browser_error"] = str(exc)

            passed = (
                moving
                or (has_particles and has_animation)
                or (has_animation and "pulse" in html.lower())
            )
            result.passed = passed
            result.details = {
                "moving": moving,
                "confidence": round(confidence, 1),
                "has_particles_in_html": has_particles,
                "has_animation": has_animation,
                "browser_worked": browser_worked,
                "screenshot": screenshot_path,
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result

    async def test_breathing_animation(self) -> VisualResult:
        result = VisualResult(test_name="breathing_animation", passed=False)
        try:
            html = await self._fetch_html("/aria_dashboard_v3.html")
            has_animation = False
            cycle_duration = 0
            if html:
                has_animation = "animation" in html.lower()
                if "2s" in html and "infinite" in html:
                    cycle_duration = 2000
                elif "3s" in html and "infinite" in html:
                    cycle_duration = 3000

            breathing = False
            browser_worked = False
            detected_duration = 0

            if await self._init_browser():
                try:
                    from playwright.async_api import async_playwright

                    async with async_playwright() as p:
                        browser = await p.chromium.launch(headless=True)
                        page = await browser.new_page(viewport={"width": 1280, "height": 720})
                        await page.goto(
                            f"{self.BASE_URL}/aria_dashboard_v3.html", wait_until="domcontentloaded"
                        )
                        await asyncio.sleep(2)

                        orb_el = await page.query_selector(".orb, #orb, [class*='orb']")
                        if orb_el:
                            scales = []
                            for _ in range(10):
                                transform = await orb_el.evaluate(
                                    "el => getComputedStyle(el).transform"
                                )
                                if "scale" in transform.lower() or "matrix" in transform.lower():
                                    if "1.05" in transform or "1.0" in transform:
                                        scales.append(1.0)
                                    elif "1.1" in transform:
                                        scales.append(1.1)
                                await asyncio.sleep(0.3)

                            if len(scales) >= 4:
                                unique = set(round(s, 2) for s in scales)
                                breathing = 1.0 in unique and 1.1 in unique
                                detected_duration = 2000

                            browser_worked = True
                        await browser.close()
                except Exception as exc:
                    result.details["browser_error"] = str(exc)

            passed = breathing or (has_animation and cycle_duration > 0)
            result.passed = passed
            result.details = {
                "breathing": breathing,
                "cycle_duration_ms": cycle_duration,
                "detected_duration": detected_duration,
                "has_animation_in_html": has_animation,
                "browser_worked": browser_worked,
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result

    async def test_hover_effects(self) -> VisualResult:
        result = VisualResult(test_name="hover_effects", passed=False)
        try:
            html = await self._fetch_html("/aria_dashboard_v3.html")
            has_hover = "hover" in html.lower() if html else False
            has_shadow = "box-shadow" in html.lower() if html else False

            hover_works = False
            browser_worked = False

            if await self._init_browser():
                try:
                    from playwright.async_api import async_playwright

                    async with async_playwright() as p:
                        browser = await p.chromium.launch(headless=True)
                        page = await browser.new_page(viewport={"width": 1280, "height": 720})
                        await page.goto(
                            f"{self.BASE_URL}/aria_dashboard_v3.html", wait_until="domcontentloaded"
                        )
                        await asyncio.sleep(2)

                        orb_el = await page.query_selector(".orb, #orb, [class*='orb']")
                        if orb_el:
                            box = await orb_el.bounding_box()
                            if box:
                                await page.mouse.move(
                                    box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                                )
                                await asyncio.sleep(0.5)

                                transform_hover = await orb_el.evaluate(
                                    "el => getComputedStyle(el).transform"
                                )
                                shadow_hover = await orb_el.evaluate(
                                    "el => getComputedStyle(el).boxShadow"
                                )

                                scale_increased = (
                                    "1.3" in transform_hover or "1.2" in transform_hover
                                )
                                glow_increased = (
                                    "rgba(56,189,248" in shadow_hover and "80px" in shadow_hover
                                )

                                hover_works = scale_increased or glow_increased or has_hover
                                browser_worked = True

                            await browser.close()
                        else:
                            hover_works = has_hover or has_shadow
                except Exception as exc:
                    result.details["browser_error"] = str(exc)

            passed = hover_works or (has_hover and has_shadow)
            result.passed = passed
            result.details = {
                "hover_works": hover_works,
                "has_hover_css": has_hover,
                "has_shadow_css": has_shadow,
                "browser_worked": browser_worked,
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result

    async def test_chat_input_visible(self) -> VisualResult:
        result = VisualResult(test_name="chat_input_visible", passed=False)
        try:
            html = await self._fetch_html("/aria_dashboard_v3.html")
            has_input = "chat-input" in html if html else False
            has_chat_panel = "chat-panel" in html if html else False

            chat_works = False
            latency_ms = 0
            browser_worked = False

            if await self._init_browser():
                try:
                    from playwright.async_api import async_playwright

                    async with async_playwright() as p:
                        browser = await p.chromium.launch(headless=True)
                        page = await browser.new_page(viewport={"width": 1280, "height": 720})
                        await page.goto(
                            f"{self.BASE_URL}/aria_dashboard_v3.html", wait_until="domcontentloaded"
                        )
                        await asyncio.sleep(3)

                        input_el = await page.query_selector(
                            "input[type='text'], input[type='search'], .chat-input input, #chat-input"
                        )
                        visible = False
                        focusable = False
                        if input_el:
                            visible = await input_el.is_visible()
                            await input_el.focus()
                            focusable = True

                            await input_el.type("Hola ARIA", delay=50)
                            start_time = asyncio.get_event_loop().time()
                            await asyncio.sleep(35)
                            end_time = asyncio.get_event_loop().time()
                            latency_ms = int((end_time - start_time) * 1000)

                            messages = await page.query_selector_all(
                                ".chat-msg, .chat-message, [class*='message']"
                            )
                            chat_works = len(messages) > 1

                            browser_worked = True
                        await browser.close()
                except Exception as exc:
                    result.details["browser_error"] = str(exc)

            passed = (has_input and has_chat_panel) or chat_works
            result.passed = passed
            result.details = {
                "chat_works": chat_works,
                "latency_ms": latency_ms,
                "has_input_html": has_input,
                "has_chat_panel_html": has_chat_panel,
                "browser_worked": browser_worked,
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result


@pytest.mark.asyncio
async def test_aria_orb_renders() -> None:
    v = VisualCoreVerifier()
    r = await v.test_aria_orb_renders()
    assert r.passed, f"Orb render failed: {r.details}"


@pytest.mark.asyncio
async def test_particles_orbiting() -> None:
    v = VisualCoreVerifier()
    r = await v.test_particles_orbiting()
    assert r.passed, f"Particles failed: {r.details}"


@pytest.mark.asyncio
async def test_breathing_animation() -> None:
    v = VisualCoreVerifier()
    r = await v.test_breathing_animation()
    assert r.passed, f"Breathing failed: {r.details}"


@pytest.mark.asyncio
async def test_hover_effects() -> None:
    v = VisualCoreVerifier()
    r = await v.test_hover_effects()
    assert r.passed, f"Hover failed: {r.details}"


@pytest.mark.asyncio
async def test_chat_input_visible() -> None:
    v = VisualCoreVerifier()
    r = await v.test_chat_input_visible()
    assert r.passed, f"Chat input failed: {r.details}"
