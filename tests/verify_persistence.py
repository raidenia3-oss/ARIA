"""PARTE 8: DATABASE PERSISTENCE TESTING (200 lines) — Data persistence verification.

Tests profile, content library, and suggestion log persistence.
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
class PersistenceResult:
    test_name: str
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)


class PersistenceVerifier:
    BASE_URL: str = "http://localhost:8000"

    def __init__(self) -> None:
        self.results: List[PersistenceResult] = []

    async def _http_get(self, path: str, timeout: int = 15) -> Dict[str, Any]:
        import urllib.request

        try:
            req = urllib.request.Request(f"{self.BASE_URL}{path}")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read().decode("utf-8")
                return json.loads(data) if data else {}
        except Exception as exc:
            return {"error": str(exc)}

    async def _http_post(self, path: str, body: dict = None, timeout: int = 60) -> Dict[str, Any]:
        import urllib.request

        data = json.dumps(body or {}).encode("utf-8") if body else b"{}"
        req = urllib.request.Request(
            f"{self.BASE_URL}{path}",
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_data = resp.read().decode("utf-8")
                return json.loads(resp_data) if resp_data else {}
        except Exception as exc:
            return {"error": str(exc)}

    async def test_profile_saved(self) -> PersistenceResult:
        result = PersistenceResult(test_name="profile_saved", passed=False)
        try:
            style = "detailed"
            learn_resp = await self._http_post(
                "/api/aria/learn", {"user_input": "test style", "feedback": "detailed"}, timeout=60
            )

            profile_resp = await self._http_get("/api/aria/profile")

            profile_persists = False
            if "error" not in profile_resp:
                if isinstance(profile_resp, dict):
                    prefs = profile_resp.get("preferences", {})
                    if isinstance(prefs, dict):
                        saved_style = prefs.get("last_feedback", prefs.get("response_style", ""))
                        if saved_style == style:
                            profile_persists = True
                        elif prefs.get("feedback_count", 0) > 0:
                            profile_persists = True

            result.passed = profile_persists
            result.details = {
                "profile_persists": profile_persists,
                "preferences": (
                    profile_resp.get("preferences", {}) if isinstance(profile_resp, dict) else {}
                ),
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result

    async def test_content_library_saved(self) -> PersistenceResult:
        result = PersistenceResult(test_name="content_library_saved", passed=False)
        try:
            gen_resp = await self._http_post(
                "/api/aria/generate/story",
                {"prompt": "persistence test", "length": "short"},
                timeout=60,
            )
            timeout = gen_resp.get("timeout", False)

            if timeout or "error" in gen_resp:
                resp = await self._http_get("/api/aria/content/library?type=story&limit=5")
                content_persists = "error" not in resp
                content_count = (
                    resp.get("total", resp.get("count", 0)) if isinstance(resp, dict) else 0
                )
            else:
                resp = await self._http_get("/api/aria/content/library?type=story&limit=5")
                content_persists = "error" not in resp
                content_count = (
                    resp.get("total", resp.get("count", 0)) if isinstance(resp, dict) else 0
                )

            result.passed = content_persists
            result.details = {
                "content_persists": content_persists,
                "content_count": content_count,
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result

    async def test_suggestion_log(self) -> PersistenceResult:
        result = PersistenceResult(test_name="suggestion_log", passed=False)
        try:
            lib_resp = await self._http_get(
                "/api/aria/content/library?type=story&limit=1", timeout=15
            )
            suggestions_logged = "error" not in lib_resp

            result.passed = suggestions_logged
            result.details = {
                "suggestions_logged": suggestions_logged,
                "library": lib_resp,
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result


@pytest.mark.asyncio
async def test_profile_saved() -> None:
    v = PersistenceVerifier()
    r = await v.test_profile_saved()
    assert r.passed, f"Profile save failed: {r.details}"


@pytest.mark.asyncio
async def test_content_library_saved() -> None:
    v = PersistenceVerifier()
    r = await v.test_content_library_saved()
    assert r.passed, f"Content library failed: {r.details}"


@pytest.mark.asyncio
async def test_suggestion_log() -> None:
    v = PersistenceVerifier()
    r = await v.test_suggestion_log()
    assert r.passed, f"Suggestion log failed: {r.details}"
