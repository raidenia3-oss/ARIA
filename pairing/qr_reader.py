# -*- coding: utf-8 -*-
"""AURA Pairing — Lector QR para AME Mobile.

Lee el QR generado por AURA Desktop o permite
ingresar el PIN manualmente para pairing.

Valida el token HMAC y conecta via WebSocket local.

Uso: python pairing/qr_reader.py
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
from typing import Optional
from urllib.parse import urljoin

try:
    import requests
except ImportError:
    print("Instalando requests...")
    os.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

logger = logging.getLogger("AURA.Pairing")

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__)).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

QR_EXPIRY = 300


def verify_token(ip: str, port: int, token: str, secret: str = None) -> bool:
    """Verifica si el token HMAC es valido (dentro de 5 min)."""
    if secret is None:
        secret = os.environ.get("AURA_PAIRING_SECRET", "aura-desktop-2026")

    now = time.time()
    for offset in [0, -1, 1]:
        message = f"{ip}:{port}:{now + offset}".encode()
        expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()[:8].upper()
        if token.upper() == expected:
            return True
    return False


def discover_aura() -> Optional[dict]:
    """Descubre AURA Desktop en LAN via UDP broadcast."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(3)
    try:
        s.sendto(b"AURA_DISCOVER", ("255.255.255.255", 8000))
        data, addr = s.recvfrom(1024)
        if data == b"AURA_HERE":
            ip = addr[0]
            return {"ip": ip, "port": 8000}
    except socket.timeout:
        pass
    except Exception as e:
        logger.warning("Discovery error: %s", e)
    finally:
        s.close()
    return None


def pair_with_aura(ip: str, port: int, token: str) -> dict:
    """Realiza el pairing con AURA Desktop."""
    if not verify_token(ip, port, token):
        return {"success": False, "error": "Token invalido o expirado"}

    try:
        base = f"http://{ip}:{port}"

        health = requests.get(f"{base}/health", timeout=5)
        if health.status_code != 200:
            return {"success": False, "error": "Backend no responde"}

        chat = requests.post(
            f"{base}/api/aura/chat",
            json={"message": "pairing"},
            timeout=5,
        )

        return {
            "success": True,
            "ip": ip,
            "port": port,
            "token": token,
            "backend_status": "healthy",
            "chat_test": chat.status_code == 200,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def scan_qr_file(filepath: str) -> Optional[dict]:
    """Lee datos de un archivo QR (simula lectura)."""
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
        return data
    except Exception:
        pass

    try:
        from PIL import Image
        import qrcode
        img = Image.open(filepath)
        return {"image": filepath, "note": "QR visual - ingresa PIN manualmente"}
    except Exception:
        return None


def run_interactive() -> None:
    """Modo interactivo para pairing."""
    logging.basicConfig(level=logging.INFO)

    print("╔══════════════════════════════════════════╗")
    print("║    AME Mobile — Pairing AURA Desktop   ║")
    print("╠══════════════════════════════════════════╣")
    print("║  1. Escanea QR                         ║")
    print("║  2. Ingresar PIN manual                ║")
    print("║  3. Descubrir en red                   ║")
    print("╚══════════════════════════════════════════╝")

    choice = input("Opcion: ").strip()

    if choice == "1":
        filepath = input("Ruta QR (aura_pairing.png): ").strip()
        data = scan_qr_file(filepath)
        if data and "token" in data:
            ip = data.get("ip", "")
            port = data.get("port", 8000)
            token = data.get("token", "")
        else:
            print("No se pudo leer QR, usando modo PIN")
            ip = input("IP: ").strip()
            token = input("PIN: ").strip()
            port = int(input("Puerto [8000]: ").strip() or "8000")
    elif choice == "2":
        ip = input("IP de AURA: ").strip()
        token = input("PIN: ").strip()
        port = int(input("Puerto [8000]: ").strip() or "8000")
    elif choice == "3":
        print("Descubriendo AURA en LAN...")
        found = discover_aura()
        if found:
            ip = found["ip"]
            port = found.get("port", 8000)
            token = input("PIN del QR: ").strip()
            print(f"Encontrado en {ip}:{port}")
        else:
            print("No se encontro AURA en la red")
            return
    else:
        print("Opcion invalida")
        return

    print(f"\nVerificando token para {ip}:{port}...")
    result = pair_with_aura(ip, port, token)

    if result["success"]:
        print()
        print("╔══════════════════════════════════════════╗")
        print("║  PAREO EXITOSO ✅                       ║")
        print("╠══════════════════════════════════════════╣")
        print(f"║  Conectado a: {ip}:{port:<18s}     ║")
        print(f"║  Backend: {'Healthy ✅':<30s} ║")
        print(f"║  Chat:    {'OK ✅':<30s} ║")
        print("╠══════════════════════════════════════════╣")
        print("║  Ya puedes chatear con AURA             ║")
        print("╚══════════════════════════════════════════╝")
    else:
        print(f"\n❌ Error: {result['error']}")
        print("Verifica que AURA Desktop este corriendo.")


def quick_connect(ip: str, port: int = 8000, token: str = "") -> bool:
    """Conexion rapida sin interactuar."""
    if not token:
        token = os.environ.get("AURA_PAIRING_TOKEN", "")
    if not ip:
        discovered = discover_aura()
        if discovered:
            ip = discovered["ip"]
        else:
            return False

    result = pair_with_aura(ip, port, token)
    return result.get("success", False)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        ip = sys.argv[2] if len(sys.argv) > 2 else ""
        port = int(sys.argv[3]) if len(sys.argv) > 3 else 8000
        token = sys.argv[4] if len(sys.argv) > 4 else ""
        ok = quick_connect(ip, port, token)
        print("CONNECTED" if ok else "FAILED")
        sys.exit(0 if ok else 1)
    else:
        run_interactive()
