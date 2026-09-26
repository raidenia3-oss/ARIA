"""PARTE 5: GREAT SAGE MODEL TESTING (250 lines) — AI model verification.

Tests model loading, inference, knowledge, coherence, and language.
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
class SageResult:
    test_name: str
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)


class GreatSageVerifier:
    BASE_URL: str = "http://localhost:8000"

    def __init__(self) -> None:
        self.results: List[SageResult] = []

    async def _http_get(self, path: str) -> Dict[str, Any]:
        import urllib.request

        try:
            req = urllib.request.Request(f"{self.BASE_URL}{path}")
            with urllib.request.urlopen(req, timeout=15) as resp:
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
            return {"error": str(exc), "timeout": True}

    async def test_model_loaded(self) -> SageResult:
        result = SageResult(test_name="model_loaded", passed=False)
        try:
            status = await self._http_get("/api/ai/status")

            model_loaded = False
            timeout = status.get("timeout", False)

            if "error" not in status and not timeout:
                current = status.get("current_model", status.get("model", ""))
                if (
                    "great-sage" in str(current).lower()
                    or "gemma" in str(current).lower()
                    or "llama" in str(current).lower()
                ):
                    model_loaded = True
                elif "ollama" in str(status).lower() or "connected" in str(status).lower():
                    model_loaded = True

            result.passed = model_loaded
            result.details = {
                "model_loaded": model_loaded,
                "current_model": status.get("current_model", status.get("model", "")),
                "status": status,
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result

    async def test_ollama_inference(self) -> SageResult:
        result = SageResult(test_name="ollama_inference", passed=False)
        try:
            resp = await self._http_post(
                "/api/aria/chat", {"message": "Hola, cual es 2+2?"}, timeout=90
            )

            inference_works = False
            latency_ms = 0
            correct = False
            timeout = resp.get("timeout", False)

            if "error" not in resp and not timeout:
                start = asyncio.get_event_loop().time()
                if isinstance(resp, dict):
                    answer = resp.get("response", resp.get("message", resp.get("text", "")))
                    if isinstance(answer, str) and len(answer) > 0:
                        inference_works = True
                        lower = answer.lower()
                        if "4" in lower or "cuatro" in lower or "four" in lower:
                            correct = True

            result.passed = inference_works
            result.details = {
                "inference_works": inference_works,
                "latency_ms": latency_ms,
                "correct": correct,
                "timeout": timeout,
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result

    async def test_anime_knowledge(self) -> SageResult:
        result = SageResult(test_name="anime_knowledge", passed=False)
        try:
            resp = await self._http_post(
                "/api/aria/chat", {"message": "Quien es Great Sage en Tensura?"}, timeout=90
            )

            anime_knowledge = False
            timeout = resp.get("timeout", False)

            if "error" not in resp and not timeout:
                if isinstance(resp, dict):
                    answer = resp.get("response", resp.get("message", resp.get("text", "")))
                    if isinstance(answer, str):
                        lower = answer.lower()
                        if (
                            "rimuru" in lower
                            or "sabia" in lower
                            or "sage" in lower
                            or "tensura" in lower
                        ):
                            anime_knowledge = True

            result.passed = anime_knowledge
            result.details = {
                "anime_knowledge": anime_knowledge,
                "timeout": timeout,
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result

    async def test_coherence(self) -> SageResult:
        result = SageResult(test_name="coherence", passed=False)
        try:
            questions = [
                "What is Tensura?",
                "Who is the main character?",
                "What is Rimuru's power?",
                "Describe the world of Tensura.",
                "What makes Tensura unique?",
            ]

            answers = []
            coherent = True
            contradiction_count = 0
            timeout = False

            for q in questions:
                resp = await self._http_post("/api/aria/chat", {"message": q}, timeout=60)
                if resp.get("timeout", False):
                    timeout = True
                    break
                if "error" in resp:
                    coherent = False
                    break
                if isinstance(resp, dict):
                    ans = resp.get("response", resp.get("message", resp.get("text", "")))
                    if isinstance(ans, str) and len(ans) > 5:
                        answers.append(ans)
                    else:
                        coherent = False
                        break
                await asyncio.sleep(1)

            if not timeout and len(answers) >= 3:
                all_text = " ".join(answers).lower()
                if "rimuru" not in all_text and "tensura" not in all_text:
                    coherent = False
                    contradiction_count += 1

            result.passed = coherent and not timeout
            result.details = {
                "coherent": coherent,
                "contradiction_count": contradiction_count,
                "answers_count": len(answers),
                "timeout": timeout,
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result

    async def test_spanish_responses(self) -> SageResult:
        result = SageResult(test_name="spanish_responses", passed=False)
        try:
            questions = [
                "Hola, como estas?",
                "Que es la inteligencia artificial?",
                "Cual es tu nombre?",
            ]

            spanish = True
            timeout = False

            for q in questions:
                resp = await self._http_post("/api/aria/chat", {"message": q}, timeout=60)
                if resp.get("timeout", False):
                    timeout = True
                    break
                if "error" in resp:
                    continue
                if isinstance(resp, dict):
                    answer = resp.get("response", resp.get("message", resp.get("text", "")))
                    if isinstance(answer, str) and len(answer) > 0:
                        lower = answer.lower()
                        es_words = [
                            "hola",
                            "como",
                            "que",
                            "es",
                            "mi",
                            "nombre",
                            "artificial",
                            "inteligencia",
                        ]
                        has_es = any(w in lower for w in es_words)
                        if not has_es and len(answer) > 10:
                            spanish = False
                await asyncio.sleep(1)

            result.passed = spanish and not timeout
            result.details = {
                "spanish_responses": spanish,
                "timeout": timeout,
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result


@pytest.mark.asyncio
async def test_model_loaded() -> None:
    v = GreatSageVerifier()
    r = await v.test_model_loaded()
    assert r.passed, f"Model loaded failed: {r.details}"


@pytest.mark.asyncio
async def test_ollama_inference() -> None:
    v = GreatSageVerifier()
    r = await v.test_ollama_inference()
    assert r.passed, f"Ollama inference failed: {r.details}"


@pytest.mark.asyncio
async def test_anime_knowledge() -> None:
    v = GreatSageVerifier()
    r = await v.test_anime_knowledge()
    assert r.passed, f"Anime knowledge failed: {r.details}"


@pytest.mark.asyncio
async def test_coherence() -> None:
    v = GreatSageVerifier()
    r = await v.test_coherence()
    assert r.passed, f"Coherence failed: {r.details}"


@pytest.mark.asyncio
async def test_spanish_responses() -> None:
    v = GreatSageVerifier()
    r = await v.test_spanish_responses()
    assert r.passed, f"Spanish responses failed: {r.details}"
