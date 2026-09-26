#!/usr/bin/env python3
"""
local_llm_router.py - Router de inferencia local para LM Studio (Gemma 4)
Este script gestiona las llamadas de inferencia dirigidas a un servidor local de LM Studio
expuesto en 'http://localhost:1234/v1' con formato OpenAI API.
Incluye un mecanismo de fallback automático a la API de la nube si el servidor local no responde.
"""

import os
import logging
import requests
import json
from typing import Optional, Dict, Any
from urllib.parse import urljoin

# Configuración global
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
LOGGER.addHandler(logging.StreamHandler())

# Configuración de endpoints
LOCAL_LLM_URL = os.getenv("LOCAL_LLM_URL", "http://localhost:1234/v1")
CLOUD_LLM_URL = os.getenv("CLOUD_LLM_URL", "https://api.openai.com/v1")
LOCAL_LLM_TIMEOUT = int(os.getenv("LOCAL_LLM_TIMEOUT", "3"))  # 3 segundos
LOCAL_LLM_RETRY = int(os.getenv("LOCAL_LLM_RETRY", "1"))

# Configuración de headers
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
}

class LocalLLMRouter:
    """
    Router de inferencia local para LM Studio con fallback a la nube.
    """

    def __init__(self):
        self.local_llm_available = False
        self._check_local_llm_availability()

    def _check_local_llm_availability(self) -> bool:
        """Verifica si el servidor local de LM Studio está disponible."""
        try:
            response = requests.get(
                urljoin(LOCAL_LLM_URL, "models"),
                headers=HEADERS,
                timeout=LOCAL_LLM_TIMEOUT
            )
            if response.status_code == 200:
                self.local_llm_available = True
                LOGGER.info("✅ Servidor local de LM Studio disponible en %s", LOCAL_LLM_URL)
                return True
            else:
                LOGGER.warning("⚠️ Servidor local de LM Studio no respondió correctamente (HTTP %s)", response.status_code)
                return False
        except requests.exceptions.RequestException as e:
            LOGGER.warning("⚠️ Error al verificar disponibilidad del servidor local: %s", e)
            return False

    def _call_local_llm(self, endpoint: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Realiza una llamada al servidor local de LM Studio."""
        try:
            url = urljoin(LOCAL_LLM_URL, endpoint)
            response = requests.post(
                url,
                headers=HEADERS,
                json=payload,
                timeout=LOCAL_LLM_TIMEOUT
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            LOGGER.error("❌ Error al llamar al servidor local: %s", e)
            return None

    def _call_cloud_llm(self, endpoint: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Realiza una llamada a la API de la nube (fallback)."""
        try:
            url = urljoin(CLOUD_LLM_URL, endpoint)
            response = requests.post(
                url,
                headers=HEADERS,
                json=payload,
                timeout=LOCAL_LLM_TIMEOUT * 2  # Timeout más largo para la nube
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            LOGGER.error("❌ Error al llamar a la API de la nube: %s", e)
            return None

    def _should_use_local(self) -> bool:
        """Determina si se debe usar el servidor local o el fallback a la nube."""
        return self.local_llm_available

    def chat_completion(self, model: str, messages: list, **kwargs) -> Dict[str, Any]:
        """
        Realiza una llamada de chat completion con fallback automático.
        """
        payload = {
            "model": model,
            "messages": messages,
            **(kwargs or {})
        }

        # Intentar usar el servidor local primero
        if self._should_use_local():
            result = self._call_local_llm("chat/completions", payload)
            if result is not None:
                return result

        # Si el local falla, usar el fallback a la nube
        LOGGER.warning("🔄 Usando fallback a la API de la nube (LM Studio no disponible)")
        return self._call_cloud_llm("chat/completions", payload) or {}

    def embeddings(self, model: str, input: str, **kwargs) -> Dict[str, Any]:
        """
        Realiza una llamada de embeddings con fallback automático.
        """
        payload = {
            "model": model,
            "input": input,
            **(kwargs or {})
        }

        # Intentar usar el servidor local primero
        if self._should_use_local():
            result = self._call_local_llm("embeddings", payload)
            if result is not None:
                return result

        # Si el local falla, usar el fallback a la nube
        LOGGER.warning("🔄 Usando fallback a la API de la nube (LM Studio no disponible)")
        return self._call_cloud_llm("embeddings", payload) or {}

    def check_availability(self) -> bool:
        """Verifica la disponibilidad del servidor local de LM Studio."""
        return self._check_local_llm_availability()

def test_local_llm_router():
    """Prueba el router de LM Studio con una petición de ejemplo."""
    router = LocalLLMRouter()

    # Verificar disponibilidad
    if not router.check_availability():
        LOGGER.warning("⚠️ El servidor local de LM Studio no está disponible. Usando fallback a la nube.")

    # Ejemplo de petición de chat
    test_messages = [
        {"role": "system", "content": "Eres un asistente de procesamiento de datos técnicos."},
        {"role": "user", "content": "Analiza este JSON sucio y devuelve una estructura limpia: {\"data\": [\"raw\", \"json\", \"sin\", \"formato\"]}"}
    ]

    try:
        response = router.chat_completion(
            model="gemma-4",
            messages=test_messages,
            max_tokens=100,
            temperature=0.7
        )
        LOGGER.info("📋 Respuesta del modelo:")
        LOGGER.info(json.dumps(response, indent=2))
    except Exception as e:
        LOGGER.error("❌ Error en la prueba: %s", e)

if __name__ == "__main__":
    test_local_llm_router()