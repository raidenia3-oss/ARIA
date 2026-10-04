"""AI Router - multi-provider AI gateway with automatic failover."""
import json
import os
import socket
from dataclasses import dataclass
from typing import Optional, Dict, List, Any, AsyncGenerator
from urllib.parse import urlparse
import time

import httpx

from backend.eventlog import EventLog, get_event_log

CIRCUIT_COOLDOWN_SECONDS = 120.0

# Cuánto vale una medicion de salud antes de volver a sondear. El sondeo es de
# arranque (una vez), NO por request: si no, cada request paga el timeout de un
# provider caido (jan:1337 apagado, etc.).
HEALTH_TTL_SECONDS = 300.0


@dataclass
class ProviderConfig:
    name: str
    base_url: str
    api_key_env: str
    model: str
    timeout: float = 30.0
    priority: int = 0
    enabled_without_key: bool = False

    @property
    def enabled(self) -> bool:
        return bool(os.environ.get(self.api_key_env)) or self.enabled_without_key


class AIRouter:
    # Cache de salud COMPARTIDO entre instancias: varios modulos construyen un
    # AIRouter() por request (p.ej. backend/sync_engine.py), y sondear en cada
    # instancia seria sondear por request — justo lo que queremos evitar.
    _health_cache: Dict[str, bool] = {}
    _health_probed_at: float = 0.0
    _health_source: str = "unavailable"

    def __init__(
        self,
        state_file: str = "ai_router_state.json",
        event_log: Optional["EventLog"] = None,
    ) -> None:
        self.state_file = state_file
        self.state = self._load_state()
        self.providers: Dict[str, ProviderConfig] = {}
        for p in self.default_providers():
            self.providers[p.name] = p
        self._event_log = event_log

    def _events(self) -> "EventLog":
        """Event log inyectado, o el compartido del proceso."""
        if self._event_log is not None:
            return self._event_log
        return get_event_log()

    def _load_state(self) -> dict:
        default = {"scores": {}, "last_failures": {}, "circuit_until": {}}
        if not os.path.exists(self.state_file):
            return default
        try:
            with open(self.state_file, "r") as f:
                loaded = json.load(f)
        except Exception:
            return default
        if not isinstance(loaded, dict):
            return default
        for key, value in default.items():
            if not isinstance(loaded.get(key), dict):
                loaded[key] = value
        return loaded

    def _save_state(self):
        try:
            with open(self.state_file, "w") as f:
                json.dump(self.state, f, indent=2)
        except Exception:
            pass

    @staticmethod
    def _env_float(name: str, default: float) -> float:
        try:
            return float(os.environ[name])
        except (KeyError, ValueError, TypeError):
            return default

    @staticmethod
    def _env_int(name: str, default: int) -> int:
        try:
            return int(os.environ[name])
        except (KeyError, ValueError, TypeError):
            return default

    @classmethod
    def default_providers(cls) -> List[ProviderConfig]:
        return [
            ProviderConfig("groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY", "llama-3.3-70b-versatile", 15.0, 1),
            ProviderConfig("mistral", "https://api.mistral.ai/v1", "MISTRAL_API_KEY", "mistral-small-latest", 20.0, 2),
            ProviderConfig("deepseek", "https://api.deepseek.com/v1", "DEEPSEEK_API_KEY", "deepseek-chat", 30.0, 3),
            ProviderConfig("openrouter", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "mistralai/mistral-7b-instruct", 30.0, 4),
            ProviderConfig("gemini", "https://generativelanguage.googleapis.com/v1beta", "GEMINI_API_KEY", "gemini-2.0-flash", 30.0, 5),
            ProviderConfig("nvidia", "https://integrate.api.nvidia.com/v1", "NVIDIA_API_KEY", "meta/llama-3.1-70b-instruct", 30.0, 6),
            ProviderConfig("zai", "https://api.z.ai/v1", "ZAI_API_KEY", "glm-4-plus", 30.0, 7),
            ProviderConfig("local-ollama", "http://localhost:11434", "", os.environ.get("LOCAL_LFM_MODEL", "dolphin-2_6-phi-2:latest"), 60.0, 8, True),
            ProviderConfig(
                "jan",
                os.environ.get("JAN_BASE_URL", "http://localhost:1337/v1"),
                "",
                os.environ.get("JAN_MODEL", "gemma-3-1b-it"),
                cls._env_float("JAN_TIMEOUT", 60.0),
                cls._env_int("JAN_PRIORITY", 9),
                True,
            ),
        ]

    def _probe_provider(self, provider: ProviderConfig) -> bool:
        """Sonda barata de reachability: ¿el host:puerto acepta conexion?

        No valida auth ni el modelo: solo descarta providers con el puerto
        cerrado (jan:1337 caido, Ollama apagado), que son timeouts garantizados
        en cada request. Un provider que responde TCP se intenta normalmente.
        """
        try:
            parsed = urlparse(provider.base_url)
        except ValueError:
            return False
        host = parsed.hostname
        if not host:
            return False
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError:
            return False

    def probe_once(self, force: bool = False) -> Dict[str, bool]:
        """Sondea la salud de todos los providers UNA vez y la cachea.

        `data_source` pasa a "measured" porque el resultado viene de una
        medicion real (conexion TCP), no de un supuesto. Se salta el sondeo si
        el cache sigue fresco, salvo que force=True.
        """
        now = time.time()
        if (
            not force
            and AIRouter._health_probed_at
            and (now - AIRouter._health_probed_at) < HEALTH_TTL_SECONDS
):
            return AIRouter._health_cache
        previous = dict(AIRouter._health_cache)
        for p in self.providers.values():
            AIRouter._health_cache[p.name] = self._probe_provider(p)
        AIRouter._health_probed_at = now
        AIRouter._health_source = "measured"
        self._record_probe_events(previous)
        return AIRouter._health_cache

    def _record_probe_events(self, previous: Dict[str, bool]) -> None:
        """Deja evento solo cuando un provider cambia de disponibilidad.

        Sondear en cada TTL emite 9 líneas por ciclo y eso esconde lo que importa.
        Lo útil es la transición: un provider que cae, o que vuelve.
        """
        events = self._events()
        for name, current in AIRouter._health_cache.items():
            before = previous.get(name)
            if before == current:
                continue
            events.append(
                "provider.probe",
                provider=name,
                available=current,
                outcome="ok" if current else "error",
                error=None if current else "unreachable",
            )

    def health_snapshot(self) -> Dict[str, Any]:
        """Estado de salud medido, con su procedencia explicita."""
        self.probe_once()
        return {
            "data_source": AIRouter._health_source,
            "probed_at": AIRouter._health_probed_at,
            "providers": dict(AIRouter._health_cache),
        }

    def _get_provider_order(self, context: Optional[dict] = None) -> List[ProviderConfig]:
        self.probe_once()
        now = time.time()
        providers = [
            p
            for p in self.providers.values()
            if p.enabled
            and float(self.state["circuit_until"].get(p.name, 0) or 0) <= now
            and AIRouter._health_cache.get(p.name, True)
        ]
        providers.sort(key=lambda p: p.priority)
        return providers

    def _record_success(self, provider: str):
        self.state["scores"][provider] = self.state["scores"].get(provider, 0) + 1
        self.state["last_failures"].pop(provider, None)
        self.state["circuit_until"].pop(provider, None)
        self._save_state()

    def _record_failure(self, provider: str, error: str):
        self.state["scores"][provider] = max(-10, self.state["scores"].get(provider, 0) - 1)
        self.state["last_failures"][provider] = error
        self.state["circuit_until"][provider] = time.time() + CIRCUIT_COOLDOWN_SECONDS
        self._save_state()

    async def generate_response(
        self,
        prompt: str,
        context: Optional[dict] = None,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        providers = self._get_provider_order(context)
        last_error = None
        attempted: List[str] = []
        event_log = self._events()
        for provider in providers:
            started = time.perf_counter()
            attempted.append(provider.name)
            try:
                chunks: List[str] = []
                async for chunk in self._call_provider(provider, prompt, context, system_prompt, max_tokens, temperature):
                    chunks.append(chunk)
                text = "".join(chunks)
                if not text.strip():
                    raise ValueError("empty response from provider")
                self._record_success(provider.name)
                latency_s = round(time.perf_counter() - started, 3)
                event_log.append(
                    "routing.decision",
                    provider=provider.name,
                    model=provider.model,
                    latency_ms=round(latency_s * 1000, 1),
                    tokens=None,
                    cost_usd=None,
                    outcome="ok",
                    attempted=attempted,
                    session_id=(context or {}).get("session_id"),
                )
                return {
                    "message": text,
                    "provider": provider.name,
                    "latency": latency_s,
                    "tokens": None,
                    "finish_reason": "stop",
                }
            except Exception as e:
                last_error = str(e)
                self._record_failure(provider.name, last_error)
                event_log.append(
                    "routing.provider_error",
                    provider=provider.name,
                    model=provider.model,
                    latency_ms=round((time.perf_counter() - started) * 1000, 1),
                    outcome="error",
                    error=last_error,
                    attempted=attempted,
                )
                continue
        event_log.append(
            "routing.decision",
            provider="none",
            outcome="error",
            error=last_error,
            attempted=attempted,
            session_id=(context or {}).get("session_id"),
        )
        return {
            "message": "",
            "provider": "none",
            "latency": None,
            "tokens": None,
            "finish_reason": "error",
            "error": f"All providers failed. Last error: {last_error}",
        }

    async def stream_response(
        self,
        prompt: str,
        context: Optional[dict] = None,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        providers = self._get_provider_order(context)
        last_error = None
        for provider in providers:
            try:
                async for chunk in self._call_provider(provider, prompt, context, system_prompt, max_tokens, temperature):
                    yield chunk
                self._record_success(provider.name)
                return
            except Exception as e:
                last_error = str(e)
                self._record_failure(provider.name, last_error)
                continue
        yield f"[All providers failed. Last error: {last_error}]"

    async def _call_provider(self, provider: ProviderConfig, prompt, context, system_prompt, max_tokens, temperature):
        if provider.name == "local-ollama":
            async for chunk in self._call_ollama(provider, prompt, system_prompt, max_tokens, temperature):
                yield chunk
        elif provider.name == "gemini":
            async for chunk in self._call_gemini(provider, prompt, system_prompt, max_tokens, temperature):
                yield chunk
        else:
            async for chunk in self._call_openai_compatible(provider, prompt, system_prompt, max_tokens, temperature):
                yield chunk

    async def _call_openai_compatible(self, provider, prompt, system_prompt, max_tokens, temperature):
        api_key = os.environ.get(provider.api_key_env, "") if provider.api_key_env else ""
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        body = {
            "model": provider.model,
            "messages": [],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_prompt:
            body["messages"].append({"role": "system", "content": system_prompt})
        body["messages"].append({"role": "user", "content": prompt})
        async with httpx.AsyncClient(timeout=provider.timeout) as client:
            resp = await client.post(f"{provider.base_url}/chat/completions", headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            chunk_size = 50
            for i in range(0, len(content), chunk_size):
                yield content[i:i+chunk_size]

    async def _call_gemini(self, provider, prompt, system_prompt, max_tokens, temperature):
        api_key = os.environ.get(provider.api_key_env, "")
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature},
        }
        if system_prompt:
            body["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        url = f"{provider.base_url}/models/{provider.model}:generateContent?key={api_key}"
        async with httpx.AsyncClient(timeout=provider.timeout) as client:
            resp = await client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()
            content = data["candidates"][0]["content"]["parts"][0]["text"]
            chunk_size = 50
            for i in range(0, len(content), chunk_size):
                yield content[i:i+chunk_size]

    async def _call_ollama(self, provider, prompt, system_prompt, max_tokens, temperature):
        body = {
            "model": provider.model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
                "top_p": 0.9,
                "repeat_penalty": 1.15,
            },
            "stop": ["\nUser:", "\nHuman:", "User:", "Human:", "<|im_end|>", "<|endoftext|>"],
        }
        if system_prompt:
            body["system"] = system_prompt
        async with httpx.AsyncClient(timeout=provider.timeout) as client:
            async with client.stream("POST", f"{provider.base_url}/api/generate", json=body) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if "response" in data:
                            yield data["response"]
                    except json.JSONDecodeError:
                        continue
