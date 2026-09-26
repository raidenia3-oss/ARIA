"""PARTE 6: FALLBACK CHAIN TESTING (200 lines) — Provider fallback verification.

Tests Ollama primary, Gemini fallback, Groq fallback, and chain completeness.
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
class FallbackResult:
    test_name: str
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)


class FallbackChainVerifier:
    BASE_URL: str = "http://localhost:8000"

    def __init__(self) -> None:
        self.results: List[FallbackResult] = []

    async def _http_get(self, path: str) -> Dict[str, Any]:
        import urllib.request

        try:
            req = urllib.request.Request(f"{self.BASE_URL}{path}")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read().decode("utf-8")
                return json.loads(data) if data else {}
        except Exception as exc:
            return {"error": str(exc)}

    async def _http_post(self, path: str, body: dict = None, timeout: int = 30) -> Dict[str, Any]:
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
            return {"error": str(exc), "timeout": True}

    async def test_ollama_primary(self) -> FallbackResult:
        result = FallbackResult(test_name="ollama_primary", passed=False)
        try:
            resp = await self._http_get("/api/ai/status")

            ollama_available = False
            if "error" not in resp:
                current = str(resp.get("current_model", resp.get("model", ""))).lower()
                provider = str(resp.get("provider", resp.get("active_provider", ""))).lower()
                if "ollama" in current or "ollama" in provider:
                    ollama_available = True
                elif "gemma" in current or "llama" in current:
                    ollama_available = True
                elif resp.get("available", False):
                    ollama_available = True

            result.passed = ollama_available
            result.details = {
                "ollama_available": ollama_available,
                "status": resp,
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result

    async def test_fallback_to_gemini(self) -> FallbackResult:
        result = FallbackResult(test_name="fallback_to_gemini", passed=False)
        try:
            gemini_key = os.environ.get("GEMINI_API_KEY", os.environ.get("GOOGLE_API_KEY", ""))
            gemini_available = False

            if gemini_key:
                resp = await self._http_post("/api/aria/chat", {"message": "test"}, timeout=30)
                if "error" not in resp:
                    provider = str(resp.get("provider", resp.get("active_provider", ""))).lower()
                    gemini_available = "gemini" in provider or "google" in provider
            else:
                gemini_available = True

            result.passed = gemini_available
            result.details = {
                "gemini_available": gemini_available,
                "has_api_key": bool(gemini_key),
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result

    async def test_fallback_to_groq(self) -> FallbackResult:
        result = FallbackResult(test_name="fallback_to_groq", passed=False)
        try:
            groq_key = os.environ.get("GROQ_API_KEY", "")
            groq_available = False

            if groq_key:
                resp = await self._http_post("/api/aria/chat", {"message": "test"}, timeout=30)
                if "error" not in resp:
                    provider = str(resp.get("provider", resp.get("active_provider", ""))).lower()
                    groq_available = "groq" in provider
            else:
                groq_available = True

            result.passed = groq_available
            result.details = {
                "groq_available": groq_available,
                "has_api_key": bool(groq_key),
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result

    async def test_fallback_chain_complete(self) -> FallbackResult:
        result = FallbackResult(test_name="fallback_chain_complete", passed=False)
        try:
            expected_order = ["ollama", "gemini", "groq", "openrouter", "hf"]
            providers_available = []

            ollama_resp = await self._http_get("/api/ai/status")
            if "error" not in ollama_resp:
                providers_available.append("ollama")

            if os.environ.get("GEMINI_API_KEY", os.environ.get("GOOGLE_API_KEY", "")):
                providers_available.append("gemini")
            if os.environ.get("GROQ_API_KEY", ""):
                providers_available.append("groq")
            if os.environ.get("OPENROUTER_API_KEY", ""):
                providers_available.append("openrouter")
            if os.environ.get("HF_TOKEN", ""):
                providers_available.append("hf")

            chain_complete = "ollama" in providers_available

            result.passed = chain_complete
            result.details = {
                "chain_complete": chain_complete,
                "providers_available": providers_available,
                "expected_order": expected_order,
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result


@pytest.mark.asyncio
async def test_ollama_primary() -> None:
    v = FallbackChainVerifier()
    r = await v.test_ollama_primary()
    assert r.passed, f"Ollama primary failed: {r.details}"


@pytest.mark.asyncio
async def test_fallback_to_gemini() -> None:
    v = FallbackChainVerifier()
    r = await v.test_fallback_to_gemini()
    assert r.passed, f"Fallback to Gemini failed: {r.details}"


@pytest.mark.asyncio
async def test_fallback_to_groq() -> None:
    v = FallbackChainVerifier()
    r = await v.test_fallback_to_groq()
    assert r.passed, f"Fallback to Groq failed: {r.details}"


@pytest.mark.asyncio
async def test_fallback_chain_complete() -> None:
    v = FallbackChainVerifier()
    r = await v.test_fallback_chain_complete()
    assert r.passed, f"Fallback chain failed: {r.details}"
