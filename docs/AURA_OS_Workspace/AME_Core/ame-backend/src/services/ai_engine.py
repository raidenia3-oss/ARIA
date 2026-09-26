"""
AURA AI Engine
Servicio unificado para orquestar múltiples proveedores de IA.
"""

from __future__ import annotations

import json
import os
import re
import requests
import time
from typing import Any, Dict, Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_SYSTEM_INTENT_CONTEXT = (
    "You are an intent parser for AURA. If the user asks to start or run any monetization bot, "
    "reply ONLY with a JSON object like: "
    '{"action": "START_BOT", "target": "<target>"} . '
    "Valid targets: surveys. "
    "For any other message, reply normally as AURA assistant."
)


class AIEngine:
    def __init__(self) -> None:
        self.providers = {
            "gemini": {
                "url": os.getenv(
                    "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
                ),
                "model": os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp"),
                "api_key": os.getenv("GEMINI_API_KEY"),
                "timeout": int(os.getenv("GEMINI_TIMEOUT", "30")),
            },
            "groq": {
                "url": "https://api.groq.com/openai/v1",
                "model": "llama-3.3-70b-versatile",
                "api_key": os.getenv("GROQ_API_KEY"),
                "timeout": int(os.getenv("GROQ_TIMEOUT", "30")),
            },
            "openrouter": {
                "url": os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
                "model": os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3-8b-instruct:free"),
                "api_key": os.getenv("OPENROUTER_API_KEY"),
                "timeout": int(os.getenv("OPENROUTER_TIMEOUT", "30")),
            },
            "lm_studio": {
                "url": os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1"),
                "model": os.getenv("LM_STUDIO_MODEL", "gemma-2-2b-it"),
                "api_key": None,
                "timeout": int(os.getenv("LM_STUDIO_TIMEOUT", "60")),
            },
        }
        self.preference = os.getenv(
            "AI_PROVIDER_PREFERENCE", "auto"
        )  # auto | gemini | groq | openrouter | lm_studio
        self.session = self._build_session()
        self._intent_pattern = re.compile(
            r"(?:inicia|arranca|empieza|start|run|activa)\s+(?:el\s+)?(?:bot\s+)?(?:de\s+)?(?:las\s+)?(?:encuestas|survey|granja|farm)",
            re.IGNORECASE,
        )

    def _build_session(self) -> requests.Session:
        s = requests.Session()
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 502, 503, 504])
        s.mount("https://", HTTPAdapter(max_retries=retries))
        s.mount("http://", HTTPAdapter(max_retries=retries))
        return s

    def _headers(self, provider: str) -> Dict[str, str]:
        key = self.providers[provider]["api_key"]
        h = {"Content-Type": "application/json"}
        if provider == "lm_studio":
            return h
        if key:
            h["Authorization"] = f"Bearer {key}"
        if provider == "openrouter":
            h["HTTP-Referer"] = "https://ame-backend.local"
            h["X-Title"] = "AURA Backend"
        return h

    def chat(
        self,
        prompt: str,
        context: Optional[str] = None,
        model_override: Optional[str] = None,
        provider_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        intent_json = self._try_intent_command(prompt)
        if intent_json is not None:
            return {
                "text": json.dumps(intent_json),
                "intent": intent_json,
                "provider": "local_parser",
            }
        return self._chat_ai(
            prompt=prompt,
            context=context,
            model_override=model_override,
            provider_override=provider_override,
        )

    def _try_intent_command(self, prompt: str) -> Optional[Dict[str, Any]]:
        if not self._intent_pattern.search(prompt or ""):
            return None
        return {"action": "START_BOT", "target": "surveys"}

    def _chat_ai(
        self,
        prompt: str,
        context: Optional[str] = None,
        model_override: Optional[str] = None,
        provider_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        effective_context = _SYSTEM_INTENT_CONTEXT
        if context:
            effective_context = f"{context}\n\n{_SYSTEM_INTENT_CONTEXT}"
        providers = self._resolve_providers(provider_override)
        last_error: Optional[Exception] = None
        for provider in providers:
            try:
                return self._call_provider(
                    provider,
                    prompt,
                    effective_context,
                    model_override,
                )
            except Exception as e:
                last_error = e
        return {
            "text": f"AI error: {last_error}",
            "error": str(last_error) if last_error else "Unknown error",
            "provider": "none",
        }

    def _resolve_providers(self, override: Optional[str]) -> list:
        if override and override in self.providers:
            return [override]
        if self.preference != "auto":
            if self.preference in self.providers:
                return [self.preference] + [p for p in self.providers if p != self.preference]
        return list(self.providers.keys())

    def _call_provider(
        self,
        provider: str,
        prompt: str,
        context: Optional[str],
        model_override: Optional[str],
    ) -> Dict[str, Any]:
        cfg = self.providers[provider]
        if provider == "gemini":
            return self._call_openai_compat(
                f"{cfg['url']}/models/{model_override or cfg['model']}:generateContent?key={cfg['api_key']}",
                {"contents": self._contents(prompt, context)},
            )
        if provider in ("groq", "openrouter", "lm_studio"):
            return self._call_openai_compat(
                f"{cfg['url']}/chat/completions",
                {
                    "model": model_override or cfg["model"],
                    "messages": self._messages(prompt, context),
                    "temperature": 0.7,
                    "max_tokens": 2048,
                    "stream": False,
                },
            )
        raise ValueError(f"Unknown provider: {provider}")

    def _call_openai_compat(self, url: str, payload: dict) -> Dict[str, Any]:
        r = self.session.post(url, json=payload, headers=self._headers_for_url(url), timeout=30)
        r.raise_for_status()
        data = r.json()
        candidates = data.get("candidates") or data.get("choices") or []
        if not candidates:
            return {"text": "", "raw": data}
        if "content" in candidates[0]:
            text = candidates[0]["content"].get("parts", [{}])[0].get("text", "")
        else:
            text = candidates[0].get("message", {}).get("content", "")
        return {"text": text, "raw": data}

    def _headers_for_url(self, url: str) -> dict:
        if "/generateContent" in url:
            return {"Content-Type": "application/json"}
        if "lm_studio" in url or "localhost" in url or "127.0.0.1" in url:
            return {"Content-Type": "application/json"}
        return self._headers("openrouter")

    def _contents(self, prompt: str, context: Optional[str]) -> list:
        parts = []
        if context:
            parts.append({"text": context})
        parts.append({"text": prompt})
        return [{"parts": parts}]

    def _messages(self, prompt: str, context: Optional[str]) -> list:
        msgs = []
        if context:
            msgs.append({"role": "system", "content": context})
        msgs.append({"role": "user", "content": prompt})
        return msgs

    def health_check(self) -> Dict[str, Any]:
        status = {}
        for name, cfg in self.providers.items():
            try:
                start = time.time()
                if name == "lm_studio":
                    url = cfg["url"].rstrip("/") + "/models"
                else:
                    url = cfg["url"].rstrip("/")
                r = self.session.get(url, timeout=5)
                ok = r.status_code < 400
                status[name] = {
                    "ok": ok,
                    "latency_ms": round((time.time() - start) * 1000),
                    "status": r.status_code,
                }
            except Exception as e:
                status[name] = {"ok": False, "error": str(e)}
        return status
