"""
Cloud Router — Inferencia Serverless en Hugging Face Hub
=========================================================
Reemplaza el endpoint local de LM Studio por la API cloud de HF.
Usa dos modelos especializados:
  - Qwen/Qwen2.5-Coder-7B-Instruct  → codigo/desarrollo
  - NousResearch/Hermes-3-Llama-3.1-8B → agente/conversacion/personalidad

Requiere: HF_TOKEN en .env
Formato de respuesta compatible con OpenAI para que AURA no se rompa.
"""

import os
import json
import asyncio
import logging
from typing import Optional, Dict
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

logger = logging.getLogger(__name__)

HF_API_BASE = "https://api-inference.huggingface.co/models"
HF_TOKEN = os.getenv("HF_TOKEN", "")

MODELS = {
    "coder": "Qwen/Qwen2.5-Coder-7B-Instruct",
    "agent": "NousResearch/Hermes-3-Llama-3.1-8B",
}


class HFCloudRouter:
    """Enrutador cloud via Hugging Face Inference API (Serverless)."""

    def __init__(self):
        self._token = HF_TOKEN
        if not self._token:
            logger.warning("HF_TOKEN no configurado. El router cloud fallara.")

    def _headers(self) -> Dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def _build_payload(self, prompt: str, system_context: str = "") -> Dict:
        """Construye payload en formato OpenAI compatible."""
        messages = []
        if system_context:
            messages.append({"role": "system", "content": system_context})
        messages.append({"role": "user", "content": prompt})
        return {
            "inputs": messages,
            "parameters": {
                "temperature": 0.2,
                "max_new_tokens": 2048,
                "return_full_text": False,
            },
        }

    async def generate(
        self, prompt: str, model_key: str = "coder", system_context: str = ""
    ) -> str:
        """
        Envia una peticion a HF Inference API.
        model_key: 'coder' para Qwen, 'agent' para Hermes.
        Retorna el texto generado o un mensaje de error.
        """
        if not self._token:
            return "ERROR_CONFIG: HF_TOKEN no configurado en .env"

        model_id = MODELS.get(model_key)
        if not model_id:
            return f"ERROR_CONFIG: modelo '{model_key}' no encontrado. Usa: coder, agent"

        url = f"{HF_API_BASE}/{model_id}"
        payload = self._build_payload(prompt, system_context)

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(url, json=payload, headers=self._headers(), timeout=120),
            )

            if response.status_code == 200:
                data = response.json()
                # Formato HF: lista de dicts con "generated_text"
                if isinstance(data, list) and len(data) > 0:
                    if isinstance(data[0], dict) and "generated_text" in data[0]:
                        return data[0]["generated_text"].strip()
                    # Si es lista de listas (algunos modelos)
                    if isinstance(data[0], list) and len(data[0]) > 0:
                        return data[0][0].get("generated_text", "").strip()
                return str(data).strip()

            elif response.status_code == 503:
                return "ERROR_MODELO: El modelo esta cargando en HF (503). Espera unos segundos y reintenta."
            else:
                return f"ERROR_HTTP: {response.status_code} - {response.text[:200]}"

        except requests.exceptions.ConnectionError:
            return "ERROR_CONEXION: No se pudo conectar con Hugging Face API."
        except requests.exceptions.Timeout:
            return "ERROR_TIMEOUT: La inferencia en HF supero el tiempo limite (120s)."
        except Exception as e:
            return f"ERROR_INFERENCIA: {str(e)}"

    async def generate_code(self, prompt: str, system_context: str = "") -> str:
        """Atajo para generar codigo con Qwen Coder."""
        ctx = (
            system_context
            or "Eres un ingeniero de software experto. Devuelve SOLO codigo limpio de Python, sin explicaciones."
        )
        return await self.generate(prompt, model_key="coder", system_context=ctx)

    async def generate_chat(self, prompt: str, system_context: str = "") -> str:
        """Atajo para conversacion/agente con Hermes."""
        ctx = (
            system_context
            or "Eres un asistente util, directo y con personalidad. Responde en el mismo idioma que te hablan."
        )
        return await self.generate(prompt, model_key="agent", system_context=ctx)


async def test_connection() -> Dict:
    """Test rapido: verifica que HF_TOKEN existe."""
    token_ok = bool(HF_TOKEN)
    return {
        "hf_configured": token_ok,
        "models_available": list(MODELS.keys()),
        "models": MODELS,
        "token_present": token_ok,
    }
