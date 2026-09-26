#!/usr/bin/env python3
"""
Script para generar una clave SSH válida en el formato correcto.
"""

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import os

def generate_ssh_key():
    # Generar clave RSA
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
    )

    # Serializar clave privada en formato PEM
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    # Obtener clave pública
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH
    )

    # Guardar claves
    ssh_dir = os.path.expanduser("~/.ssh")
    os.makedirs(ssh_dir, exist_ok=True)

    private_key_path = os.path.join(ssh_dir, "id_rsa")
    public_key_path = os.path.join(ssh_dir, "id_rsa.pub")

    with open(private_key_path, "wb") as f:
        f.write(pem)

    with open(public_key_path, "wb") as f:
        f.write(public_pem)

    print(f"🔑 Clave SSH generada en {private_key_path}")
    print(f"🔑 Clave pública generada en {public_key_path}")

    # Establecer permisos correctos
    os.chmod(private_key_path, 0o600)
    print(f"🔒 Permisos establecidos en {private_key_path} (600)")

if __name__ == "__main__":
    generate_ssh_key()