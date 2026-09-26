#!/usr/bin/env python3
"""
Script para Termux que monitorea cambios en archivos y reinicia el servidor automáticamente.
"""

import os
import time
import subprocess
import hashlib
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configuración
PROJECT_DIR = os.path.expanduser("~/AME-termux")
SERVER_SCRIPT = os.path.join(PROJECT_DIR, "servidor.py")
LOG_FILE = os.path.join(PROJECT_DIR, "server_watcher.log")

# Función para calcular el hash de un archivo
def file_hash(filepath):
    sha1 = hashlib.sha1()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            sha1.update(chunk)
    return sha1.hexdigest()

# Función para reiniciar el servidor
def restart_server():
    try:
        # Matar procesos existentes del servidor
        subprocess.run(["pkill", "-f", "servidor.py"], check=True)

        # Esperar un momento
        time.sleep(1)

        # Iniciar el servidor nuevamente
        subprocess.Popen(["python3", SERVER_SCRIPT], cwd=PROJECT_DIR)
        print(f"[+] Servidor reiniciado en {SERVER_SCRIPT}")
    except Exception as e:
        print(f"[-] Error al reiniciar el servidor: {e}")

# Clase para manejar eventos del sistema de archivos
class ChangeHandler(FileSystemEventHandler):
    def __init__(self):
        self.previous_hashes = {}

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.py'):
            filepath = os.path.abspath(event.src_path)
            if os.path.exists(filepath):
                current_hash = file_hash(filepath)
                if filepath not in self.previous_hashes or self.previous_hashes[filepath] != current_hash:
                    self.previous_hashes[filepath] = current_hash
                    print(f"[+] Archivo modificado: {filepath}")
                    restart_server()

# Función principal
def main():
    # Verificar si el directorio existe
    if not os.path.exists(PROJECT_DIR):
        print(f"[-] Directorio {PROJECT_DIR} no existe.")
        return

    # Iniciar el servidor al comienzo
    restart_server()

    # Guardar hashes iniciales de los archivos
    handler = ChangeHandler()
    for root, _, files in os.walk(PROJECT_DIR):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                handler.previous_hashes[filepath] = file_hash(filepath)

    # Configurar el observador
    event_handler = ChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, PROJECT_DIR, recursive=True)
    observer.start()

    try:
        print(f"[+] Monitoreando cambios en {PROJECT_DIR}...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()