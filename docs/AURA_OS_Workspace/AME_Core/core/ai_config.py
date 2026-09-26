#!/usr/bin/env python3
"""
AI Config — Gestión centralizada de múltiples proveedores de IA
Soporta: OpenRouter (free), Google Gemini, LM Studio (local), y fallback legacy.
=====================================================
Pilar #1: API Keys gratuitas + redundancia local.
"""

import os
import logging
from typing import Dict, List, Optional, TypedDict
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env desde la raíz del proyecto
BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / ".env")

logger = logging.getLogger(__name__)


class ProviderConfig(TypedDict, total=False):
    """Estructura de configuración para un proveedor de IA."""

    name: str
    api_key: str
    base_url: str
    model: str
    timeout: int


@dataclass
class AIProvider:
    """Configuración de un proveedor de IA individual."""

    name: str
    api_key: str
    base_url: str
    model: str
    timeout: int
    enabled: bool = False

    def __post_init__(self):
        self.enabled = bool(self.api_key) and bool(self.base_url)

    def get_headers(self) -> Dict[str, str]:
        """Obtener headers de autorización para el proveedor."""
        headers = {"Content-Type": "application/json"}
        if self.name == "openrouter":
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["HTTP-Referer"] = "https://github.com/raidenia3-oss/AURA-server.01"
            headers["X-Title"] = "AURA Ecosystem"
        elif self.name == "gemini":
            # Gemini usa API key como query param, no en header
            pass
        elif self.name in ("lm_studio", "proxy"):
            headers["Authorization"] = f"Bearer {self.api_key}" if self.api_key else ""
        return headers

    def get_chat_endpoint(self) -> str:
        """Obtener URL completa del endpoint de chat."""
        if self.name == "gemini":
            return f"{self.base_url}/models/{self.model}:streamGenerateContent?key={self.api_key}"
        return f"{self.base_url}/chat/completions"

    def build_payload(self, messages: List[Dict], stream: bool = True, **kwargs) -> Dict:
        """Construir payload específico para cada proveedor."""
        if self.name == "gemini":
            return {
                "contents": [
                    {
                        "role": "user" if m["role"] == "user" else "model",
                        "parts": [{"text": m["content"]}],
                    }
                    for m in messages
                ],
                "generationConfig": {
                    "temperature": kwargs.get("temperature", 0.7),
                    "maxOutputTokens": kwargs.get("max_tokens", 4096),
                },
            }
        # Formato estándar OpenAI-compatible (OpenRouter, LM Studio, Proxy)
        return {"model": self.model, "messages": messages, "stream": stream, **kwargs}


@dataclass
class AIConfig:
    """
    Configuración global de la arquitectura de IA.
    Administra todos los proveedores y el orden de fallback.
    """

    providers: List[AIProvider] = field(default_factory=list)
    preference: str = "auto"
    active_provider: Optional[str] = None

    def __post_init__(self):
        self._load_from_env()
        self.preference = os.getenv("AI_PROVIDER_PREFERENCE", "auto").lower()

    def _load_from_env(self):
        """Cargar todos los proveedores desde variables de entorno."""
        self.providers = [
            AIProvider(
                name="openrouter",
                api_key=os.getenv("OPENROUTER_API_KEY", ""),
                base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
                model=os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3-8b-instruct:free"),
                timeout=int(os.getenv("OPENROUTER_TIMEOUT", "30")),
            ),
            AIProvider(
                name="gemini",
                api_key=os.getenv("GEMINI_API_KEY", ""),
                base_url=os.getenv(
                    "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
                ),
                model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp"),
                timeout=int(os.getenv("GEMINI_TIMEOUT", "30")),
            ),
            AIProvider(
                name="lm_studio",
                api_key=os.getenv("LM_STUDIO_API_KEY", ""),  # LM Studio no requiere key
                base_url=os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1"),
                model=os.getenv("LM_STUDIO_MODEL", "gemma-2-2b-it"),
                timeout=int(os.getenv("LM_STUDIO_TIMEOUT", "60")),
            ),
            AIProvider(
                name="proxy",  # Legacy Cerebras
                api_key=os.getenv("PROXY_API_KEY", ""),
                base_url=os.getenv("PROXY_BASE_URL", "https://api.cerebras.ai/v1"),
                model=os.getenv("PROXY_MODEL", "glm-4"),
                timeout=int(os.getenv("PROXY_TIMEOUT", "30")),
            ),
        ]

    def get_provider(self, name: str) -> Optional[AIProvider]:
        """Obtener un proveedor por nombre."""
        for p in self.providers:
            if p.name == name:
                return p
        return None

    def get_fallback_chain(self) -> List[AIProvider]:
        """
        Obtener la cadena de fallback según la preferencia configurada.
        Si preference='auto', devuelve todos los proveedores habilitados
        en orden: OpenRouter -> Gemini -> LM Studio -> Proxy
        """
        if self.preference != "auto":
            specific = self.get_provider(self.preference)
            if specific and specific.enabled:
                return [specific]

        # Orden de prioridad para fallback automático
        order = ["openrouter", "gemini", "lm_studio", "proxy"]
        chain = []
        for name in order:
            provider = self.get_provider(name)
            if provider:
                chain.append(provider)
        return chain

    def get_health_summary(self) -> Dict:
        """Resumen de salud de todos los proveedores."""
        return {
            "preference": self.preference,
            "providers": [
                {
                    "name": p.name,
                    "enabled": p.enabled,
                    "model": p.model,
                    "base_url": p.base_url,
                }
                for p in self.providers
            ],
        }


# Singleton de configuración global
CONFIG: AIConfig = AIConfig()


def get_config() -> AIConfig:
    """Obtener la instancia global de configuración."""
    return CONFIG
