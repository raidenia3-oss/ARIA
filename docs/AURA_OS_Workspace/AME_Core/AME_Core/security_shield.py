# security_shield.py - Módulo de Defensa y Ocultamiento
import hashlib
import psutil
import requests
import random

# Lista de User-Agents para evitar Fingerprinting
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
]

def rotate_fingerprint():
    return {"User-Agent": random.choice(USER_AGENTS)}

def get_tor_proxy():
    # Enrutamiento obligatorio a través del nodo local Tor
    return {"http": "socks5h://127.0.0.1:9050", "https": "socks5h://127.0.0.1:9050"}

def check_integrity(file_path):
    """Calcula el SHA-256 para detectar inyecciones o alteraciones"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def scan_for_threats():
    """Detecta procesos sospechosos intentando inyectar memoria en AURA"""
    for proc in psutil.process_iter(['pid', 'name']):
        # Escaneo de patrones de herramientas de monitoreo externo
        if any(tool in proc.info['name'].lower() for tool in ['wireshark', 'fiddler', 'nmap']):
            return f"AMENAZA DETECTADA: {proc.info['name']}"
    return "CLEAN"