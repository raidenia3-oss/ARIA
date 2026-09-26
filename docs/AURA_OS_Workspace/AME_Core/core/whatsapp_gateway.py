#!/usr/bin/env python3
"""
whatsapp_gateway.py - Pasarela de WhatsApp con Anti-Ban
Integra Baileys para API auto-alojada con cola de mensajes y retraso aleatorio.
"""

import os
import time
import random
import asyncio
import logging
import httpx
from datetime import datetime
from typing import Dict, List, Optional
from collections import deque

logger = logging.getLogger(__name__)


class WhatsAppGateway:
    """Gateway de WhatsApp con protección anti-ban mediante cola de mensajes."""

    def __init__(self):
        self.api_url = os.getenv("WHATSAPP_API_URL", "http://localhost:3001")
        self.session_id = os.getenv("WHATSAPP_SESSION_ID", "default")
        self.enabled = os.getenv("WHATSAPP_ENABLED", "false").lower() == "true"
        self._queue: deque = deque()
        self._processing = False
        self._last_sent = 0.0
        self._min_delay = 5.0
        self._max_delay = 9.0

    def enqueue_message(self, to: str, text: str, metadata: Optional[Dict] = None) -> Dict:
        """
        Encolar un mensaje para enviar por WhatsApp.
        Retorna inmediatamente con un tracking ID.
        """
        msg = {
            "id": f"wa_{int(time.time()*1000)}_{random.randint(1000,9999)}",
            "to": to,
            "text": text,
            "meta": metadata or {},
            "queued_at": datetime.now().isoformat(),
            "status": "queued",
        }
        self._queue.append(msg)
        logger.info(f"[WA] Mensaje encolado: {msg['id']} -> {to}")
        return {"queue_id": msg["id"], "status": "queued"}

    async def _process_queue(self):
        """Procesar la cola con retraso aleatorio anti-ban."""
        if self._processing:
            return
        self._processing = True
        try:
            while self._queue:
                msg = self._queue[0]
                delay = random.uniform(self._min_delay, self._max_delay)
                logger.info(f"[WA] Esperando {delay:.2f}s antes de enviar {msg['id']}")
                await asyncio.sleep(delay)
                try:
                    await self._send_message(msg)
                    msg["status"] = "sent"
                    msg["sent_at"] = datetime.now().isoformat()
                    self._queue.popleft()
                    self._last_sent = time.time()
                except Exception as e:
                    logger.error(f"[WA] Error enviando {msg['id']}: {e}")
                    msg["status"] = "error"
                    msg["error"] = str(e)
                    # Reintentar una vez
                    await asyncio.sleep(2)
        finally:
            self._processing = False

    async def _send_message(self, msg: Dict) -> bool:
        """
        Enviar mensaje a la API de WhatsApp (Baileys o proveedor conectado).
        """
        if not self.enabled:
            logger.warning("[WA] Gateway deshabilitado")
            return False

        payload = {
            "session": self.session_id,
            "to": msg["to"],
            "message": msg["text"],
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.api_url}/api/send-message",
                    json=payload,
                )
                if resp.status_code in (200, 201):
                    logger.info(f"[WA] Enviado OK: {msg['id']}")
                    return True
                else:
                    logger.error(f"[WA] Error API {resp.status_code}: {resp.text}")
                    return False
        except Exception as e:
            logger.error(f"[WA] Error de conexión: {e}")
            return False

    async def get_session_status(self) -> Dict:
        """Consultar estado de la sesión de WhatsApp."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.api_url}/api/status/{self.session_id}")
                if resp.status_code == 200:
                    return resp.json()
                return {"status": "unknown", "connected": False}
        except Exception as e:
            logger.error(f"[WA] Error consultando estado: {e}")
            return {"status": "error", "connected": False}

    def queue_size(self) -> int:
        return len(self._queue)


# Instancia global
_wa_gateway = WhatsAppGateway()


def get_whatsapp_gateway() -> WhatsAppGateway:
    return _wa_gateway
