#!/usr/bin/env python3
"""
AURA Proxy Chat Connector v2 — Pipeline inteligente multi-proveedor con fallback automático.
=============================================================================
Pilar #2: Conector inteligente con fallback automático.
Pilar #3: Loop Engineering incorporado en la arquitectura.

Flujo de fallback:
  OpenRouter Free (meta-llama/llama-3-8b-instruct:free)
  -> Google Gemini (gemini-2.0-flash-exp)
  -> LM Studio Local (http://localhost:1234/v1)
  -> Proxy Legacy (Cerebras)
"""

import os
import json
import logging
import asyncio
from typing import AsyncGenerator, Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import httpx

# Cargar configuración centralizada desde el nuevo módulo ai_config
from core.ai_config import AIConfig, AIProvider, get_config
from core.hf_space_connector import (
    StreamConfig,
    HFSpaceConnector,
    ChatMessage,
)  # Importar clases para HF Space

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FallbackError(Exception):
    """Error que dispara un cambio de proveedor en la cadena de fallback."""

    def __init__(self, provider_name: str, reason: str, status_code: Optional[int] = None):
        self.provider_name = provider_name
        self.reason = reason
        self.status_code = status_code
        super().__init__(f"[{provider_name}] {reason} (HTTP {status_code})")


# Umbrales para considerar que un proveedor falló por cuota o conectividad
QUOTA_STATUS_CODES = {429, 402, 403}
CONNECTION_ERROR_MARKERS = [
    "quota",
    "rate limit",
    "insufficient",
    "credit",
    "billing",
    "too many requests",
    "over quota",
    "capacity",
    "timeout",
    "connection refused",
    "connection error",
    "reset by peer",
]


class ProxyChatMessage:
    """Clase para manejar mensajes de chat."""

    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content

    def to_dict(self) -> Dict:
        return {"role": self.role, "content": self.content}


