# -*- coding: utf-8 -*-
"""AURA OS — WhatsApp API Routes (Twilio).

Endpoints para WhatsApp bot:
- POST /api/whatsapp/webhook — Twilio webhook
- POST /api/whatsapp/send — Enviar mensaje
- GET  /api/whatsapp/status — Status del bot
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel

from backend.bots.whatsapp_bot import WhatsAppBot, get_whatsapp_bot

logger = logging.getLogger("AURA.WhatsAppRoutes")

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])


class SendMessageRequest(BaseModel):
    to_number: str
    text: str


class WebhookRequest(BaseModel):
    Body: Optional[str] = ""
    From: Optional[str] = ""
    MessagingProduct: Optional[str] = "whatsapp"


@router.post("/webhook")
async def whatsapp_webhook(request: WebhookRequest) -> Dict[str, Any]:
    """Webhook de Twilio para mensajes entrantes."""
    try:
        bot = get_whatsapp_bot()
        result = await bot.handle_webhook(request.dict())
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/send")
async def whatsapp_send(req: SendMessageRequest) -> Dict[str, Any]:
    """Envía mensaje WhatsApp a un numero."""
    try:
        bot = get_whatsapp_bot()
        result = await bot.send_message(req.to_number, req.text)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/status")
async def whatsapp_status() -> Dict[str, Any]:
    """Status del bot WhatsApp."""
    try:
        bot = get_whatsapp_bot()
        return {
            "bot_active": True,
            "messages_processed": bot.messages_processed,
            "users_connected": len(bot.users_connected),
            "whatsapp_number": bot.whatsapp_number,
            "twilio_sid": bot.account_sid[:10] + "...",
            "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
