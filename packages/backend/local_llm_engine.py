"""Offline local LLM engine for AURA - Module 27.

Inferencia 100% offline con modelos locales (Llama, DeepSeek, Gemma,
Mistral), fallback automatico entre modelos y gestion de contexto local.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests as _requests


LOCAL_MODELS: Dict[str, Dict[str, str]] = {
    "llama": {"primary": "llama3.2:latest", "fallback": "llama3.1:latest"},
    "deepseek": {"primary": "deepseek-coder:latest", "fallback": "deepseek-r1:latest"},
    "gemma": {"primary": "gemma2:latest", "fallback": "gemma:latest"},
    "mistral": {"primary": "mistral:latest", "fallback": "mixtral:latest"},
    "mixtral": {"primary": "mixtral:latest", "fallback": "mistral:latest"},
}

DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_GGUF_DIR = os.getenv("AURA_GGUF_DIR", os.path.join(os.getcwd(), "models"))


@dataclass
class LocalModel:
    name: str
    size_mb: float
    format: str
    family: str
    source: str
    available: bool


@dataclass
class ChatMessage:
    role: str
    content: str

    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class ChatResponse:
    model: str
    message: Dict[str, Any]
    done: bool
    total_duration: int
    eval_count: int
    eval_duration: int
    raw: Dict[str, Any]


class OllamaBridge:
    """Puente al API de Ollama para inferencia local 100% offline."""

    def __init__(self, base_url: str = DEFAULT_OLLAMA_URL, timeout: int = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def is_available(self) -> bool:
        try:
            resp = _requests.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self) -> List[Dict[str, Any]]:
        try:
            resp = _requests.get(f"{self.base_url}/api/tags", timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json().get("models", [])
        except Exception:
            pass
        return []

    def pull_model(self, model_name: str) -> Dict[str, Any]:
        try:
            resp = _requests.post(
                f"{self.base_url}/api/pull",
                json={"name": model_name, "stream": False},
                timeout=self.timeout * 10,
            )
            return {"status_code": resp.status_code, "response": resp.json()}
        except Exception as exc:
            return {"status_code": 0, "error": str(exc)}

    def delete_model(self, model_name: str) -> bool:
        try:
            resp = _requests.delete(
                f"{self.base_url}/api/delete",
                json={"name": model_name},
                timeout=self.timeout,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def chat(
        self,
        model_name: str,
        messages: List[Dict[str, Any]],
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        resp = _requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": model_name,
                "messages": messages,
                "stream": stream,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def generate(
        self,
        model_name: str,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        resp = _requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": model_name,
                "prompt": prompt,
                "system": system,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()


class LocalModelRunner:
    """Ejecutor de inferencia local con gestion de contexto y truncation."""

    def __init__(self, ollama_bridge: OllamaBridge, context_window: int = 4096) -> None:
        self.ollama = ollama_bridge
        self.context_window = context_window
        self.context_tokens = 0
        self.history: List[Dict[str, Any]] = []

    @staticmethod
    def estimate_tokens(text: str) -> int:
        return max(1, len(text) // 4)

    def _can_fit(self, messages: List[Dict[str, Any]]) -> bool:
        needed = sum(self.estimate_tokens(m.get("content", "")) for m in messages)
        return needed <= self.context_window

    def trim_context(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self._can_fit(messages):
            return list(messages)
        trimmed = list(messages)
        while trimmed and not self._can_fit(trimmed[1:]):
            trimmed.pop(1)
        return trimmed

    async def run_chat(
        self,
        model_name: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        trimmed = self.trim_context(messages)
        self.context_tokens += sum(self.estimate_tokens(m.get("content", "")) for m in trimmed)
        return self.ollama.chat(model_name, trimmed, temperature=temperature, max_tokens=max_tokens)

    def context_info(self) -> Dict[str, Any]:
        return {
            "context_window": self.context_window,
            "used_tokens": self.context_tokens,
            "remaining_tokens": max(0, self.context_window - self.context_tokens),
            "history_count": len(self.history),
        }


class GGUFModelManager:
    """Gestor de archivos de modelo GGUF en disco local."""

    def __init__(self, gguf_dir: str = DEFAULT_GGUF_DIR) -> None:
        self.gguf_dir = gguf_dir
        self.loaded_models: Dict[str, Dict[str, Any]] = {}

    def list_models(self) -> List[Dict[str, Any]]:
        if not os.path.isdir(self.gguf_dir):
            return []
        models: List[Dict[str, Any]] = []
        for filename in sorted(os.listdir(self.gguf_dir)):
            if filename.endswith(".gguf"):
                filepath = os.path.join(self.gguf_dir, filename)
                size_bytes = os.path.getsize(filepath)
                models.append({
                    "name": filename,
                    "path": filepath,
                    "size_mb": round(size_bytes / (1024 * 1024), 1),
                    "family": self._infer_family(filename),
                    "source": "gguf",
                })
        return models

    def load_model(self, path: str) -> Dict[str, Any]:
        if not os.path.exists(path):
            return {"status": "error", "error": "file_not_found"}
        name = os.path.basename(path)
        try:
            import llama_cpp
            llm = llama_cpp.Llama(model_path=path)
            self.loaded_models[name] = {
                "path": path,
                "loaded_at": datetime.utcnow().isoformat() + "Z",
                "n_ctx": getattr(llm, "n_ctx", 2048),
            }
            return {"status": "loaded", "name": name, "path": path}
        except ImportError:
            self.loaded_models[name] = {
                "path": path,
                "loaded_at": datetime.utcnow().isoformat() + "Z",
                "placeholder": True,
            }
            return {"status": "registered", "name": name, "path": path, "note": "llama_cpp not installed"}

    def unload_model(self, name: str) -> bool:
        return self.loaded_models.pop(name, None) is not None

    @staticmethod
    def _infer_family(filename: str) -> str:
        f = filename.lower()
        for family in LOCAL_MODELS:
            if family in f:
                return family
        return "unknown"


class OfflineLLMEngine:
    """Motor de LLM offline con fallback automatico entre modelos."""

    def __init__(self, ollama_url: str = DEFAULT_OLLAMA_URL, gguf_dir: str = DEFAULT_GGUF_DIR) -> None:
        self.ollama = OllamaBridge(base_url=ollama_url)
        self.runner = LocalModelRunner(self.ollama)
        self.gguf_manager = GGUFModelManager(gguf_dir=gguf_dir)
        self._model_aliases = dict(LOCAL_MODELS)

    def get_available_models(self) -> List[Dict[str, Any]]:
        models: List[Dict[str, Any]] = []
        if self.ollama.is_available():
            for m in self.ollama.list_models():
                models.append({
                    "name": m.get("name", ""),
                    "size_mb": round(m.get("size", 0) / (1024 * 1024), 1),
                    "format": "gguf",
                    "family": self._detect_family(m.get("name", "")),
                    "source": "ollama",
                    "available": True,
                })
        models.extend(self.gguf_manager.list_models())
        return models

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        preferred_model: str = "auto",
        fallbacks: Optional[List[str]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        if preferred_model == "auto":
            if self.ollama.is_available():
                ollama_models = self.ollama.list_models()
                if ollama_models:
                    preferred_model = ollama_models[0].get("name", "llama3.2:latest")
                else:
                    preferred_model = "llama3.2:latest"
            else:
                preferred_model = "llama3.2:latest"

        fallback_list = fallbacks or self._get_fallbacks(preferred_model)
        tried: List[str] = []
        last_error = "no backend available"

        for model in [preferred_model] + fallback_list:
            tried.append(model)
            try:
                if self.ollama.is_available():
                    raw = await self.runner.run_chat(model, messages, temperature, max_tokens)
                    return {
                        "model": model,
                        "response": raw,
                        "tried_models": tried,
                        "status": "success",
                    }
                last_error = "ollama not available"
            except Exception as exc:
                last_error = str(exc)
                continue

        return {
            "model": preferred_model,
            "response": None,
            "tried_models": tried,
            "status": "failed",
            "error": last_error,
        }

    def pull_model(self, model_name: str) -> Dict[str, Any]:
        return self.ollama.pull_model(model_name)

    def get_context_info(self) -> Dict[str, Any]:
        return self.runner.context_info()

    def _get_fallbacks(self, model_name: str) -> List[str]:
        family = self._detect_family(model_name)
        config = self._model_aliases.get(family, {})
        fb = config.get("fallback")
        return [fb] if fb else []

    @staticmethod
    def _detect_family(model_name: str) -> str:
        f = model_name.lower()
        for family in LOCAL_MODELS:
            if family in f:
                return family
        return "unknown"
