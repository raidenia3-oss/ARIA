"""
TelemetryHub — Notificador Telegram para AURA.
Envía alertas críticas: saldo ganado, inicio de tareas y captcha pendientes.
"""

import os
import requests
from typing import Optional

TELEGRAM_BOT_TOKEN: Optional[str] = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID: Optional[str] = os.environ.get("TELEGRAM_CHAT_ID")


def send_status_update(message: str) -> bool:
    """Envía un mensaje de texto al chat de Telegram configurado."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"[Telegram omitido] {message}")
        return False

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        response = requests.post(url, json=payload, timeout=10)
        ok = response.status_code == 200 and response.json().get("ok")
        if ok:
            print(f"[Telegram OK] {message}")
        else:
            print(f"[Telegram FAIL] {response.text}")
        return ok
    except Exception as e:
        print(f"[Telegram ERROR] {e}")
        return False


def notify_balance_gained(account: str, amount: float, currency: str = "USD") -> None:
    msg = f"💰 <b>Saldo ganado</b>\n" f"Cuenta: {account}\n" f"Monto: {amount:.4f} {currency}"
    send_status_update(msg)


def notify_task_started(task_name: str, account: str) -> None:
    msg = f"▶️ <b>Tarea iniciada</b>\n" f"Task: {task_name}\n" f"Cuenta: {account}"
    send_status_update(msg)


def notify_captcha_pending(account: str, captcha_type: str = "reCAPTCHA") -> None:
    msg = (
        f"⚠️ <b>Captcha pendiente</b>\n"
        f"Tipo: {captcha_type}\n"
        f"Cuenta: {account}\n"
        f"Requiere intervención humana."
    )
    send_status_update(msg)


if __name__ == "__main__":
    test_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    test_chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not test_token or not test_chat:
        print("Faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID en variables de entorno.")
    else:
        send_status_update("✅ Hub de telemetría operativo.")
