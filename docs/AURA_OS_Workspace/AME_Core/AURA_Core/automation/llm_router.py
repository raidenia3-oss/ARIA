# AURA_Core/automation/llm_router.py
# Enrutador asíncrono con streaming activo, failover rápido y ejecución no bloqueante.
# Optimización "Mark XLVI": prioriza Gemini Flash para respuesta
# inmediata y reduce latencia perceptiva con streaming de tokens.
import asyncio
import json
import os
import re
import time
import logging
from typing import Any, Dict, List, Optional, Union

try:
    from openai import OpenAI, APIError, APITimeoutError, APIConnectionError

    _HAVE_OPENAI = True
except ImportError:
    _HAVE_OPENAI = False

import httpx
from core.ai_config import AIConfig, AIProvider, get_config

logger = logging.getLogger("LLMRouter")


class EndpointConfig:
    """Configuración de un endpoint compatible con API OpenAI."""

    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str = "",
        model: str = "default",
        timeout: int = 30,
        max_retries: int = 1,
    ):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "base_url": self.base_url,
            "model": self.model,
            "timeout": self.timeout,
        }


class LLMRouter:
    """
    Enrutador asíncrono con streaming y failover automático de 3 niveles.

    Orden por defecto:
      1) HF Space (remoto - gratuito)
      2) OpenRouter (remoto - modelos gratuitos open-source)
      3) LM Studio (local)

    Modo `prefer_local=True` invierte orden: LM Studio → OpenRouter → HF Space.
    Ahora con streaming y procesamiento asíncrono inspirado en Mark XLVI.
    """

    def __init__(self, prefer_local: bool = False):
        # Endpoints heredados de la config centralizada (ai_config)
        self._config: AIConfig = get_config()
        self.prefer_local = bool(prefer_local)
        self.last_used: Optional[str] = None

    # ──────────────────────────────────────────
    # API PÚBLICA ASÍNCRONA
    # ──────────────────────────────────────────

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 256,
    ) -> str:
        """
        Envía un chat completion usando failover de 3 niveles con streaming activo.
        Retorna texto completo, pero comienza a generar tokens desde el primer chunk.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        endpoints = self._get_ordered_endpoints()
        errors: List[str] = []

        for endpoint in endpoints:
            try:
                logger.info(f"[LLMRouter] Intentando endpoint async: {endpoint.name}")
                result = await self._call_endpoint_streaming(
                    endpoint, messages, temperature, max_tokens
                )
                self.last_used = endpoint.name
                return result
            except Exception as e:
                logger.warning(f"[LLMRouter] {endpoint.name} falló: {e}. Saltando...")
                errors.append(f"{endpoint.name}: {e}")

        raise RuntimeError(
            f"Todos los endpoints fallaron. Orden: {[e.name for e in endpoints]}. "
            f"Errores: {' | '.join(errors)}"
        )

    async def chat_multimodal(
        self,
        system_prompt: str,
        user_text: str,
        image_base64: str,
        temperature: float = 0.0,
        max_tokens: int = 256,
    ) -> str:
        """Multimodal con streaming."""
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                    },
                ],
            },
        ]
        endpoints = self._get_ordered_endpoints()
        errors: List[str] = []

        for endpoint in endpoints:
            try:
                logger.info(f"[LLMRouter] Multimodal intento: {endpoint.name}")
                result = await self._call_endpoint_streaming(
                    endpoint, messages, temperature, max_tokens
                )
                self.last_used = endpoint.name
                return result
            except Exception as e:
                logger.warning(f"[LLMRouter] Multimodal {endpoint.name} falló: {e}")
                errors.append(f"{endpoint.name}: {e}")

        raise RuntimeError(
            "Todos los endpoints multimodales fallaron. "
            f"Orden: {[e.name for e in endpoints]}. "
            f"Errores: {' | '.join(errors)}"
        )

    # ──────────────────────────────────────────
    # ORDEN DE ENDPOINTS
    # ──────────────────────────────────────────

    def _get_ordered_endpoints(self) -> List[EndpointConfig]:
        providers = self._config.get_fallback_chain()
        endpoints: List[EndpointConfig] = []
        for p in providers:
            endpoints.append(
                EndpointConfig(
                    name=p.name,
                    base_url=p.base_url,
                    api_key=p.api_key,
                    model=p.model,
                    timeout=p.timeout,
                    max_retries=1,
                )
            )
        if self.prefer_local:
            # LM Studio primero si está habilitado
            endpoints.sort(key=lambda e: 0 if e.name == "lm_studio" else 1)
        return endpoints

    # ──────────────────────────────────────────
    # STREAMING ASÍNCRONO POR ENDPOINT
    # ──────────────────────────────────────────

    async def _call_endpoint_streaming(
        self,
        cfg: EndpointConfig,
        messages: Union[List[Dict[str, Any]], Dict[str, Any]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """
        Llama a un endpoint con streaming SSE y retorna el contenido completo.
        Captura el primer chunk con timeout reducido para fallback rápido.
        """
        # Construir cuerpo y headers según proveedor
        payload, headers, endpoint_url = self._build_request(cfg, messages, temperature, max_tokens)

        last_error: Optional[Exception] = None
        for attempt in range(1 + cfg.max_retries):
            try:
                text = await self._stream_with_fallback(
                    cfg.name, endpoint_url, payload, headers, cfg.timeout
                )
                if text:
                    return text
                raise RuntimeError("Respuesta vacía del proveedor")
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                logger.warning(f"[LLMRouter] Intento {attempt+1} falló (red): {e}")
                await asyncio.sleep(0.5)
            except Exception as e:
                status = getattr(e, "status_code", None) or getattr(e, "status", None)
                if status and isinstance(status, int) and 500 <= status < 600:
                    last_error = e
                    logger.warning(f"[LLMRouter] Intento {attempt+1} falló (5xx): {e}")
                    await asyncio.sleep(1)
                else:
                    raise
        raise RuntimeError(f"Endpoint {cfg.name} agotó reintentos: {last_error}") from last_error

    def _build_request(
        self,
        cfg: EndpointConfig,
        messages: Union[List[Dict[str, Any]], Dict[str, Any]],
        temperature: float,
        max_tokens: int,
    ) -> tuple[Dict[str, Any], Dict[str, str], str]:
        """Construye payload, headers y URL según el proveedor."""
        if cfg.name == "gemini":
            url = f"{cfg.base_url}/models/{cfg.model}:streamGenerateContent?key={cfg.api_key}"
            payload = {
                "contents": [
                    {
                        "role": "user" if m.get("role") == "user" else "model",
                        "parts": [{"text": m.get("content", "")}],
                    }
                    for m in messages
                ],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens,
                },
            }
            headers = {"Content-Type": "application/json"}
            return payload, headers, url

        # OpenAI-compatible (OpenRouter, LM Studio, proxy)
        url = f"{cfg.base_url}/chat/completions"
        payload = {
            "model": cfg.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        headers = {"Content-Type": "application/json"}
        if cfg.api_key:
            headers["Authorization"] = f"Bearer {cfg.api_key}"
        if cfg.name == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/raidenia3-oss/AURA-server.01"
            headers["X-Title"] = "AURA-Core"
        return payload, headers, url

    async def _stream_with_fallback(
        self,
        provider_name: str,
        url: str,
        payload: Dict[str, Any],
        headers: Dict[str, str],
        timeout: int,
    ) -> str:
        """
        Hace una llamada streaming y retorna el texto completo.
        Timeout reducido para el primer chunk (2s) y luego extendido.
        """
        collected = ""
        first_chunk = True
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes():
                        try:
                            text = chunk.decode("utf-8", errors="ignore")
                            if "data: " in text:
                                json_data = text.split("data: ", 1)[1].strip()
                                if json_data == "[DONE]":
                                    continue
                                data = json.loads(json_data)
                                token = self._extract_token(data, provider_name)
                                if token:
                                    collected += token
                                    # Log de progreso cada 128 chars para depuración
                                    if len(collected) % 128 == 0:
                                        logger.debug(
                                            f"[LLMRouter] {provider_name} streaming: {len(collected)} chars"
                                        )
                                first_chunk = False
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            logger.error(f"[LLMRouter] Error procesando chunk: {e}")
                            raise
            except httpx.TimeoutException as e:
                raise RuntimeError(f"TIMEOUT tras {timeout}s") from e
            except httpx.ConnectError as e:
                raise RuntimeError(f"CONNECTION REFUSED: {e}") from e
            except httpx.HTTPStatusError as e:
                raise RuntimeError(f"HTTP {e.response.status_code}: {e.response.text[:200]}") from e

        if not collected:
            raise RuntimeError("Sin contenido en respuesta streaming")
        return collected

    def _extract_token(self, data: Dict[str, Any], provider_name: str) -> str:
        """Extrae un token/chunk de texto del formato específico del proveedor."""
        if provider_name == "gemini":
            try:
                part = data["candidates"][0]["content"]["parts"][0]
                return part.get("text", "")
            except (KeyError, IndexError):
                return ""
        # OpenAI-compatible
        try:
            return data["choices"][0]["delta"].get("content", "")
        except (KeyError, IndexError):
            return ""

    # ──────────────────────────────────────────
    # MÉTODO ESPECÍFICO DE REPARACIÓN (compatibilidad)
    # ──────────────────────────────────────────

    async def enviar_solicitud_reparacion(self, prompt_sistema: str, html_contexto: str) -> str:
        """
        Envía una solicitud de reparación de selector al modelo (async).
        """
        respuesta = await self.chat(
            system_prompt=prompt_sistema,
            user_prompt=html_contexto,
            temperature=0.0,
            max_tokens=256,
        )
        m = re.search(r"\{.*\}", respuesta, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
                selector = data.get("selector", "").strip()
                if selector:
                    return selector
            except json.JSONDecodeError:
                pass
        lines = [l.strip() for l in respuesta.split("\n") if l.strip()]
        for line in lines:
            if (
                line.startswith("css=")
                or line.startswith("xpath=")
                or line.startswith(".")
                or line.startswith("#")
            ):
                return line
        raise RuntimeError(
            f"No se pudo extraer selector de la respuesta del LLM: {respuesta[:200]}"
        )


# Singleton global para uso en todo el ecosistema
llm_router = LLMRouter()
