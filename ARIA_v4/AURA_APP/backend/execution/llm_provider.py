"""LLM Provider — Ollama routing con fallback"""

from typing import Dict, Optional


class LLMProvider:
    """Proveedor LLM con fallback chain"""

    def __init__(self):
        self.providers = ['ollama', 'groq', 'anthropic']
        self.active_provider = 'ollama'
        self.fallback_chain = ['ollama', 'groq', 'anthropic']

    def chat(self, message: str, history: list = None, system_prompt: str = "") -> Dict:
        return {
            'response': '[Respuesta simulada]',
            'provider': self.active_provider,
            'latency': 0.5,
        }

    def set_provider(self, provider: str) -> bool:
        if provider in self.providers:
            self.active_provider = provider
            return True
        return False

    def get_available(self) -> list:
        return self.providers

    def get_best(self) -> str:
        for p in self.fallback_chain:
            if self._is_healthy(p):
                return p
        return self.providers[0]

    def _is_healthy(self, provider: str) -> bool:
        return True