class ProxyChatConnector:
    """
    Maneja la lógica de fallback y enrutamiento para diferentes proveedores de chat.
    Integra OpenRouter, Google Gemini, LM Studio y HuggingFace Spaces.
    """

    def __init__(self):
        self.ai_config: AIConfig = get_config()

        # Configuración e inicialización del conector HF Space
        self.hf_config = StreamConfig.from_env()
        self.hf_connector: Optional[HFSpaceConnector] = None

        if self.hf_config.is_configured():
            self.hf_connector = HFSpaceConnector(self.hf_config)
            logger.info("HF Space Connector inicializado y configurado.")
        else:
            logger.warning(
                "HF Space URL no configurada en el entorno. HF Space Connector no se activará."
            )

    async def _try_provider_chat_streaming(
        self,
        client: httpx.AsyncClient,
        provider: AIProvider,
        messages: List[Dict],
        **kwargs,
    ) -> AsyncGenerator[Tuple[bool, Optional[str], Optional[str], Optional[int]], None]:
        """
        Intenta una llamada a un proveedor específico en modo streaming.
        Retorna: (éxito, token_generado, error_msg, status_code)
        """
        if not provider.enabled:
            yield (False, None, f"Provider '{provider.name}' not enabled (no API key)", None)
            return

        if provider.name == "hf_space" and self.hf_connector and self.hf_config.is_configured():
            logger.debug(f"[hf_space] Usando HF Space Connector para modelo: {provider.model}")
            hf_messages = [ChatMessage(role=m["role"], content=m["content"]) for m in messages]
            try:
                async for token in self.hf_connector.stream_chat(hf_messages):
                    yield (True, token, None, 200)
            except Exception as e:
                logger.error(f"[hf_space] Error en streaming: {e}")
                yield (False, None, f"HF Space streaming error: {e}", None)
            return

        # Lógica para otros proveedores (OpenAI-compatible, Gemini) para streaming
        # Similar a _try_provider_chat pero procesando chunks
        endpoint = provider.get_chat_endpoint()
        payload = provider.build_payload(messages, stream=True, **kwargs)  # Asegurar stream=True
        headers = provider.get_headers()

        logger.info(
            f"[{provider.name}] Intentando streaming: {provider.model} en {provider.base_url}"
        )

        try:
            async with client.stream(
                "POST",
                endpoint,
                json=payload,
                headers=headers,
                timeout=httpx.Timeout(provider.timeout),
            ) as response:
                response.raise_for_status()  # Lanza excepción para códigos de error HTTP
                async for chunk in response.aiter_bytes():
                    # Decodificar y procesar chunks SSE
                    try:
                        decoded_chunk = chunk.decode("utf-8")
                        # Aquí se necesita una lógica más robusta para parsear SSE
                        # Esto es un placeholder simplificado
                        if "data: " in decoded_chunk:
                            json_data = decoded_chunk.split("data: ", 1)[1].strip()
                            if json_data == "[DONE]":
                                continue
                            data = json.loads(json_data)
                            content = _extract_content_streaming(data, provider.name)
                            if content:
                                yield (True, content, None, 200)
                    except json.JSONDecodeError:
                        logger.warning(f"[{provider.name}] No JSON en chunk: {decoded_chunk[:100]}")
                        continue  # Ignorar chunks no JSON, pueden ser keepalives o info extra
                    except Exception as e:
                        logger.error(f"[{provider.name}] Error procesando chunk: {e}")
                        yield (False, None, f"Error procesando chunk: {e}", None)
                        return

        except httpx.TimeoutException:
            yield (False, None, f"TIMEOUT after {provider.timeout}s", None)
        except httpx.ConnectError as e:
            yield (False, None, f"CONNECTION REFUSED: {e}", None)
        except httpx.HTTPStatusError as e:
            error_text = e.response.text[:500]
            if _is_quota_error(e.response.status_code, error_text):
                yield (False, None, f"QUOTA ERROR: {error_text}", e.response.status_code)
            else:
                yield (
                    False,
                    None,
                    f"HTTP {e.response.status_code}: {error_text}",
                    e.response.status_code,
                )
        except Exception as e:
            yield (False, None, f"UNEXPECTED: {e}", None)


def _extract_content_streaming(data: Dict, provider_name: str) -> str:
    """Extraer el texto de respuesta de un chunk de streaming."""
    if provider_name == "gemini":
        try:
            # Gemini puede enviar partes o la respuesta completa en un solo chunk
            if "candidates" in data and data["candidates"] and "content" in data["candidates"][0]:
                part = data["candidates"][0]["content"]["parts"][0]
                if "text" in part:
                    return part["text"]
            return ""
        except (KeyError, IndexError):
            logger.warning(f"[gemini] Formato inesperado en chunk: {json.dumps(data)[:200]}")
            return ""
    else:
        # Formato OpenAI-compatible (OpenRouter, LM Studio, Proxy)
        try:
            if "choices" in data and data["choices"] and "delta" in data["choices"][0]:
                return data["choices"][0]["delta"].get("content", "")
            return ""
        except (KeyError, IndexError):
            logger.warning(
                f"[{provider_name}] Formato inesperado en chunk: {json.dumps(data)[:200]}"
            )
            return ""


