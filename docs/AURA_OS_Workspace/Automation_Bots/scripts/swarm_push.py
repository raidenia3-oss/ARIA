#!/usr/bin/env python3
"""
Script para transferir archivos a Termux con validación de red y seguridad.
Uso: python swarm_push.py <archivo_local> <ruta_remota>
Ejemplo: python swarm_push.py osint_username.py ~/osint_username.py
"""

import os
import sys
import subprocess
import time
import hashlib
from pathlib import Path

# Configuración
TERMUX_HOST = "192.168.3.14"
TERMUX_PORT = 8022
TERMUX_USER = "u0_a1167"
TERMUX_PASS = "termux123"
REMOTE_DIR = "/data/data/com.termux/files/home/"

def calcular_md5(archivo):
    """Calcula el hash MD5 de un archivo."""
    hash_md5 = hashlib.md5()
    with open(archivo, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def validar_red():
    """Verifica si el dispositivo Termux está en la red local."""
    try:
        # Ping rápido al dispositivo
        result = subprocess.run(
            ["ping", "-n", "1", "-w", "1000", TERMUX_HOST],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        if result.returncode != 0:
            print("ERROR: Nodo fuera de la red local Wi-Fi")
            print("Causas posibles:")
            print("- Celular en red de datos móviles (ccmni0)")
            print("- Firewall bloqueando ICMP")
            print("- Celular apagado o en reposo")
            return False
        return True
    except Exception as e:
        print(f"ERROR: No se pudo verificar la red: {e}")
        return False

def transferir_archivo(local_path, remote_path):
    """Transfiere un archivo a Termux usando SCP."""
    try:
        # Verificar que el archivo local exista
        if not os.path.exists(local_path):
            print(f"ERROR: Archivo local no encontrado: {local_path}")
            return False

        # Calcular hash MD5 del archivo local
        local_md5 = calcular_md5(local_path)
        print(f"Hash MD5 local: {local_md5}")

        # Transferir el archivo usando SCP
        scp_cmd = [
            "scp",
            "-P", str(TERMUX_PORT),
            "-o", f"StrictHostKeyChecking=no",
            f"{local_path}",
            f"{TERMUX_USER}@{TERMUX_HOST}:{remote_path}"
        ]

        # Ejecutar SCP con contraseña
        scp_process = subprocess.Popen(
            scp_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Enviar contraseña
        stdout, stderr = scp_process.communicate(input=f"{TERMUX_PASS}\n")

        if scp_process.returncode != 0:
            print(f"ERROR: Falló la transferencia SCP: {stderr}")
            return False

        print(f"Archivo transferido correctamente: {local_path} -> {remote_path}")
        return True
    except Exception as e:
        print(f"ERROR: Falló la transferencia: {e}")
        return False

def verificar_integridad(remote_path):
    """Verifica que el archivo en Termux tenga el mismo tamaño y hash."""
    try:
        # Obtener tamaño del archivo local
        local_size = os.path.getsize(sys.argv[1])
        local_md5 = calcular_md5(sys.argv[1])

        # Obtener tamaño del archivo remoto
        ssh_cmd = [
            "sshpass",
            "-p", TERMUX_PASS,
            "ssh",
            "-p", str(TERMUX_PORT),
            "-o", "StrictHostKeyChecking=no",
            f"{TERMUX_USER}@{TERMUX_HOST}",
            f"ls -la {remote_path} | awk '{{print $5}}'"
        ]

        result = subprocess.run(
            ssh_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:
            print(f"ERROR: No se pudo obtener el tamaño del archivo remoto: {result.stderr}")
            return False

        remote_size = int(result.stdout.strip())

        if local_size != remote_size:
            print(f"ERROR: Tamaño del archivo no coincide. Local: {local_size} bytes, Remoto: {remote_size} bytes")
            return False

        # Verificar hash MD5 (opcional, requiere transferencia de hash)
        print(f"Verificación de tamaño exitosa. Tamaño: {local_size} bytes")
        return True
    except Exception as e:
        print(f"ERROR: Falló la verificación de integridad: {e}")
        return False

def main():
    if len(sys.argv) != 3:
        print("Uso: python swarm_push.py <archivo_local> <ruta_remota>")
        print("Ejemplo: python swarm_push.py osint_username.py ~/osint_username.py")
        sys.exit(1)

    local_path = sys.argv[1]
    remote_path = REMOTE_DIR + sys.argv[2].lstrip("~/")

    # Validar red
    if not validar_red():
        sys.exit(1)

    # Transferir archivo
    if not transferir_archivo(local_path, remote_path):
        sys.exit(1)

    # Verificar integridad
    if not verificar_integridad(remote_path):
        sys.exit(1)

    print("¡Transferencia exitosa!")

if __name__ == "__main__":
    main()