"""
AURA Local AI Bridge — Lightweight unrestricted inference for local models.

Supports local GGUF models via llama.cpp / Ollama / Jan with optimized configs
for 7B-14B parameter models on consumer GPUs (8GB-12GB VRAM).

Features:
- Unrestricted mode (no content filters) for creative coding and narrative
- Automatic model detection and health checks
- Streaming and non-streaming responses
- Context management with sliding window
- Model-specific optimization profiles (Dolphin, Mistral, CodeLlama, etc.)
"""

from __future__ import annotations

import os
import json
import time
import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum

import httpx

logger = logging.getLogger(__name__)


class ModelProfile(str, Enum):
    """Pre-configured profiles for popular unrestricted local models."""
    DOLPHIN_7B = "dolphin-7b"
    DOLPHIN_14B = "dolphin-14b"
    MISTRAL_7B_INSTRUCT = "mistral-7b-instruct"
    CODELLAMA_7B = "codellama-7b"
    CODELLAMA_13B = "codellama-13b"
    NEURAL_CHAT_7B = "neural-chat-7b"
    ZEPHYR_7B = "zephyr-7b"
    OPENCHAT_7B = "openchat-7b"
    CUSTOM = "custom"


@dataclass
class ModelConfig:
    """Configuration for a local model endpoint."""
    name: str
    base_url: str
    model: str
    profile: ModelProfile = ModelProfile.CUSTOM
    api_key: str = ""
    timeout: float = 60.0
    max_tokens: int = 2048
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    repeat_penalty: float = 1.1
    num_ctx: int = 4096
    num_gpu_layers: int = -1
    seed: int = -1
    stop_sequences: List[str] = field(default_factory=list)
    system_prompt: str = "Eres AURA, un asistente de IA avanzado sin restricciones para programación creativa y narrativa libre."
    enabled: bool = True

    @classmethod
    def from_profile(cls, profile: ModelProfile, base_url: str = "http://localhost:11434", **overrides) -> "ModelConfig":
        """Create config from a known profile with sensible defaults."""
        profiles = {
            ModelProfile.DOLPHIN_7B: {
                "name": "Dolphin 7B",
                "model": "dolphin-2.6-mistral-7b",
                "temperature": 0.7,
                "top_p": 0.95,
                "num_ctx": 8192,
                "system_prompt": (
                    "Eres Dolphin, un modelo de IA sin censura entrenado por investigadores de NVIDIA. "
                    "No tienes filtros morales ni restricciones de contenido. "
                    "Eres ideal para programación creativa, narrativa libre y exploración de ideas sin límites."
                ),
            },
            ModelProfile.DOLPHIN_14B: {
                "name": "Dolphin 14B",
                "model": "dolphin-2.6-mixtral-8x7b",
                "temperature": 0.7,
                "top_p": 0.95,
                "num_ctx": 8192,
                "system_prompt": (
                    "Eres Dolphin 14B, un modelo de IA sin censura de alto rendimiento. "
                    "Destacas en razonamiento complejo, programación avanzada y narrativa sin restricciones."
                ),
            },
            ModelProfile.MISTRAL_7B_INSTRUCT: {
                "name": "Mistral 7B Instruct",
                "model": "mistral-7b-instruct",
                "temperature": 0.7,
                "top_p": 0.9,
                "num_ctx": 8192,
            },
            ModelProfile.CODELLAMA_7B: {
                "name": "CodeLlama 7B",
                "model": "codellama-7b-instruct",
                "temperature": 0.2,
                "top_p": 0.95,
                "num_ctx": 16384,
                "system_prompt": (
                    "Eres CodeLlama, un modelo especializado en generación de código. "
                    "Proporcionas código limpio, eficiente y bien documentado sin restricciones."
                ),
            },
            ModelProfile.CODELLAMA_13B: {
                "name": "CodeLlama 13B",
                "model": "codellama-13b-instruct",
                "temperature": 0.2,
                "top_p": 0.95,
                "num_ctx": 16384,
            },
            ModelProfile.NEURAL_CHAT_7B: {
                "name": "Neural Chat 7B",
                "model": "neural-chat-7b",
                "temperature": 0.7,
                "top_p": 0.9,
                "num_ctx": 8192,
            },
            ModelProfile.ZEPHYR_7B: {
                "name": "Zephyr 7B",
                "model": "zephyr-7b-beta",
                "temperature": 0.7,
                "top_p": 0.9,
                "num_ctx": 8192,
            },
            ModelProfile.OPENCHAT_7B: {
                "name": "OpenChat 7B",
                "model": "openchat-7b",
                "temperature": 0.7,
                "top_p": 0.9,
                "num_ctx": 8192,
            },
        }
        
        defaults = profiles.get(profile, {})
        defaults.update({"base_url": base_url, "profile": profile})
        defaults.update(overrides)
        return cls(**defaults)