async def smart_chat_completion(
    messages: List[ProxyChatMessage], provider_override: Optional[str] = None, **kwargs
) -> AsyncGenerator[str, None]:
    """
    Pipeline inteligente de chat completion con streaming y fallback automático.

    Args:
        messages: Lista de mensajes del chat
        provider_override: Forzar un proveedor específico
        **kwargs: Parámetros adicionales (temperature, max_tokens, etc.)

    Returns:
        AsyncGenerator[str, None]: Generador de tokens de respuesta
    """
    config: AIConfig = get_config()
    chain = config.get_fallback_chain()

    if not chain:
        yield "[ERROR] No hay proveedores de IA configurados. Revisa tu archivo .env"
        return

    if provider_override:
        chain = [p for p in chain if p.name == provider_override]
        if not chain:
            yield f"[ERROR] Proveedor '{provider_override}' no encontrado o no configurado"
            return

    msg_dicts = [m.to_dict() if hasattr(m, "to_dict") else m for m in messages]

    errors = []
    async with httpx.AsyncClient() as client:
        for provider in chain:
            logger.info(f"Intentando proveedor de streaming: {provider.name}")
            current_response_content = ""
            try:
                async for (
                    success,
                    token,
                    error_msg,
                    status_code,
                ) in self._try_provider_chat_streaming(client, provider, msg_dicts, **kwargs):
                    if success and token is not None:
                        current_response_content += token
                        yield token
                    elif error_msg:
                        raise FallbackError(provider.name, error_msg, status_code)

                # Si llegamos aquí, el streaming del proveedor actual terminó con éxito
                if current_response_content:  # Asegurarse de que se recibió algo
                    logger.info(
                        f"✅ [{provider.name}] Streaming exitoso. "
                        f"Total chars: {len(current_response_content)}"
                    )
                    return  # Éxito, termina la cadena de fallback

            except FallbackError as e:
                error_entry = f"{e.provider_name}: {e.reason}"
                errors.append(error_entry)
                logger.warning(f"⚠️ Fallback para {e.provider_name}: {e.reason}")
            except Exception as e:  # Captura errores inesperados no manejados por FallbackError
                error_entry = f"{provider.name}: Error inesperado durante streaming: {e}"
                errors.append(error_entry)
                logger.error(f"❌ {error_entry}")

    # Si se llega aquí, todos los proveedores fallaron o no produjeron contenido
    detailed = "; ".join(errors) if errors else "No response from any provider."
    logger.error(f"❌ Todos los proveedores de streaming fallaron: {detailed}")
    yield f"[ERROR] Todos los proveedores de streaming fallaron. Detalles: {detailed}"


async def health_check() -> Dict:
    """Verificar la salud de todos los proveedores."""
    config = get_config()
    summary = config.get_health_summary()

    enabled_count = sum(1 for p in summary["providers"] if p["enabled"])
    total_count = len(summary["providers"])

    if enabled_count == 0:
        return {
            "ok": False,
            "message": "❌ Ningún proveedor configurado. Revisa tu .env",
            "providers": summary["providers"],
        }

    return {
        "ok": True,
        "enabled_providers": enabled_count,
        "total_providers": total_count,
        "fallback_chain": [p["name"] for p in summary["providers"] if p["enabled"]],
        "message": f"✅ {enabled_count}/{total_count} proveedores habilitados",
        "providers": summary["providers"],
    }


async def test_fallback_chain() -> Dict:
    """
    Probar la cadena de fallback completa (sin enviar mensajes reales).
    Útil para diagnostico: verifica conectividad básica con cada proveedor.
    """
    config = get_config()
    chain = config.get_fallback_chain()
    results = []

    async with httpx.AsyncClient() as client:
        for provider in chain:
            if not provider.enabled:
                results.append(
                    {
                        "provider": provider.name,
                        "status": "skipped",
                        "reason": "No API key configured",
                    }
                )
                continue

            try:
                # Health check simple al endpoint de modelos
                headers = provider.get_headers()
                models_url = f"{provider.base_url}/models"
                if provider.name == "gemini":
                    models_url = f"{provider.base_url}/models?key={provider.api_key}"

                resp = await client.get(models_url, headers=headers, timeout=5)
                if resp.status_code == 200:
                    results.append(
                        {
                            "provider": provider.name,
                            "status": "available",
                            "model": provider.model,
                            "latency": "OK",
                        }
                    )
                else:
                    results.append(
                        {
                            "provider": provider.name,
                            "status": "error",
                            "http_code": resp.status_code,
                            "detail": resp.text[:200],
                        }
                    )
            except Exception as e:
                results.append(
                    {"provider": provider.name, "status": "unreachable", "error": str(e)[:200]}
                )

    return {
        "timestamp": str(asyncio.get_event_loop().time()),
        "results": results,
        "all_available": all(r.get("status") == "available" for r in results),
        "any_available": any(r.get("status") == "available" for r in results),
    }


