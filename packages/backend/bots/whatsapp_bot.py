# -*- coding: utf-8 -*-
"""AURA OS — WhatsApp Bot (Twilio Integration).

Recibe y envia mensajes WhatsApp via Twilio API.
Conecta a AURA backend para procesar comandos.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURA.WhatsAppBot")


class WhatsAppBot:
    """WhatsApp bot via Twilio API."""

    def __init__(self, account_sid: Optional[str] = None, auth_token: Optional[str] = None, whatsapp_number: Optional[str] = None) -> None:
        self.account_sid = account_sid or "TWILIO_ACCOUNT_SID"
        self.auth_token = auth_token or "TWILIO_AUTH_TOKEN"
        self.whatsapp_number = whatsapp_number or "+51942858492"
        self.client: Optional[Any] = None
        self.active: bool = False
        self.messages_processed: int = 0
        self.users_connected: List[str] = []
        self._message_log: List[Dict[str, Any]] = []
        self._command_handlers: Dict[str, callable] = {}
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        self._command_handlers = {
            "/fanfic": self._cmd_fanfic,
            "/search": self._cmd_search,
            "/marketplace": self._cmd_marketplace,
            "/stats": self._cmd_stats,
            "/netrunner": self._cmd_netrunner,
            "/ask": self._cmd_ask,
            "/help": self._cmd_help,
            "/status": self._cmd_status,
        }

    async def receive_message(self, from_number: str, body: str) -> str:
        """Recibe mensaje WhatsApp y retorna respuesta."""
        self.messages_processed += 1
        timestamp = datetime.now(timezone.utc).isoformat()

        if from_number not in self.users_connected:
            self.users_connected.append(from_number)

        msg_record = {
            "id": f"wa_{uuid.uuid4().hex[:12]}",
            "from": from_number,
            "body": body,
            "timestamp": timestamp,
            "direction": "incoming",
        }
        self._message_log.append(msg_record)
        logger.info("Received from %s: %s", from_number, body[:100])

        try:
            if body.strip().startswith("/"):
                response = await self._process_command(body.strip(), from_number)
            else:
                response = await self._process_chat(body, from_number)
        except Exception as exc:
            logger.error("Error processing message: %s", exc)
            response = "Error procesando mensaje. Envia /help para comandos."

        msg_record["response"] = response
        msg_record["direction"] = "complete"

        return response

    async def send_message(self, to_number: str, text: str) -> Dict[str, Any]:
        """Envia mensaje por WhatsApp via Twilio."""
        try:
            from twilio.rest import Client
            if self.client is None:
                self.client = Client(self.account_sid, self.auth_token)

            message = self.client.messages.create(
                body=text,
                from_=f"whatsapp:{self.whatsapp_number}",
                to=f"whatsapp:{to_number}",
            )
            result = {
                "status": "sent",
                "message_sid": message.sid,
                "to": to_number,
                "from": self.whatsapp_number,
                "text": text,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            logger.info("Sent to %s: %s (sid: %s)", to_number, text[:50], message.sid)
            return result
        except ImportError:
            logger.warning("Twilio SDK not available, simulating send")
            return {
                "status": "simulated",
                "message_sid": f"SM_{uuid.uuid4().hex[:16]}",
                "to": to_number,
                "from": self.whatsapp_number,
                "text": text,
            }
        except Exception as exc:
            logger.error("Send failed: %s", exc)
            return {"status": "error", "error": str(exc)}

    async def process_command(self, command: str, args: str, from_number: str) -> str:
        """Procesa comandos de WhatsApp."""
        cmd = command.lower().strip()
        handler = self._command_handlers.get(cmd)

        if handler:
            try:
                result = await handler(args, from_number)
                return result
            except Exception as exc:
                return f"Error executing {cmd}: {exc}"

        return f"Comando desconocido: {cmd}. Envía /help para lista."

    async def handle_webhook(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Webhook endpoint para Twilio."""
        body = request.get("Body", "")
        from_number = request.get("From", "")
        messaging_product = request.get("MessagingProduct", "whatsapp")

        if messaging_product != "whatsapp":
            return {"status": "ignored", "reason": "not_whatsapp"}

        response_text = await self.receive_message(from_number, body)

        return {
            "status": "processed",
            "from": from_number,
            "response": response_text,
            "message_id": f"wa_{uuid.uuid4().hex[:12]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _process_chat(self, message: str, from_number: str) -> str:
        """Procesa mensaje de chat normal."""
        try:
            from fastapi import APIClient  # type: ignore
            # Usa HTTP directo para evitar dependencia
            import urllib.request
            import json as json_mod

            endpoint = self._get_chat_endpoint()
            payload = json_mod.dumps({"message": message}).encode()
            req = urllib.request.Request(
                f"{endpoint}/api/aura/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json_mod.loads(resp.read())
                return data.get("response", "No response")
        except Exception as exc:
            logger.debug("Chat endpoint failed: %s", exc)
            return "Chat unavailable. Try the desktop app."

    async def _process_command(self, text: str, from_number: str) -> str:
        """Procesa comando desde WhatsApp."""
        parts = text.split(" ", 1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        return await self.process_command(cmd, args, from_number)

    def _get_chat_endpoint(self) -> str:
        """Obtiene endpoint de chat."""
        import os
        return os.getenv("AURA_BACKEND_URL", "http://127.0.0.1:8000")

    async def _cmd_fanfic(self, prompt: str, from_number: str) -> str:
        """Genera fanfic."""
        try:
            result = await self.send_message(from_number, f"Generating fanfic: {prompt[:50]}...")
            return f"Fanfic started: {prompt or 'adventure'}. Check your AURA desktop for the full story."
        except Exception as exc:
            return f"Fanfic error: {exc}"

    async def _cmd_search(self, query: str, from_number: str) -> str:
        """Busca algo."""
        return f"Searching for: {query or 'general query'}. Use desktop for detailed results."

    async def _cmd_marketplace(self, args: str, from_number: str) -> str:
        """Muestra items del marketplace."""
        try:
            resp = await self.send_message(from_number, "Opening marketplace...")
            return "Marketplace: Check AURA desktop or web dashboard for full catalog."
        except Exception as exc:
            return f"Marketplace error: {exc}"

    async def _cmd_stats(self, args: str, from_number: str) -> str:
        """Muestra estadisticas."""
        try:
            import urllib.request, json as json_mod
            endpoint = self._get_chat_endpoint()
            req = urllib.request.Request(f"{endpoint}/api/status")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json_mod.loads(resp.read())
                daq = data.get("daemon", {})
                rev = data.get("revenue", 0)
                agents = data.get("agents_count", 0)
            return f"Stats: {agents} agents, ${rev:.2f} revenue, {daq.get('current_tasks', 0)} tasks active"
        except Exception as exc:
            return f"Stats unavailable: {exc}"

    async def _cmd_netrunner(self, args: str, from_number: str) -> str:
        """Inicia juego netrunner."""
        return "Netrunner v2: Open web dashboard to play from your phone!"

    async def _cmd_ask(self, question: str, from_number: str) -> str:
        """AURA responde una pregunta."""
        return f"AURA would answer: {question or 'your question'} (desktop recommended for full response)"

    async def _cmd_help(self, args: str, from_number: str) -> str:
        """Muestra ayuda."""
        return "Commands: /fanfic, /search, /marketplace, /stats, /netrunner, /ask, /status, /help"

    async def _cmd_status(self, args: str, from_number: str) -> str:
        """Status del bot."""
        return f"Bot: {self.messages_processed} messages, {len(self.users_connected)} users connected"


whatsapp_bot: Optional[WhatsAppBot] = None


def get_whatsapp_bot() -> WhatsAppBot:
    """Singleton accessor for WhatsAppBot."""
    global whatsapp_bot
    if whatsapp_bot is None:
        whatsapp_bot = WhatsAppBot()
    return whatsapp_bot
