"""AURA Brain Orchestrator — unifies external APIs + local model + continuous learning.

Architecture:
1. External APIs (Gemini, Groq, OpenRouter) = 'experience' - fast, capable, cloud
2. Small local model (LoRA) = 'reflection' - offline, personal, improves over time
3. Local rules = 'instinct' - instant, no dependencies

Flow:
- Chat -> try external APIs (cached) -> try local model -> fallback rules
- Every good response is captured as training sample
- Auto-train when enough samples collected
- Circuit breaker per provider with 30s cooldown
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional


class BrainOrchestrator:
    def __init__(self, brain: Any = None, brain_api: Any = None, ai_manager: Any = None) -> None:
        self.brain = brain
        self.brain_api = brain_api
        self.ai_manager = ai_manager
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 3600
        self._auto_train_threshold = 50
        self._last_auto_train = 0
        self._train_interval = 3600

    def chat(self, message: str, history: Optional[List[List[str]]] = None) -> Dict[str, Any]:
        start = time.time()
        context = self._build_context(history)
        cache_key = self._get_cache_key(message, context)

        cached = self._get_cached(cache_key)
        if cached:
            return {**cached, "cached": True}

        provider_result = self._try_external_apis(message, context)
        if provider_result:
            self._set_cache(cache_key, provider_result)
            self._capture_training_sample(message, provider_result.get("message", ""), quality="high")
            return provider_result

        local_result = self._try_local_model(message, context)
        if local_result:
            self._set_cache(cache_key, local_result)
            return local_result

        fallback = self._try_fallback(message)
        if fallback:
            self._set_cache(cache_key, fallback)
            self._capture_training_sample(message, fallback.get("message", ""), quality="medium")
            return fallback

        return {"message": "No response available.", "provider": "none", "source": "none"}

    def _build_context(self, history: Optional[List[List[str]]]) -> str:
        if not history:
            return ""
        parts = []
        for h in history[-5:]:
            if h[0]:
                parts.append(f"User: {h[0]}")
            if len(h) > 1 and h[1]:
                parts.append(f"AURA: {h[1]}")
        return "\n".join(parts)

    def _get_cache_key(self, message: str, context: str) -> str:
        return f"{context}:{message.lower().strip()[:100]}"

    def _get_cached(self, key: str) -> Optional[Dict[str, Any]]:
        entry = self._cache.get(key)
        if not entry:
            return None
        if time.time() - entry["timestamp"] > self._cache_ttl:
            del self._cache[key]
            return None
        return entry["response"]

    def _set_cache(self, key: str, response: Dict[str, Any]) -> None:
        self._cache[key] = {
            "response": response,
            "timestamp": time.time(),
        }
        if len(self._cache) > 500:
            oldest = min(self._cache, key=lambda k: self._cache[k]["timestamp"])
            del self._cache[oldest]

    def _try_external_apis(self, message: str, context: str) -> Optional[Dict[str, Any]]:
        if not self.ai_manager or not self.brain_api:
            return None
        best = self.brain_api.get_best_provider()
        if not best:
            return None
        try:
            start = time.time()
            resp = self.ai_manager.chat(message, history=None, provider=best)
            latency = time.time() - start
            text = resp.get("message", "")
            if text and len(text.strip()) > 3:
                self.brain_api.mark_success(best, latency)
                return {
                    "message": text,
                    "provider": best,
                    "latency": round(latency, 2),
                    "source": "external_api",
                }
            self.brain_api.mark_failure(best)
        except Exception:
            if best:
                self.brain_api.mark_failure(best)
        return None

    def _try_local_model(self, message: str, context: str) -> Optional[Dict[str, Any]]:
        if not self.brain or not self.brain.model_loaded:
            return None
        prompt = self._build_prompt(message, context)
        response = self.brain.generate(prompt)
        if response and len(response.strip()) > 3:
            return {
                "message": response,
                "provider": "local_model",
                "latency": 0.0,
                "source": "local_model",
            }
        return None

    def _try_fallback(self, message: str) -> Optional[Dict[str, Any]]:
        if not self.ai_manager:
            return None
        try:
            resp = self.ai_manager.chat(message, history=None)
            text = resp.get("message", "")
            if text and len(text.strip()) > 3:
                return {
                    "message": text,
                    "provider": resp.get("provider", "local"),
                    "latency": resp.get("latency", 0),
                    "source": "fallback",
                }
        except Exception:
            pass
        return None

    def _build_prompt(self, message: str, context: str) -> str:
        system = "Eres AURA, un asistente de IA avanzado. Eres util, conciso y preciso."
        if context:
            prompt = f"{system}\n\nContexto:\n{context}\n\nUser: {message}\nAURA:"
        else:
            prompt = f"{system}\n\nUser: {message}\nAURA:"
        return prompt

    def _capture_training_sample(self, user_msg: str, bot_msg: str, quality: str = "auto") -> None:
        if not self.brain:
            return
        if len(user_msg) < 3 or len(bot_msg) < 5:
            return
        if user_msg.startswith("/"):
            return
        self.brain.add_training_sample(user_msg, bot_msg, quality=quality)

    def get_status(self) -> Dict[str, Any]:
        return {
            "brain": self.brain.get_status() if self.brain else None,
            "api": self.brain_api.get_status() if self.brain_api else None,
            "ai": self.ai_manager.get_provider_health() if self.ai_manager else None,
            "cache_size": len(self._cache),
        }
