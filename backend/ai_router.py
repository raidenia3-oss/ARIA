"""AI Router - multi-provider AI gateway with automatic failover."""
import json
import os
from dataclasses import dataclass
from typing import Optional, Dict, List, AsyncGenerator
import httpx


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
    def __init__(self, state_file: str = "ai_router_state.json"):
        self.state_file = state_file
        self.state = self._load_state()
        self.providers: Dict[str, ProviderConfig] = {}
        for p in self.default_providers():
            self.providers[p.name] = p

    def _load_state(self) -> dict:
        if not os.path.exists(self.state_file):
            return {"scores": {}, "last_failures": {}, "circuit_until": {}}
        try:
            with open(self.state_file, "r") as f:
                return json.load(f)
        except Exception:
            return {"scores": {}, "last_failures": {}, "circuit_until": {}}

    def _save_state(self):
        try:
            with open(self.state_file, "w") as f:
                json.dump(self.state, f, indent=2)
        except Exception:
            pass

    @staticmethod
    def default_providers() -> List[ProviderConfig]:
        return [
            ProviderConfig("groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY", "llama-3.3-70b-versatile", 15.0, 1),
            ProviderConfig("mistral", "https://api.mistral.ai/v1", "MISTRAL_API_KEY", "mistral-small-latest", 20.0, 2),
            ProviderConfig("deepseek", "https://api.deepseek.com/v1", "DEEPSEEK_API_KEY", "deepseek-chat", 30.0, 3),
            ProviderConfig("openrouter", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "mistralai/mistral-7b-instruct", 30.0, 4),
            ProviderConfig("gemini", "https://generativelanguage.googleapis.com/v1beta", "GEMINI_API_KEY", "gemini-2.0-flash", 30.0, 5),
            ProviderConfig("nvidia", "https://integrate.api.nvidia.com/v1", "NVIDIA_API_KEY", "meta/llama-3.1-70b-instruct", 30.0, 6),
            ProviderConfig("zai", "https://api.z.ai/v1", "ZAI_API_KEY", "glm-4-plus", 30.0, 7),
            ProviderConfig("local-ollama", "http://localhost:11434/v1", "", "qwen3:4b", 30.0, 0, True),
            ProviderConfig("jan", "http://localhost:1337/v1", "", "gemma-3-1b-it", 60.0, 0, True),
        ]

    def _get_provider_order(self, context: Optional[dict] = None) -> List[ProviderConfig]:
        providers = [p for p in self.providers.values() if p.enabled]
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
        self.state["circuit_until"][provider] = 0
        self._save_state()

    async def generate_response(
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
            "options": {"num_predict": max_tokens, "temperature": temperature},
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
