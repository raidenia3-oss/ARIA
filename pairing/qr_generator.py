# -*- coding: utf-8 -*-
"""AURA Pairing — Generador de QR local.

Genera un QR con:
  - IP local (192.168.x.x)
  - Puerto WebSocket
  - Token de pairing (HMAC, valido 5 minutos)
  - Timestamp

Uso: python pairing/qr_generator.py
"""
from __future__ import annotations

import os
import sys
import socket
import hmac
import hashlib
import time
import json
import logging
from pathlib import Path

try:
    import qrcode
except ImportError:
    print("Instalando qrcode...")
    os.check_call([sys.executable, "-m", "pip", "install", "qrcode[pil]"])
    import qrcode

logger = logging.getLogger("AURA.Pairing")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def get_local_ip() -> str:
    """Obtiene IP local real."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_backend_port() -> int:
    """Obtiene puerto del backend (default 8000 o env)."""
    return int(os.environ.get("AURA_PORT", os.environ.get("PORT", "8000")))


def generate_pairing_token(ip: str, port: int, secret: str = None) -> str:
    """Genera token HMAC para pairing."""
    if secret is None:
        secret = os.environ.get("AURA_PAIRING_SECRET", "aura-desktop-2026")
    message = f"{ip}:{port}:{time.time()}".encode()
    token = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()[:8]
    return token.upper()


def generate_qr_data(ip: str, port: int, token: str) -> dict:
    """Genera los datos que se codifican en el QR."""
    return {
        "app": "aura",
        "ip": ip,
        "port": port,
        "ws_port": 9000,
        "token": token,
        "timestamp": time.time(),
        "expires_in": 300,
        "version": "1.0",
    }


def generate_qr_image(data: dict, filename: str = "aura_pairing.png") -> str:
    """Genera imagen QR y la guarda."""
    text = json.dumps(data, separators=(",", ":"))

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(text)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#38bdf8", back_color="#0f172a")
    img.save(filename)
    logger.info("QR guardado en: %s", filename)
    return filename


def display_pairing_info(ip: str, port: int, token: str) -> None:
    """Muestra info de pairing en consola."""
    print()
    print("╔══════════════════════════════════════════╗")
    print("║     🤖 AURA Desktop — Pairing QR       ║")
    print("╠══════════════════════════════════════════╣")
    print(f"║  IP Local:    {ip:<27s} ║")
    print(f"║  Puerto:      {port:<27s} ║")
    print(f"║  WS Puerto:   9000{' ' * 22}║")
    print(f"║  PIN:         {token:<27s} ║")
    print(f"║  Válido:      5 minutos                 ║")
    print("╠══════════════════════════════════════════╣")
    print(f"║  Escanea el QR o usa PIN: {token:<11s} ║")
    print("╚══════════════════════════════════════════╝")
    print()


def run() -> None:
    """Genera y muestra el QR de pairing."""
    logging.basicConfig(level=logging.INFO)

    ip = get_local_ip()
    port = get_backend_port()
    token = generate_pairing_token(ip, port)
    data = generate_qr_data(ip, port, token)

    display_pairing_info(ip, port, token)

    qr_path = str(PROJECT_ROOT / "pairing" / "aura_pairing.png")
    os.makedirs(os.path.dirname(qr_path), exist_ok=True)
    generate_qr_image(data, qr_path)

    print(f"QR visual: {qr_path}")
    print("Espera 5 minutos para que el pairing expire.")
    print("Inicia AME Mobile y escanea el QR o ingresa el PIN.")


if __name__ == "__main__":
    run()
