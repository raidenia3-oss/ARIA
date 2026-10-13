from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests
from jsonschema import Draft202012Validator, ValidationError


@dataclass
class LLMResponse:
    content: str
    raw: Dict[str, Any]
    tokens: int
    latency_ms: int


class LLMLocalClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11500",
        timeout: int = 300,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()

    def health(self) -> bool:
        try:
            r = self._session.get(f"{self.base_url}/health", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def wait_ready(self, max_wait: int = 180, interval: float = 0.3) -> bool:
        deadline = time.time() + max_wait
        while time.time() < deadline:
            if self.health():
                return True
            time.sleep(interval)
        return False

    def complete(
        self,
        prompt: str,
        schema: Optional[Dict[str, Any]] = None,
        n_predict: int = 256,
        temperature: float = 0.7,
        stop: Optional[list] = None,
    ) -> LLMResponse:
        payload = {
            "prompt": prompt,
            "n_predict": n_predict,
            "temperature": temperature,
        }
        if stop:
            payload["stop"] = stop
        if schema:
            payload["json_schema"] = schema

        start = time.perf_counter()
        try:
            r = self._session.post(
                f"{self.base_url}/completion",
                json=payload,
                timeout=self.timeout,
            )
            r.raise_for_status()
        except Exception as e:
            raise RuntimeError(f"llama-server request failed: {e}")
        latency_ms = int((time.perf_counter() - start) * 1000)

        data = r.json()
        content = data.get("content", "")

        if schema:
            content = self._validate_json(content, schema)

        tokens = data.get("tokens_predicted", 0)
        return LLMResponse(content=content, raw=data, tokens=tokens, latency_ms=latency_ms)

    def _validate_json(self, content: str, schema: Dict[str, Any]) -> str:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"respuesta no es JSON válido: {e}")

        validator = Draft202012Validator(schema)
        try:
            validator.validate(parsed)
        except ValidationError as e:
            raise ValueError(f"JSON no cumple schema: {e.message}")

        return json.dumps(parsed, ensure_ascii=False)


def create_client(base_url: str = "http://127.0.0.1:11500") -> LLMLocalClient:
    return LLMLocalClient(base_url)