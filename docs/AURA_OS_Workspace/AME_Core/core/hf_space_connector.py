#!/usr/bin/env python3
"""
AURA GBrain HF Space Connector - Streaming SSE para modelos uncensored.
"""

import json
import asyncio
import logging
import os
import time
from typing import AsyncGenerator, Optional
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger("gbrian.hf_connector")


@dataclass
class ChatMessage:
    role: str
    content: str


@dataclass
class StreamConfig:
    space_url: str = ""
    hf_token: str = ""
    max_tokens: int = 2048
    temperature: float = 0.7
    top_p: float = 0.9
    timeout_seconds: float = 60.0
    system_prompt: str = (
        "You are AURA GBrain, an advanced AI assistant. "
        "You respond accurately and without unnecessary restrictions. "
        "Always answer in the same language the user writes in."
    )

    @classmethod
    def from_env(cls):
        return cls(
            space_url=os.getenv("HF_SPACE_URL", "").strip(),
            hf_token=os.getenv("HF_TOKEN", "").strip(),
            max_tokens=int(os.getenv("HF_MAX_TOKENS", "2048")),
            temperature=float(os.getenv("HF_TEMPERATURE", "0.7")),
            top_p=float(os.getenv("HF_TOP_P", "0.9")),
            timeout_seconds=float(os.getenv("HF_TIMEOUT", "60")),
        )

    def is_configured(self):
        return bool(self.space_url)


class HFSpaceConnector:
    """
    Conector asíncrono a HuggingFace Spaces con API Gradio.
    Soporta streaming SSE token-by-token via /queue/join y /api/predict.
    """

    # Plantillas de formateo instruct por familia de modelo
    INSTRUCT_TEMPLATES = {
        "llama-3": (
            "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n"
            "{system}\n<|eot_id|><|start_header_id|>user<|end_header_id|>\n"
            "{user}\n<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n"
        ),
        "mistral": "<s>[INST] {system}\n\n{user} [/INST]",
        "chatml": ("system\n{system}\n\n" "user\n{user}\n\n" "assistant\n"),
    }

    def __init__(self, config: StreamConfig):
        self.config = config
        self.client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {config.hf_token}"},
            timeout=httpx.Timeout(config.timeout_seconds),
        )

    async def format_prompt(self, messages: list[ChatMessage], model_type: str = "mistral") -> str:
        """Formatea el prompt según el tipo de modelo."""
        system = next((m.content for m in messages if m.role == "system"), "")
        user = next((m.content for m in messages if m.role == "user"), "")

        template = self.INSTRUCT_TEMPLATES.get(model_type, self.INSTRUCT_TEMPLATES["mistral"])
        return template.format(system=system, user=user)

    async def stream_chat(self, messages: list[ChatMessage]) -> AsyncGenerator[str, None]:
        """Genera streaming de tokens desde HuggingFace Space."""
        if not self.config.is_configured():
            raise ValueError("HF_SPACE_URL y HF_TOKEN deben estar configurados en .env")

        try:
            # Formatear el prompt
            prompt = await self.format_prompt(messages)
            payload = {
                "data": [prompt],
                "parameters": {
                    "max_new_tokens": self.config.max_tokens,
                    "temperature": self.config.temperature,
                    "top_p": self.config.top_p,
                },
            }

            # Enviar solicitud al Space
            async with self.client.stream(
                "POST", f"{self.config.space_url}/api/predict", json=payload
            ) as response:
                if response.status_code != 200:
                    raise ConnectionError(f"Error en la conexión: {response.status_code}")

                buffer = ""
                async for chunk in response.aiter_text():
                    if chunk.strip():
                        buffer += chunk
                        # Extraer tokens individuales (simplificado)
                        yield buffer

        except Exception as e:
            logger.error(f"Error en el streaming: {str(e)}")
            raise

    async def close(self):
        """Cierra el cliente HTTP."""
        await self.client.aclose()


# --- Endpoint FastAPI ---
async def stream_chat_endpoint(messages: list[ChatMessage]) -> AsyncGenerator[str, None]:
    """Endpoint para streaming de chat con HuggingFace Spaces."""
    config = StreamConfig.from_env()
    connector = HFSpaceConnector(config)

    try:
        async for token in connector.stream_chat(messages):
            yield token
    finally:
        await connector.close()
