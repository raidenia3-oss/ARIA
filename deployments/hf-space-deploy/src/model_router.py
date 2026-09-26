"""
AURA Model Router — Domain-aware routing with fallback and cache.
CPU-safe for Hugging Face Spaces free tier.
"""

import os
import hashlib
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

logger = logging.getLogger("AURA.Router")

MAX_HISTORY = 10

CODE_KEYWORDS = [
    "code", "python", "javascript", "typescript", "function", "class",
    "def ", "import ", "const ", "let ", "var ", "print(", "return",
    "implement", "algorithm", "bug", "debug", "error", "exception",
    "api", "endpoint", "route", "database", "sql", "query", "docker",
    "git", "commit", "push", "deploy", "test", "unit test",
]
MATH_KEYWORDS = [
    "math", "equation", "calculate", "solve", "derivative", "integral",
    "algebra", "geometry", "statistics", "probability", "matrix",
    "linear", "quadratic", "polynomial", "function f(", "summation",
]
CREATIVE_KEYWORDS = [
    "write", "story", "poem", "essay", "creative", "imagine",
    "describe", "narrate", "fiction", "fantasy", "character",
    "plot", "dialogue", "metaphor", "lyrics", "song",
]
ANALYSIS_KEYWORDS = [
    "analyze", "explain", "compare", "contrast", "summarize",
    "evaluate", "interpret", "why", "how does", "what is the",
    "difference between", "pros and cons", "advantages",
]


class ResponseCache:
    def __init__(self, max_size: int = 100, ttl_minutes: int = 30):
        self.max_size = max_size
        self.ttl = timedelta(minutes=ttl_minutes)
        self._cache: Dict[str, Dict[str, Any]] = {}

    def _make_key(self, prompt: str, model: str) -> str:
        raw = f"{prompt.strip().lower()}|{model}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, prompt: str, model: str) -> Optional[str]:
        key = self._make_key(prompt, model)
        entry = self._cache.get(key)
        if entry is None:
            return None
        if datetime.now() - entry["ts"] > self.ttl:
            del self._cache[key]
            return None
        return entry["response"]

    def set(self, prompt: str, model: str, response: str) -> None:
        key = self._make_key(prompt, model)
        if len(self._cache) >= self.max_size:
            oldest = min(self._cache.keys(), key=lambda k: self._cache[k]["ts"])
            del self._cache[oldest]
        self._cache[key] = {"response": response, "ts": datetime.now()}

    def clear(self) -> None:
        self._cache.clear()


class ModelRouter:
    def __init__(
        self,
        primary_model: str = "microsoft/Phi-3-mini-4k-instruct",
        fallback_model: str = "microsoft/Phi-3-mini-4k-instruct",
        hf_token: Optional[str] = None,
        use_cache: bool = True,
    ):
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.hf_token = hf_token or os.getenv("HF_TOKEN", "")
        self.cache = ResponseCache() if use_cache else None
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from huggingface_hub import InferenceClient
            self._client = InferenceClient(token=self.hf_token)
        return self._client

    def classify_domain(self, prompt: str) -> str:
        lower = prompt.lower()
        scores = {
            "code": sum(1 for kw in CODE_KEYWORDS if kw in lower),
            "math": sum(1 for kw in MATH_KEYWORDS if kw in lower),
            "creative": sum(1 for kw in CREATIVE_KEYWORDS if kw in lower),
            "analysis": sum(1 for kw in ANALYSIS_KEYWORDS if kw in lower),
        }
        if len(prompt.split()) < 3:
            return "conversation"
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "conversation"

    def select_model(self, domain: str) -> str:
        return self.primary_model

    def query(
        self,
        prompt: str,
        system_prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        history: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        domain = self.classify_domain(prompt)
        model = self.primary_model

        if self.cache:
            cached = self.cache.get(prompt, model)
            if cached:
                return {
                    "response": cached,
                    "model_used": model,
                    "domain": domain,
                    "cached": True,
                    "error": None,
                }

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            for msg in history[-MAX_HISTORY:]:
                messages.append(msg)
        messages.append({"role": "user", "content": prompt})

        try:
            result = self._query_model(model, messages, max_tokens, temperature)
            if self.cache:
                self.cache.set(prompt, model, result)
            return {
                "response": result,
                "model_used": model,
                "domain": domain,
                "cached": False,
                "error": None,
            }
        except Exception as exc:
            logger.warning("Primary model failed: %s", exc)

        try:
            result = self._query_model(model, messages, max_tokens, temperature)
            return {
                "response": result,
                "model_used": model,
                "domain": domain,
                "cached": False,
                "error": None,
            }
        except Exception as exc:
            logger.error("All models failed: %s", exc)
            return {
                "response": None,
                "model_used": None,
                "domain": domain,
                "cached": False,
                "error": str(exc),
            }

    def _query_model(self, model_id: str, messages: List[Dict], max_tokens: int, temperature: float) -> str:
        result = self.client.chat_completion(
            model=model_id,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return result.choices[0].message.content.strip()

    def health_check(self) -> Dict[str, Any]:
        try:
            test = self.client.chat_completion(
                model=self.primary_model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            primary_ok = bool(test.choices)
        except Exception:
            primary_ok = False

        return {
            "status": "ok" if primary_ok else "degraded",
            "primary_model": self.primary_model,
            "primary_online": primary_ok,
            "fallback_model": self.fallback_model,
            "cache_size": len(self.cache._cache) if self.cache else 0,
        }
