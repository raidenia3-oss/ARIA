# -*- coding: utf-8 -*-
"""AURA OS — Bots package init."""
from backend.bots.whatsapp_bot import WhatsAppBot, get_whatsapp_bot, whatsapp_bot

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