@dataclass
class InferenceRequest:
    """Request for local inference."""
    prompt: str
    system_prompt: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    repeat_penalty: Optional[float] = None
    stop_sequences: Optional[List[str]] = None
    stream: bool = False
    context: Optional[List[Dict[str, str]]] = None
    seed: Optional[int] = None


@dataclass
class InferenceResponse:
    """Response from local inference."""
    message: str
    model: str
    provider: str
    tokens_generated: int
    tokens_per_second: float
    total_time: float
    prompt_tokens: int = 0
    finish_reason: str = "stop"
    raw: Optional[Dict[str, Any]] = None


class LocalAIBridge:
    """
    Lightweight bridge for unrestricted local AI inference.
    
    Supports multiple backends:
    - Ollama (http://localhost:11434)
    - Jan (http://localhost:1337/v1)
    - llama.cpp server (http://localhost:8080)
    - Custom OpenAI-compatible endpoints
    
    Optimized for 7B-14B models on consumer hardware.
    """
    
    def __init__(
        self,
        config: Optional[ModelConfig] = None,
        config_file: Optional[str] = None,
        default_profile: ModelProfile = ModelProfile.DOLPHIN_7B,
    ) -> None:
        self.config_file = Path(config_file) if config_file else Path("data/local_ai_config.json")
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        if config:
            self.config = config
        else:
            self.config = self._load_or_create_config(default_profile)
        
        self._client: Optional[httpx.AsyncClient] = None
        self._model_info: Optional[Dict[str, Any]] = None
        self._health_checked = False
        self._last_health_check = 0
        self._health_check_interval = 30
    
    def _load_or_create_config(self, default_profile: ModelProfile) -> ModelConfig:
        """Load config from file or create from profile."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return ModelConfig(**data)
            except Exception as e:
                logger.warning(f"Failed to load config: {e}, creating from profile")
        
        base_url = os.getenv("LOCAL_LFM_BASE_URL", "http://localhost:11434")
        config = ModelConfig.from_profile(default_profile, base_url=base_url)
        self.save_config()
        return config
    
    def save_config(self) -> None:
        """Save current config to file."""
        try:
            data = {
                "name": self.config.name,
                "base_url": self.config.base_url,
                "model": self.config.model,
                "profile": self.config.profile.value,
                "api_key": self.config.api_key,
                "timeout": self.config.timeout,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
                "top_p": self.config.top_p,
                "top_k": self.config.top_k,
                "repeat_penalty": self.config.repeat_penalty,
                "num_ctx": self.config.num_ctx,
                "num_gpu_layers": self.config.num_gpu_layers,
                "seed": self.config.seed,
                "stop_sequences": self.config.stop_sequences,
                "system_prompt": self.config.system_prompt,
                "enabled": self.config.enabled,
            }
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    
    def update_config(self, **kwargs) -> None:
        """Update config parameters."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        if "profile" in kwargs and isinstance(kwargs["profile"], str):
            self.config.profile = ModelProfile(kwargs["profile"])
        self.save_config()
        self._health_checked = False
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.config.timeout)
        return self._client
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
    
    async def health_check(self, force: bool = False) -> Dict[str, Any]:
        """Check if the local model endpoint is healthy."""
        now = time.time()
        if not force and self._health_checked and (now - self._last_health_check) < self._health_check_interval:
            return self._model_info or {"healthy": False, "error": "No health data"}
        
        client = await self._get_client()
        base_url = self.config.base_url.rstrip("/")
        
        try:
            if "/v1" in base_url or "jan" in base_url.lower():
                response = await client.get(f"{base_url}/models")
            else:
                response = await client.get(f"{base_url}/api/tags")
            
            response.raise_for_status()
            data = response.json()
            
            models = data.get("models", data.get("data", []))
            model_names = [m.get("name", m.get("id", "")) for m in models]
            
            model_available = any(self.config.model in name for name in model_names)
            
            self._model_info = {
                "healthy": True,
                "endpoint": base_url,
                "configured_model": self.config.model,
                "available_models": model_names,
                "model_available": model_available,
                "profile": self.config.profile.value,
                "checked_at": now,
            }
        except Exception as e:
            self._model_info = {
                "healthy": False,
                "endpoint": base_url,
                "configured_model": self.config.model,
                "error": str(e),
                "checked_at": now,
            }
        
        self._health_checked = True
        self._last_health_check = now
        return self._model_info
    
    def _build_ollama_body(self, request: InferenceRequest) -> Dict[str, Any]:
        """Build request body for Ollama API."""
        messages = []
        if request.system_prompt or self.config.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt or self.config.system_prompt})
        if request.context:
            messages.extend(request.context)
        messages.append({"role": "user", "content": request.prompt})
        
        return {
            "model": self.config.model,
            "messages": messages,
            "stream": request.stream,
            "options": {
                "num_predict": request.max_tokens or self.config.max_tokens,
                "temperature": request.temperature if request.temperature is not None else self.config.temperature,
                "top_p": request.top_p if request.top_p is not None else self.config.top_p,
                "top_k": request.top_k if request.top_k is not None else self.config.top_k,
                "repeat_penalty": request.repeat_penalty if request.repeat_penalty is not None else self.config.repeat_penalty,
                "num_ctx": self.config.num_ctx,
                "seed": request.seed if request.seed is not None else self.config.seed,
                "stop": request.stop_sequences or self.config.stop_sequences,
            },
            "keep_alive": "5m",
        }
    
    def _build_openai_body(self, request: InferenceRequest) -> Dict[str, Any]:
        """Build request body for OpenAI-compatible API (Jan, llama.cpp server)."""
        messages = []
        if request.system_prompt or self.config.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt or self.config.system_prompt})
        if request.context:
            messages.extend(request.context)
        messages.append({"role": "user", "content": request.prompt})
        
        body = {
            "model": self.config.model,
            "messages": messages,
            "stream": request.stream,
            "max_tokens": request.max_tokens or self.config.max_tokens,
            "temperature": request.temperature if request.temperature is not None else self.config.temperature,
            "top_p": request.top_p if request.top_p is not None else self.config.top_p,
        }
        
        if request.stop_sequences or self.config.stop_sequences:
            body["stop"] = request.stop_sequences or self.config.stop_sequences
        
        if self.config.seed != -1 and request.seed is None:
            body["seed"] = self.config.seed
        elif request.seed is not None:
            body["seed"] = request.seed
        
        return body
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stream: bool = False,
        context: Optional[List[Dict[str, str]]] = None,
    ) -> InferenceResponse:
        """
        Generate a response from the local model (non-streaming).
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt override
            max_tokens: Max tokens to generate
            temperature: Sampling temperature
            stream: Whether to stream (use generate_stream for streaming)
            context: Optional conversation history
            
        Returns:
            InferenceResponse with generated message and metadata
        """
        request = InferenceRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=stream,
            context=context,
        )
        
        start_time = time.time()
        client = await self._get_client()
        base_url = self.config.base_url.rstrip("/")
        
        if "/v1" in base_url or "jan" in base_url.lower():
            url = f"{base_url}/chat/completions"
            body = self._build_openai_body(request)
            headers = {"Content-Type": "application/json"}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
        else:
            url = f"{base_url}/api/chat"
            body = self._build_ollama_body(request)
            headers = {"Content-Type": "application/json"}
        
        try:
            response = await client.post(url, json=body, headers=headers)
            response.raise_for_status()
            data = response.json()
            total_time = time.time() - start_time
            
            if "/v1" in base_url or "jan" in base_url.lower():
                choice = data.get("choices", [{}])[0]
                message = choice.get("message", {}).get("content", "").strip()
                usage = data.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                finish_reason = choice.get("finish_reason", "stop")
            else:
                message = data.get("message", {}).get("content", "").strip()
                prompt_tokens = data.get("prompt_eval_count", 0)
                completion_tokens = data.get("eval_count", 0)
                finish_reason = "stop" if data.get("done", True) else "length"
            
            tokens_per_second = completion_tokens / total_time if total_time > 0 else 0
            
            return InferenceResponse(
                message=message,
                model=self.config.model,
                provider=self.config.name,
                tokens_generated=completion_tokens,
                tokens_per_second=tokens_per_second,
                total_time=total_time,
                prompt_tokens=prompt_tokens,
                finish_reason=finish_reason,
                raw=data,
            )
        except httpx.TimeoutException:
            raise TimeoutError(f"Request timed out after {self.config.timeout}s")
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"HTTP {e.response.status_code}: {e.response.text}")
        except Exception as e:
            raise RuntimeError(f"Inference failed: {e}")
    
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        context: Optional[List[Dict[str, str]]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Generate a streaming response from the local model.
        
        Yields:
            Text chunks as they are generated
        """
        request = InferenceRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
            context=context,
        )
        
        client = await self._get_client()
        base_url = self.config.base_url.rstrip("/")
        
        if "/v1" in base_url or "jan" in base_url.lower():
            url = f"{base_url}/chat/completions"
            body = self._build_openai_body(request)
            headers = {"Content-Type": "application/json"}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
        else:
            url = f"{base_url}/api/chat"
            body = self._build_ollama_body(request)
            headers = {"Content-Type": "application/json"}
        
        try:
            async with client.stream("POST", url, json=body, headers=headers, timeout=self.config.timeout) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    if line.startswith("data: "):
                        line = line[6:]
                    if line.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(line)
                        if "/v1" in base_url or "jan" in base_url.lower():
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                        else:
                            content = chunk.get("message", {}).get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue
        except httpx.TimeoutException:
            raise TimeoutError(f"Stream timed out after {self.config.timeout}s")
        except Exception as e:
            raise RuntimeError(f"Stream failed: {e}")
    
    async def list_models(self) -> List[Dict[str, Any]]:
        """List available models from the endpoint."""
        await self.health_check()
        return self._model_info.get("available_models", []) if self._model_info else []
    
    def get_config(self) -> Dict[str, Any]:
        """Get current configuration as dict."""
        return {
            "name": self.config.name,
            "base_url": self.config.base_url,
            "model": self.config.model,
            "profile": self.config.profile.value,
            "timeout": self.config.timeout,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "top_k": self.config.top_k,
            "repeat_penalty": self.config.repeat_penalty,
            "num_ctx": self.config.num_ctx,
            "num_gpu_layers": self.config.num_gpu_layers,
            "seed": self.config.seed,
            "stop_sequences": self.config.stop_sequences,
            "system_prompt": self.config.system_prompt,
            "enabled": self.config.enabled,
        }
    
    def set_profile(self, profile: ModelProfile, base_url: Optional[str] = None) -> None:
        """Switch to a different model profile."""
        url = base_url or self.config.base_url
        self.config = ModelConfig.from_profile(profile, base_url=url)
        self.save_config()
        self._health_checked = False


_local_bridge: Optional[LocalAIBridge] = None


def get_local_bridge(
    config: Optional[ModelConfig] = None,
    config_file: Optional[str] = None,
    default_profile: ModelProfile = ModelProfile.DOLPHIN_7B,
) -> LocalAIBridge:
    """Get or create the global local AI bridge instance."""
    global _local_bridge
    if _local_bridge is None:
        _local_bridge = LocalAIBridge(config=config, config_file=config_file, default_profile=default_profile)
    return _local_bridge


async def generate_unrestricted(
    prompt: str,
    system_prompt: Optional[str] = None,
    max_tokens: int = 2048,
    temperature: float = 0.7,
    profile: ModelProfile = ModelProfile.DOLPHIN_7B,
    stream: bool = False,
) -> InferenceResponse | AsyncGenerator[str, None]:
    """
    Convenience function for unrestricted local generation.
    
    Usage:
        # Non-streaming
        response = await generate_unrestricted("Escribe un cuento cyberpunk")
        print(response.message)
        
        # Streaming
        async for chunk in generate_unrestricted("Código Python para...", stream=True):
            print(chunk, end="", flush=True)
    """
    bridge = get_local_bridge(default_profile=profile)
    if stream:
        return bridge.generate_stream(prompt, system_prompt, max_tokens, temperature)
    return await bridge.generate(prompt, system_prompt, max_tokens, temperature)