# =====================================================
# NOTA: Loop Engineering se aplica desde test_all_providers.py
# Este conector está diseñado para auto-recuperarse en runtime
# sin necesidad de reiniciar el servidor.
# =====================================================


def _is_quota_error(status_code: int, response_text: str) -> bool:
    """Detectar si el error es por cuota (rate limit, billing, etc.)"""
    text_lower = response_text.lower()
    if status_code in QUOTA_STATUS_CODES:
        return True
    for marker in CONNECTION_ERROR_MARKERS:
        if marker in text_lower:
            return True
    return False


async def _try_provider_chat(
    client: httpx.AsyncClient,
    provider: AIProvider,
    messages: List[Dict],
    stream: bool = True,
    **kwargs,
) -> Tuple[bool, Optional[Dict], Optional[str], Optional[int]]:
    """
    Intentar una llamada a un proveedor específico.
    Retorna: (éxito, respuesta_json, error_msg, status_code)
    """
    if not provider.enabled:
        return False, None, f"Provider '{provider.name}' not enabled (no API key)", None

    endpoint = provider.get_chat_endpoint()
    payload = provider.build_payload(messages, stream=False, **kwargs)
    headers = provider.get_headers()

    logger.info(f"[{provider.name}] Intentando: {provider.model} en {provider.base_url}")

    try:
        # Timeout más generoso para el primer proveedor
        timeout_val = provider.timeout + 15  # +15s de margen

        response = await client.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=timeout_val,
        )

        if response.status_code == 200:
            try:
                data = response.json()
                return True, data, None, 200
            except json.JSONDecodeError as e:
                return False, None, f"JSON decode error: {e}", response.status_code

        # Error: verificar si es de cuota o desconexión
        error_text = response.text[:500]  # Truncar para log
        if _is_quota_error(response.status_code, error_text):
            return False, None, f"QUOTA ERROR: {error_text}", response.status_code

        return False, None, f"HTTP {response.status_code}: {error_text}", response.status_code

    except httpx.TimeoutException:
        return False, None, f"TIMEOUT after {provider.timeout}s", None
    except httpx.ConnectError as e:
        return False, None, f"CONNECTION REFUSED: {e}", None
    except httpx.HTTPError as e:
        return False, None, f"HTTP ERROR: {e}", None
    except Exception as e:
        return False, None, f"UNEXPECTED: {e}", None


def _extract_content(data: Dict, provider_name: str) -> str:
    """Extraer el texto de respuesta del formato específico de cada proveedor."""
    if provider_name == "gemini":
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            logger.warning(f"[gemini] Formato inesperado: {json.dumps(data)[:200]}")
            return "[ERROR] No se pudo extraer contenido de Gemini"
    else:
        # Formato OpenAI-compatible (OpenRouter, LM Studio, Proxy)
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            logger.warning(f"[{provider_name}] Formato inesperado: {json.dumps(data)[:200]}")
            return "[ERROR] No se pudo extraer contenido"


