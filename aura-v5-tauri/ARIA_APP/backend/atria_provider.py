"""Atria Dawn Provider — connects ARIA OS to Atria Dawn Preview API.

Atria Dawn Preview: 744B MoE agentic model by Shanghai AI Laboratory.
4 capability dimensions: Discovery, Creation, Delivery, Cybersecurity.
Uses OpenAI-compatible Chat Completions API.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional


class AtriaDawnProvider:
    """Provider for Atria Dawn Preview via OpenAI-compatible API."""

    BASE_URL = os.environ.get("ATRIA_API_URL", "https://api.atria-asi.ai/v1")
    MODEL = os.environ.get("ATRIA_MODEL", "Atria-Dawn-Preview")
    SUPPORTED_MODALITIES = ["text"]
    CONTEXT_WINDOW = 256000

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.environ.get("ATRIA_API_KEY", "")
        self.available: bool = bool(self.api_key)
        self.priority: int = 2
        self._latency_history: List[float] = []
        self._failures: int = 0

    def is_available(self) -> bool:
        if not self.available or not self.api_key:
            return False
        if self._failures >= 5 and len(self._latency_history) > 0:
            return False
        return True

    def chat(
        self,
        message: str,
        history: Optional[List[List[str]]] = None,
        system_prompt: str = "",
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        if not self.is_available():
            return {"error": "Atria Dawn not configured. Set ATRIA_API_KEY.", "message": ""}

        start = time.time()
        try:
            import urllib.request

            messages: List[Dict[str, str]] = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            if history:
                for user_msg, assistant_msg in history[-20:]:
                    if user_msg:
                        messages.append({"role": "user", "content": str(user_msg)})
                    if assistant_msg:
                        messages.append({"role": "assistant", "content": str(assistant_msg)})
            messages.append({"role": "user", "content": message})

            body: Dict[str, Any] = {
                "model": self.MODEL,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
            }
            if tools:
                body["tools"] = tools

            data = json.dumps(body).encode()
            req = urllib.request.Request(
                f"{self.BASE_URL}/chat/completions",
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=300) as r:
                result = json.loads(r.read())

            text = ""
            choices = result.get("choices", [])
            if choices:
                text = choices[0].get("message", {}).get("content", "") or ""
                tool_calls = choices[0].get("message", {}).get("tool_calls", [])
            else:
                tool_calls = []

            latency = time.time() - start
            self._latency_history.append(latency)
            if len(self._latency_history) > 50:
                self._latency_history.pop(0)
            self._failures = 0

            return {
                "message": text,
                "provider": "atria_dawn",
                "model": self.MODEL,
                "latency": round(latency, 2),
                "tool_calls": tool_calls,
                "finish_reason": (
                    choices[0].get("finish_reason", "completed") if choices else "completed"
                ),
                "context_used": result.get("usage", {}).get("prompt_tokens", 0),
                "output_tokens": result.get("usage", {}).get("completion_tokens", 0),
            }
        except Exception as exc:
            latency = time.time() - start
            self._latency_history.append(latency)
            self._failures += 1
            return {
                "error": str(exc),
                "message": f"[Atria Dawn error: {exc}]",
                "provider": "atria_dawn",
                "latency": round(latency, 2),
            }

    def chat_stream(
        self,
        message: str,
        history: Optional[List[List[str]]] = None,
        system_prompt: str = "",
    ):
        """Generator for streaming responses from Atria Dawn."""
        if not self.is_available():
            yield "Atria Dawn not configured."
            return

        import urllib.request

        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            for user_msg, assistant_msg in history[-20:]:
                if user_msg:
                    messages.append({"role": "user", "content": str(user_msg)})
                if assistant_msg:
                    messages.append({"role": "assistant", "content": str(assistant_msg)})
        messages.append({"role": "user", "content": message})

        body = json.dumps(
            {
                "model": self.MODEL,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 4096,
                "stream": True,
            }
        ).encode()

        req = urllib.request.Request(
            f"{self.BASE_URL}/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                for line in r:
                    line = line.decode("utf-8", "replace").strip()
                    if not line or not line.startswith("data: "):
                        continue
                    try:
                        chunk = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                        if chunk.get("done"):
                            break
        except Exception as exc:
            yield f"[Stream error: {exc}]"

    def get_health(self) -> Dict[str, Any]:
        avg = (
            sum(self._latency_history) / len(self._latency_history)
            if self._latency_history
            else None
        )
        return {
            "available": self.is_available(),
            "model": self.MODEL,
            "context_window": self.CONTEXT_WINDOW,
            "modalities": self.SUPPORTED_MODALITIES,
            "avg_latency": avg,
            "failures": self._failures,
        }
