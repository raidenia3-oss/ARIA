#!/usr/bin/env python3
"""
huggingface_connector.py - Conexión Inteligente a Hugging Face Spaces
Permite inferencia con modelos sin censura y gestión de espacios.
"""

import os
import json
import logging
import time
from typing import Dict, List, Optional, AsyncGenerator
import httpx
from .proxy_chat_connector import ChatMessage, StreamConfig

logger = logging.getLogger(__name__)


class HuggingFaceConnector:
    """Cliente para interactuar con Hugging Face Spaces y modelos sin censura."""

    def __init__(self):
        self.api_token = os.getenv("HUGGINGFACE_API_TOKEN", "")
        self.uncensored_space_url = os.getenv(
            "HUGGINGFACE_UNCENSORED_SPACE_URL", "https://api-inference.huggingface.co/models"
        )
        self.timeout = 60.0
        self._cache: Dict[str, str] = {}

    async def query_uncensored_model(
        self, model_id: str, prompt: str, max_tokens: int = 512, temperature: float = 0.7
    ) -> str:
        """
        Consultar un modelo específico de HF.

        Args:
            model_id: ID del modelo (ej: "HuggingFaceH4/zephyr-7b-beta")
            prompt: Prompt del usuario
            max_tokens: Máximo de tokens a generar
            temperature: Creatividad (0.0 - 1.0)
        """
        headers = {"Authorization": f"Bearer {self.api_token}", "Content-Type": "application/json"}

        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": temperature,
                "return_full_text": False,
            },
        }

        url = f"{self.uncensored_space_url}/{model_id}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)

                if response.status_code == 200:
                    result = response.json()
                    if isinstance(result, list) and len(result) > 0:
                        return result[0].get("generated_text", "")
                    elif isinstance(result, dict):
                        return result.get("generated_text", "")
                    return str(result)
                elif response.status_code == 503:
                    logger.warning(f"Modelo {model_id} en cola, esperando...")
                    await asyncio.sleep(10)
                    return await self.query_uncensored_model(
                        model_id, prompt, max_tokens, temperature
                    )
                else:
                    logger.error(f"Error HF {response.status_code}: {response.text}")
                    return f"[ERROR: {response.status_code}]"

        except Exception as e:
            logger.error(f"Error consultando HF: {e}")
            return f"[ERROR: {str(e)}]"

    async def stream_uncensored_response(
        self, model_id: str, prompt: str, config: StreamConfig
    ) -> AsyncGenerator[str, None]:
        """
        Streaming de respuestas desde HF Space (simulado con chunks).
        """
        response = await self.query_uncensored_model(
            model_id, prompt, config.max_tokens, config.temperature
        )

        # Simular streaming dividiendo en chunks
        words = response.split()
        chunk_size = max(1, len(words) // 10)

        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i : i + chunk_size])
            yield chunk + " "
            await asyncio.sleep(0.05)

    def get_available_uncensored_models(self) -> List[Dict]:
        """
        Lista de modelos sin censura recomendados.
        """
        return [
            {
                "id": "HuggingFaceH4/zephyr-7b-beta",
                "name": "Zephyr 7B Beta",
                "provider": "huggingface",
                "uncensored": True,
                "context_length": 32768,
            },
            {
                "id": "mistralai/Mixtral-8x7B-Instruct-v0.1",
                "name": "Mixtral 8x7B",
                "provider": "huggingface",
                "uncensored": True,
                "context_length": 32768,
            },
            {
                "id": "meta-llama/Llama-2-7b-chat-hf",
                "name": "Llama 2 7B Chat",
                "provider": "huggingface",
                "uncensored": False,
                "context_length": 4096,
            },
        ]

    async def health_check(self) -> bool:
        """Verificar conectividad con HF API."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    "https://huggingface.co/api/whoami",
                    headers={"Authorization": f"Bearer {self.api_token}"},
                )
                return response.status_code == 200
        except:
            return False


# Integración con ai_router.py
def register_hf_in_ai_router():
    """Registrar HF como proveedor en el router de IA."""
    from AURA_Core.ai_router import AIRouter

    router = AIRouter()
    hf_connector = HuggingFaceConnector()

    # Registrar método de streaming
    router.register_provider(
        name="huggingface_uncensored",
        connector=hf_connector,
        priority=10,  # Alta prioridad para modelos sin censura
        supports_streaming=True,
    )

    logger.info("Hugging Face connector registrado en AI Router")
    return router