async def smart_chat_completion(
    messages: List[ProxyChatMessage], provider_override: Optional[str] = None, **kwargs
) -> str:
    """
    Pipeline inteligente de chat completion con fallback automático.

    1. Intenta con el proveedor principal (OpenRouter Free)
    2. Si falla por cuota/conexión -> cambia a Gemini
    3. Si Gemini falla -> cambia a LM Studio (local)
    4. Si LM Studio falla -> fallback legacy (Cerebras)

    Args:
        messages: Lista de mensajes del chat
        provider_override: Forzar un proveedor específico
        **kwargs: Parámetros adicionales (temperature, max_tokens, etc.)

    Returns:
        str: Texto de respuesta del primer proveedor exitoso
    """
    config: AIConfig = get_config()
    chain = config.get_fallback_chain()

    if not chain:
        return "[ERROR] No hay proveedores de IA configurados. Revisa tu archivo .env"

    # Si hay override, filtrar la cadena
    if provider_override:
        chain = [p for p in chain if p.name == provider_override]
        if not chain:
            return f"[ERROR] Proveedor '{provider_override}' no encontrado o no configurado"

    # Convertir mensajes a dict
    msg_dicts = [m.to_dict() if hasattr(m, "to_dict") else m for m in messages]

    errors = []
    async with httpx.AsyncClient() as client:
        for provider in chain:
            success, data, error_msg, status = await _try_provider_chat(
                client, provider, msg_dicts, **kwargs
            )

            if success and data:
                content = _extract_content(data, provider.name)
                logger.info(
                    f"✅ [{provider.name}] Éxito con {provider.model} " f"({len(content)} chars)"
                )
                return content

            # Registrar error y continuar con el siguiente proveedor
            error_entry = f"{provider.name}: {error_msg or 'Unknown error'}"
            errors.append(error_entry)
            logger.warning(f"⚠️ Fallback: {error_entry}")

    # Todos los proveedores fallaron
    detailed = "; ".join(errors)
    logger.error(f"❌ Todos los proveedores fallaron: {detailed}")
    return f"[ERROR] Todos los proveedores fallaron. Detalles: {detailed}"


async def health_check() -> Dict:
    """Verificar la salud de todos los proveedores."""
    config = get_config()
    summary = config.get_health_summary()

    enabled_count = sum(1 for p in summary["providers"] if p["enabled"])
    total_count = len(summary["providers"])

    if enabled_count == 0:
        return {
            "ok": False,
            "message": "❌ Ningún proveedor configurado. Revisa tu .env",
            "providers": summary["providers"],
        }

    return {
        "ok": True,
        "enabled_providers": enabled_count,
        "total_providers": total_count,
        "fallback_chain": [p["name"] for p in summary["providers"] if p["enabled"]],
        "message": f"✅ {enabled_count}/{total_count} proveedores habilitados",
        "providers": summary["providers"],
    }


async def test_fallback_chain() -> Dict:
    """
    Probar la cadena de fallback completa (sin enviar mensajes reales).
    Útil para diagnostico: verifica conectividad básica con cada proveedor.
    """
    config = get_config()
    chain = config.get_fallback_chain()
    results = []

    async with httpx.AsyncClient() as client:
        for provider in chain:
            if not provider.enabled:
                results.append(
                    {
                        "provider": provider.name,
                        "status": "skipped",
                        "reason": "No API key configured",
                    }
                )
                continue

            try:
                # Health check simple al endpoint de modelos
                headers = provider.get_headers()
                models_url = f"{provider.base_url}/models"
                if provider.name == "gemini":
                    models_url = f"{provider.base_url}/models?key={provider.api_key}"

                resp = await client.get(models_url, headers=headers, timeout=5)
                if resp.status_code == 200:
                    results.append(
                        {
                            "provider": provider.name,
                            "status": "available",
                            "model": provider.model,
                            "latency": "OK",
                        }
                    )
                else:
                    results.append(
                        {
                            "provider": provider.name,
                            "status": "error",
                            "http_code": resp.status_code,
                            "detail": resp.text[:200],
                        }
                    )
            except Exception as e:
                results.append(
                    {"provider": provider.name, "status": "unreachable", "error": str(e)[:200]}
                )

    return {
        "timestamp": str(asyncio.get_event_loop().time()),
        "results": results,
        "all_available": all(r.get("status") == "available" for r in results),
        "any_available": any(r.get("status") == "available" for r in results),
    }


# =====================================================
# NOTA: Loop Engineering se aplica desde test_all_providers.py
# Este conector está diseñado para auto-recuperarse en runtime
# sin necesidad de reiniciar el servidor.
# =====================================================
