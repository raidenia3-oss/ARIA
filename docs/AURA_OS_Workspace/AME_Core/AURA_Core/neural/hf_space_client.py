# AURA_Core/neural/hf_space_client.py
# Cliente HF Space compatible con API OpenAI para usar como LLM real en healer / chat.

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional


class HFSpaceClient:
    """Cliente HTTP para un Hugging Face Space que exponha una API tipo OpenAI."""

    def __init__(
        self, base_url: Optional[str] = None, api_key: Optional[str] = None, timeout: int = 60
    ):
        self.base_url = (base_url or os.environ.get("HF_SPACE_URL", "")).rstrip("/")
        self.api_key = (
            api_key or os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_API_KEY")
        )
        self.timeout = timeout

    def chat(
        self, system_prompt: str, user_prompt: str, temperature: float = 0.0, max_tokens: int = 256
    ) -> str:
        try:
            import requests  # lazy import para no forzar dependencia global innecesaria

            chat_endpoint = f"{self.base_url}/v1/chat/completions"
            payload = {
                "model": "default",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            r = requests.post(chat_endpoint, headers=headers, json=payload, timeout=self.timeout)
            r.raise_for_status()
            data = r.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
        except Exception as e:
            raise RuntimeError(f"Error llamando a HF Space: {e}") from e


hf_client = HFSpaceClient()
