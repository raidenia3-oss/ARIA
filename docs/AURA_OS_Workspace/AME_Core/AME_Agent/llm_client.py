import os, json, re, time
import requests

class ModelProvider:
    """Representa un proveedor LLM con estado de tokens."""
    def __init__(self, name, call_fn, tokens_per_min=0, daily_limit=0):
        self.name = name
        self.call_fn = call_fn
        self.tokens_per_min = tokens_per_min
        self.daily_limit = daily_limit
        self.tokens_used_today = 0
        self.tokens_used_this_min = 0
        self.last_min_reset = time.time()
        self.active = True
        self.error_count = 0

    def can_use(self):
        now = time.time()
        if now - self.last_min_reset >= 60:
            self.tokens_used_this_min = 0
            self.last_min_reset = now
        if self.tokens_per_min and self.tokens_used_this_min >= self.tokens_per_min:
            return False
        if self.daily_limit and self.tokens_used_today >= self.daily_limit:
            return False
        if self.error_count >= 3:
            return False
        return self.active

    def register_usage(self, tokens):
        self.tokens_used_this_min += tokens
        self.tokens_used_today += tokens

    def register_error(self):
        self.error_count += 1
        if self.error_count >= 3:
            self.active = False

    def reset_errors(self):
        self.error_count = 0
        self.active = True


class LLMClient:
    """
    Cliente multi-modelo con fallback automatico.
    Modelos censurados: Gemini, Groq, OpenRouter
    Modelos sin censura: Ollama local, Venice (si disponible)
    Cuando un modelo se queda sin tokens, pasa al siguiente automaticamente.
    """

    def __init__(self, config: dict):
        self.config = config
        self.providers: list[ModelProvider] = []
        self.current_provider_idx = 0
        self._init_providers()

    def _init_providers(self):
        api_key = (
            os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GROQ_API_KEY")
            or self.config.get("api_key", "")
        )

        # Orden de prioridad: modelos gratuitos primero, luego locales
        self.providers = [
            ModelProvider("gemini-flash", self._call_gemini,
                         tokens_per_min=15, daily_limit=1500),
            ModelProvider("groq-llama", self._call_groq,
                         tokens_per_min=30, daily_limit=1000),
            ModelProvider("openrouter-free", self._call_openrouter,
                         tokens_per_min=20, daily_limit=500),
            ModelProvider("ollama-local", self._call_ollama,
                         tokens_per_min=0, daily_limit=0),  # sin limite
        ]
        self.api_key = api_key

    def _get_available_provider(self) -> ModelProvider | None:
        for i in range(len(self.providers)):
            idx = (self.current_provider_idx + i) % len(self.providers)
            p = self.providers[idx]
            if p.can_use():
                self.current_provider_idx = idx
                return p
        return None

    def get_status(self) -> dict:
        """Estado de todos los proveedores para el dashboard."""
        return {
            "current": self.providers[self.current_provider_idx].name,
            "providers": [
                {
                    "name": p.name,
                    "active": p.active,
                    "can_use": p.can_use(),
                    "tokens_today": p.tokens_used_today,
                    "daily_limit": p.daily_limit,
                }
                for p in self.providers
            ],
        }

    def reset_all_providers(self):
        """Reiniciar todos los proveedores (nuevo dia)."""
        for p in self.providers:
            p.tokens_used_today = 0
            p.reset_errors()

    async def plan(self, context: dict) -> dict:
        prompt = self._build_prompt(context)
        provider = self._get_available_provider()
        if not provider:
            return {"analysis": "Sin proveedores disponibles", "steps": [],
                    "expected_result": "todos los modelos agotados"}

        try:
            response = provider.call_fn(prompt, self.api_key)
            provider.reset_errors()
            # Estimar tokens usados (aprox 4 chars = 1 token)
            estimated_tokens = len(response) // 4
            provider.register_usage(estimated_tokens)
            return self._parse_plan(response)
        except Exception as e:
            provider.register_error()
            # Intentar con el siguiente proveedor
            return await self.plan(context)

    def _build_prompt(self, context: dict) -> str:
        tools_list = "\n".join(f"- {t}" for t in context.get("tools", []))
        return f"""Eres AME Agent, un agente autonomo en Android/Termux.
TAREA: {context['task']}
HERRAMIENTAS: {tools_list}
Responde SOLO en JSON:
{{"analysis":"que hago","steps":[{{"tool":"nombre","args":{{}},"reason":"por que"}}],"expected_result":"resultado"}}
Maximo 5 pasos."""

    def _call_gemini(self, prompt, api_key):
        url = ("https://generativelanguage.googleapis.com/v1beta/"
               "models/gemini-1.5-flash:generateContent")
        r = requests.post(url, params={"key": api_key},
                         json={"contents": [{"parts": [{"text": prompt}]}]},
                         timeout=30)
        data = r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    def _call_groq(self, prompt, api_key):
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                         headers={"Authorization": f"Bearer {api_key}"},
                         json={"model": "llama-3.1-8b-instant",
                               "messages": [{"role": "user", "content": prompt}],
                               "max_tokens": 1000}, timeout=30)
        return r.json()["choices"][0]["message"]["content"]

    def _call_openrouter(self, prompt, api_key):
        r = requests.post("https://openrouter.ai/api/v1/chat/completions",
                         headers={"Authorization": f"Bearer {api_key}"},
                         json={"model": "google/gemini-flash-1.5",
                               "messages": [{"role": "user", "content": prompt}]},
                         timeout=30)
        return r.json()["choices"][0]["message"]["content"]

    def _call_ollama(self, prompt, _api_key=""):
        model = self.config.get("model", "llama3.2").replace("ollama/", "")
        r = requests.post("http://localhost:11434/api/generate",
                         json={"model": model, "prompt": prompt,
                               "stream": False}, timeout=60)
        return r.json()["response"]

    def _parse_plan(self, response: str) -> dict:
        try:
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                return json.loads(match.group())
        except json.JSONDecodeError:
            pass
        return {"analysis": response[:200], "steps": [],
                "expected_result": "respuesta sin estructura"}