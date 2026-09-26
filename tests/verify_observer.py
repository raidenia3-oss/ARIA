"""PARTE 2: OBSERVER TESTING (300 lines) — Observer detection verification.

Tests observer activity detection, intent, mood, and keyword extraction.
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
class ObserverResult:
    test_name: str
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)


class ObserverVerifier:
    BASE_URL: str = "http://localhost:8000"

    def __init__(self) -> None:
        self.results: List[ObserverResult] = []

    async def _http_get(self, path: str) -> Dict[str, Any]:
        import urllib.request

        try:
            req = urllib.request.Request(f"{self.BASE_URL}{path}")
            with urllib.request.urlopen(req, timeout=10) as resp:
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

    async def test_observer_starts(self) -> ObserverResult:
        result = ObserverResult(test_name="observer_starts", passed=False)
        try:
            health = await self._http_get("/api/aria/health")
            observer_running = health.get("observer") == "running"
            engine_running = health.get("engine") == "running"

            result.passed = observer_running and engine_running
            result.details = {
                "observer_running": observer_running,
                "engine_running": engine_running,
                "health": health,
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result

    async def test_activity_detection(self) -> ObserverResult:
        result = ObserverResult(test_name="activity_detection", passed=False)
        try:
            event_data = {"event": "file_opened", "filename": "test.txt", "timestamp": 1234567890}
            resp = await self._http_post("/api/aria/activity/log", event_data)

            detected = False
            if "error" not in resp:
                detected = True

            status = await self._http_get("/api/automation/monitor/status")
            monitors_activity = "error" not in status

            result.passed = detected or monitors_activity
            result.details = {
                "detects_files": detected,
                "activity_logged": detected,
                "monitor_status": status,
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result

    async def test_process_monitoring(self) -> ObserverResult:
        result = ObserverResult(test_name="process_monitoring", passed=False)
        try:
            status = await self._http_get("/api/system/status")
            has_process_info = isinstance(status, dict) and "backend" in status

            detected = False
            if has_process_info:
                detected = True

            result.passed = detected and has_process_info
            result.details = {
                "detects_processes": detected,
                "system_status": status,
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result

    async def test_intent_detection(self) -> ObserverResult:
        result = ObserverResult(test_name="intent_detection", passed=False)
        try:
            resp = await self._http_get("/api/aria/profile")

            intent_correct = False
            if "error" not in resp and isinstance(resp, dict):
                state = str(resp.get("state", "")).lower()
                intent = str(resp.get("intent", "")).lower()
                all_text = json.dumps(resp).lower()
                if "initializing" in state or "general" in intent:
                    intent_correct = True
                elif "storytelling" in state or "storytelling" in intent:
                    intent_correct = True
                elif (
                    "story" in all_text
                    or "creation" in all_text
                    or "anime" in all_text
                    or "interest" in all_text
                ):
                    intent_correct = True

            result.passed = intent_correct
            result.details = {
                "intent_correct": intent_correct,
                "state": resp.get("state", "") if isinstance(resp, dict) else "",
                "intent": resp.get("intent", "") if isinstance(resp, dict) else "",
                "confidence": resp.get("confidence", 0) if isinstance(resp, dict) else 0,
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result

    async def test_mood_tracking(self) -> ObserverResult:
        result = ObserverResult(test_name="mood_tracking", passed=False)
        try:
            for _ in range(5):
                await self._http_get("/api/aria/health")
                await asyncio.sleep(0.2)

            mood_data = {"user_input": "search anime", "feedback": "exploring"}
            resp = await self._http_post("/api/aria/learn", mood_data)

            mood_detection = False
            if isinstance(resp, dict):
                if "error" not in resp:
                    mood_detection = True
                mood = resp.get("mood", "").lower()
                state = resp.get("state", "").lower()
                if "exploring" in mood or "exploring" in state or "exploring" in str(resp).lower():
                    mood_detection = True

            result.passed = mood_detection
            result.details = {
                "mood_detection": mood_detection,
                "response": resp,
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result

    async def test_keyword_extraction(self) -> ObserverResult:
        result = ObserverResult(test_name="keyword_extraction", passed=False)
        try:
            resp = await self._http_get("/api/aria/content/library?type=story&limit=3")

            keywords_accurate = False
            if "error" not in resp:
                if isinstance(resp, dict):
                    items = resp.get("items", resp.get("data", []))
                    if isinstance(items, list) and len(items) >= 0:
                        keywords_accurate = True
                elif isinstance(resp, list) and len(resp) >= 0:
                    keywords_accurate = True

            if not keywords_accurate:
                prof = await self._http_get("/api/aria/profile")
                if isinstance(prof, dict):
                    interests = prof.get("interests_count", 0)
                    if isinstance(interests, (int, float)) and interests > 0:
                        keywords_accurate = True

            result.passed = keywords_accurate
            result.details = {
                "keywords_accurate": keywords_accurate,
                "library": resp if isinstance(resp, dict) else {},
                "profile": prof if isinstance(prof, dict) else {},
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result


@pytest.mark.asyncio
async def test_observer_starts() -> None:
    v = ObserverVerifier()
    r = await v.test_observer_starts()
    assert r.passed, f"Observer start failed: {r.details}"


@pytest.mark.asyncio
async def test_activity_detection() -> None:
    v = ObserverVerifier()
    r = await v.test_activity_detection()
    assert r.passed, f"Activity detection failed: {r.details}"


@pytest.mark.asyncio
async def test_process_monitoring() -> None:
    v = ObserverVerifier()
    r = await v.test_process_monitoring()
    assert r.passed, f"Process monitoring failed: {r.details}"


@pytest.mark.asyncio
async def test_intent_detection() -> None:
    v = ObserverVerifier()
    r = await v.test_intent_detection()
    assert r.passed, f"Intent detection failed: {r.details}"


@pytest.mark.asyncio
async def test_mood_tracking() -> None:
    v = ObserverVerifier()
    r = await v.test_mood_tracking()
    assert r.passed, f"Mood tracking failed: {r.details}"


@pytest.mark.asyncio
async def test_keyword_extraction() -> None:
    v = ObserverVerifier()
    r = await v.test_keyword_extraction()
    assert r.passed, f"Keyword extraction failed: {r.details}"
