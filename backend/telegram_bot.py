"""
AURA Telegram Bot - Interface adicional del cerebro unificado.

Funciona como puente entre Telegram y el backend AURA.
Usa las mismas APIs que Discord, Godot y el celular.
"""

from __future__ import annotations

import os
import logging
import requests
from typing import Any, Dict, Optional

logger = logging.getLogger("AURA.Telegram")

TELEGRAM_API = "https://api.telegram.org/bot{token}"


class TelegramBot:
    def __init__(self, token: str, backend_url: str = "http://localhost:8000") -> None:
        self.token = token
        self.backend_url = backend_url.rstrip("/")
        self._offset: int = 0
        self._running = False

    def _api(self, method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = TELEGRAM_API.format(token=self.token) + f"/{method}"
        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            return resp.json().get("result", {})
        except Exception as exc:
            logger.error("Telegram API error %s: %s", method, exc)
            return {}

    def send_message(self, chat_id: int, text: str, parse_mode: str = "HTML") -> Dict[str, Any]:
        return self._api("sendMessage", {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        })

    def get_updates(self) -> Dict[str, Any]:
        return self._api("getUpdates", {
            "offset": self._offset,
            "timeout": 30,
        })

    def process_update(self, update: Dict[str, Any]) -> None:
        message = update.get("message") or {}
        text = message.get("text", "").strip()
        chat_id = message.get("chat", {}).get("id")
        if not text or not chat_id:
            return

        self._offset = update.get("update_id", self._offset) + 1

        if text.startswith("/start"):
            self.send_message(chat_id, "Bienvenido a AURA. Escribime tu mensaje y te respondo.")
            return
        if text.startswith("/status"):
            try:
                resp = requests.get(f"{self.backend_url}/api/status", timeout=5)
                data = resp.json()
                lines = ["Estado de servicios:"]
                for svc, info in data.items():
                    lines.append(f"- {svc}: {info.get('status', 'unknown')}")
                self.send_message(chat_id, "\n".join(lines))
            except Exception as exc:
                self.send_message(chat_id, f"Error consultando estado: {exc}")
            return

        try:
            resp = requests.post(
                f"{self.backend_url}/api/chat",
                json={"prompt": text, "source": "telegram"},
                headers={"Content-Type": "application/json", "X-API-Key": os.getenv("AURA_API_KEY", "")},
                timeout=30,
            )
            data = resp.json()
            reply = data.get("text") or data.get("message") or "(sin respuesta)"
            self.send_message(chat_id, reply)
        except Exception as exc:
            logger.error("Error procesando mensaje Telegram: %s", exc)
            self.send_message(chat_id, "Error procesando tu mensaje.")

    def run(self) -> None:
        self._running = True
        logger.info("Telegram bot started")
        while self._running:
            try:
                updates = self.get_updates()
                for update in updates:
                    self.process_update(update)
            except Exception as exc:
                logger.error("Telegram loop error: %s", exc)
                time.sleep(5)

    def stop(self) -> None:
        self._running = False


def create_telegram_bot() -> Optional[TelegramBot]:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return None
    backend_url = os.getenv("AURA_BACKEND_URL", "http://localhost:8000")
    return TelegramBot(token=token, backend_url=backend_url)
