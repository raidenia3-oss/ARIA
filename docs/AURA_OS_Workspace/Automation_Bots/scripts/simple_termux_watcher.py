#!/usr/bin/env python3
"""
Script simplificado para Termux que monitorea cambios en archivos usando polling.
No requiere dependencias adicionales.
"""

import os
import time
import subprocess
import hashlib

# Configuración
PROJECT_DIR = os.path.expanduser("~/AME-termux")
SERVER_SCRIPT = os.path.join(PROJECT_DIR, "servidor.py")

# Diccionario para almacenar hashes de archivos
file_hashes = {}

def calculate_hash(filepath):
    """Calcula el hash SHA1 de un archivo."""
    sha1 = hashlib.sha1()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            sha1.update(chunk)
    return sha1.hexdigest()

def restart_server():
    """Reinicia el servidor."""
    try:
        # Matar procesos existentes del servidor
        subprocess.run(["pkill", "-f", "python3.*servidor.py"], shell=True, check=True)
        time.sleep(1)

        # Iniciar el servidor nuevamente
        subprocess.Popen(["python3", SERVER_SCRIPT], cwd=PROJECT_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"[+] Servidor reiniciado en {SERVER_SCRIPT}")
    except Exception as e:
        print(f"[-] Error al reiniciar el servidor: {e}")

def monitor_changes():
    """Monitorea cambios en los archivos usando polling."""
    global file_hashes

    print(f"[+] Monitoreando cambios en {PROJECT_DIR}...")

    while True:
        try:
            for root, _, files in os.walk(PROJECT_DIR):
                for file in files:
                    if file.endswith('.py'):
                        filepath = os.path.join(root, file)
                        if os.path.exists(filepath):
                            current_hash = calculate_hash(filepath)
                            if filepath in file_hashes:
                                if file_hashes[filepath] != current_hash:
                                    print(f"[+] Archivo modificado: {filepath}")
                                    restart_server()
                                    file_hashes[filepath] = current_hash
                            else:
                                file_hashes[filepath] = current_hash
            time.sleep(2)  # Verificar cada 2 segundos

        except KeyboardInterrupt:
            print("\n[-] Deteniendo el monitoreo...")
            break

        except Exception as e:
            print(f"[-] Error en el monitoreo: {e}")
            time.sleep(5)

if __name__ == "__main__":
    # Iniciar el servidor al comienzo
    restart_server()

    # Iniciar el monitoreo
    monitor_changes()