"""
AURA_Core/automation/n8n_bridge.py
Puente de webhooks para N8N - Despacha cargas útiles de eventos internos de AURA
hacia una instancia de N8N (local o remota) para orquestación multi-agente.

Métodos principales:
  - trigger_gmail_automation(data): Enviar alertas/correos automatizados
  - trigger_agent_workflow(prompt, context): Delegar subtareas complejas a N8N
"""

import os
import json
import logging
import asyncio
from typing import Any, Dict, Optional, Callable
from datetime import datetime

try:
    import aiohttp

    _HAVE_AIOHTTP = True
except ImportError:
    _HAVE_AIOHTTP = False

try:
    import requests

    _HAVE_REQUESTS = True
except ImportError:
    _HAVE_REQUESTS = False


logger = logging.getLogger("N8NBridge")


class N8NBridge:
    """
    Puente de comunicación asíncrona con N8N.

    Configuración vía variables de entorno:
      N8N_BASE_URL        - URL base de N8N (default: http://localhost:5678)
      N8N_WEBHOOK_PREFIX  - Prefijo para webhooks (default: webhook)
      N8N_API_KEY         - API Key opcional para autenticación
      N8N_TIMEOUT         - Timeout en segundos (default: 10)
    """

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (
            base_url or os.environ.get("N8N_BASE_URL", "http://localhost:5678")
        ).rstrip("/")
        self.webhook_prefix = os.environ.get("N8N_WEBHOOK_PREFIX", "webhook")
        self.api_key = os.environ.get("N8N_API_KEY", "")
        self.timeout = int(os.environ.get("N8N_TIMEOUT", "10"))

        # Callbacks para notificar al EventManager cuando N8N responde
        self._response_callbacks: Dict[str, Callable] = {}

        logger.info(f"N8NBridge inicializado -> {self.base_url}/{self.webhook_prefix}/*")

    # ──────────────────────────────────────────
    # Webhooks predefinidos de N8N
    # ──────────────────────────────────────────

    def trigger_gmail_automation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispara un flujo de N8N para enviar alertas o correos automatizados.

        Args:
            data: Diccionario con al menos:
                - to: destinatario del correo
                - subject: asunto
                - body: cuerpo del mensaje
                - priority: (opcional) "low" | "normal" | "high"

        Returns:
            Respuesta de N8N como dict
        """
        payload = {
            "event": "gmail_automation",
            "timestamp": datetime.utcnow().isoformat(),
            "source": "AURA_Core",
            "data": {
                "to": data.get("to", "aura@local"),
                "subject": data.get("subject", "AURA Notification"),
                "body": data.get("body", ""),
                "priority": data.get("priority", "normal"),
                "attachments": data.get("attachments", []),
            },
        }
        return self._dispatch_webhook("gmail", payload)

    def trigger_agent_workflow(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delega una subtarea compleja de orquestación multi-agente a N8N.

        Args:
            prompt: Instrucción para el agente de N8N
            context: Contexto adicional (estado del sistema, datos de telemetría, etc.)

        Returns:
            Resultado del workflow de N8N
        """
        payload = {
            "event": "agent_workflow",
            "timestamp": datetime.utcnow().isoformat(),
            "source": "AURA_Core",
            "data": {
                "prompt": prompt,
                "context": context,
                "prefer_local": os.environ.get("AI_PROVIDER_PREFERENCE", "auto"),
            },
        }
        return self._dispatch_webhook("agent", payload)

    def trigger_event_replication(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """
        Replica eventos críticos del EventManager a N8N de forma asíncrona (fire & forget).

        Args:
            event_type: Tipo de evento (ej: "low_battery", "high_cpu", "security_alert")
            event_data: Payload del evento
        """
        payload = {
            "event": "event_replication",
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "source": "AURA_EventManager",
            "data": event_data,
        }
        # Disparo asíncrono, no bloqueante
        try:
            if _HAVE_AIOHTTP:
                asyncio.create_task(self._dispatch_async("event", payload))
            else:
                # Fallback síncrono con timeout corto para no bloquear el EventBus
                import threading

                t = threading.Thread(
                    target=self._dispatch_webhook,
                    args=("event", payload),
                    daemon=True,
                )
                t.start()
        except Exception as e:
            logger.warning(f"Event replication a N8N falló (no crítico): {e}")

    # ──────────────────────────────────────────
    # Dispatch interno
    # ──────────────────────────────────────────

    def _dispatch_webhook(self, workflow: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Envía un webhook a N8N usando requests (síncrono)."""
        if not _HAVE_REQUESTS:
            logger.error("requests no está instalado. No se puede enviar webhook a N8N.")
            return {"status": "error", "message": "requests not available"}

        url = f"{self.base_url}/{self.webhook_prefix}/{workflow}"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "AURA-Core-N8N-Bridge/1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            logger.info(f"N8N webhook -> {url}")
            r = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            if r.status_code in (200, 201):
                result = r.json() if r.text else {"status": "ok"}
                logger.info(f"N8N responded OK: {workflow}")
                return {"status": "ok", "workflow": workflow, "result": result}
            else:
                logger.warning(f"N8N HTTP {r.status_code}: {r.text[:200]}")
                return {
                    "status": "error",
                    "code": r.status_code,
                    "message": r.text[:200],
                }
        except requests.ConnectionError as e:
            logger.warning(f"N8N no disponible ({self.base_url}): {e}")
            return {"status": "unavailable", "message": str(e)}
        except requests.Timeout:
            logger.warning(f"N8N timeout ({self.timeout}s) en {workflow}")
            return {"status": "timeout", "message": f"Timeout after {self.timeout}s"}
        except Exception as e:
            logger.error(f"Error enviando webhook a N8N: {e}")
            return {"status": "error", "message": str(e)}

    async def _dispatch_async(self, workflow: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Envía un webhook a N8N usando aiohttp (asíncrono)."""
        if not _HAVE_AIOHTTP:
            return self._dispatch_webhook(workflow, payload)

        url = f"{self.base_url}/{self.webhook_prefix}/{workflow}"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "AURA-Core-N8N-Bridge/1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as resp:
                    if resp.status in (200, 201):
                        text = await resp.text()
                        result = json.loads(text) if text else {"status": "ok"}
                        logger.info(f"N8N async OK: {workflow}")
                        return {"status": "ok", "workflow": workflow, "result": result}
                    else:
                        text = await resp.text()
                        logger.warning(f"N8N async HTTP {resp.status}: {text[:200]}")
                        return {"status": "error", "code": resp.status, "message": text[:200]}
        except asyncio.TimeoutError:
            logger.warning(f"N8N async timeout en {workflow}")
            return {"status": "timeout", "message": f"Timeout after {self.timeout}s"}
        except Exception as e:
            logger.error(f"Error N8N async: {e}")
            return {"status": "error", "message": str(e)}

    def register_callback(self, workflow: str, callback: Callable) -> None:
        """Registra un callback para ser invocado cuando N8N responda."""
        self._response_callbacks[workflow] = callback
        logger.debug(f"Callback registrado para workflow: {workflow}")


# Singleton global
n8n_bridge = N8NBridge()
