#!/usr/bin/env python3
"""
Script para detectar cambios en AME_Core y ejecutar comandos de compilación y sincronización.
"""

import os
import time
import hashlib
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configuración
AME_CORE_DIR = "AME_Core"
DIST_DIR = "dist"
TERMUX_IP = "192.168.3.14"  # Cambiar por la IP real de Termux
TERMUX_USER = "u0_a1167"
TERMUX_PATH = "/home/u0_a1167/AME-termux"
SSH_KEY_PATH = os.path.expanduser("~/.ssh/id_rsa")

# Archivos a monitorear
FILES_TO_WATCH = [
    "index.html",
    "dashboard.html",
    "static/js/**/*.js",
    "static/css/**/*.css",
    "templates/**/*.html"
]

# Diccionario para almacenar hashes de archivos
file_hashes = {}

def calculate_hash(filepath):
    """Calcula el hash SHA1 de un archivo."""
    sha1 = hashlib.sha1()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            sha1.update(chunk)
    return sha1.hexdigest()

def build_apk():
    """Compila el APK usando Capacitor."""
    print("🔧 Compilando APK con Capacitor...")
    try:
        # Compilar el frontend
        subprocess.run(["npm", "run", "build"], check=True, cwd=".")

        # Sincronizar con Android
        subprocess.run(["npx", "capacitor", "sync", "android"], check=True, cwd=".")

        # Compilar APK
        subprocess.run(["./gradlew", "assembleDebug"], check=True, cwd="android/app")

        print("✅ APK compilado exitosamente.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error al compilar APK: {e}")
        return False

def copy_apk_to_desktop():
    """Copia el APK generado al escritorio."""
    apk_path = os.path.join("android", "app", "build", "outputs", "apk", "debug", "app-debug.apk")
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop", "AME_PROD.apk")

    if os.path.exists(apk_path):
        try:
            os.makedirs(os.path.dirname(desktop_path), exist_ok=True)
            subprocess.run(["copy", apk_path, desktop_path], shell=True, check=True)
            print(f"✅ APK copiado a: {desktop_path}")
            return True
        except Exception as e:
            print(f"❌ Error al copiar APK: {e}")
            return False
    else:
        print("❌ No se encontró el APK generado.")
        return False

def sync_to_termux():
    """Sincroniza archivos modificados a Termux usando SCP."""
    if not os.path.exists(SSH_KEY_PATH):
        print("⚠️  No se encontró clave SSH. Usando SCP con contraseña.")
        return False

    try:
        # Copiar solo los archivos modificados
        for root, dirs, files in os.walk(AME_CORE_DIR):
            for file in files:
                if any([file.endswith(ext) for ext in [".html", ".js", ".css"]]):
                    filepath = os.path.join(root, file)
                    relative_path = os.path.relpath(filepath, AME_CORE_DIR)
                    remote_path = os.path.join(TERMUX_PATH, relative_path)

                    # Crear directorios remotos si no existen
                    remote_dir = os.path.dirname(remote_path)
                    subprocess.run(f"ssh -p 8022 -i {SSH_KEY_PATH} {TERMUX_USER}@{TERMUX_IP} 'mkdir -p {remote_dir}'", shell=True, check=True)

                    # Copiar archivo
                    subprocess.run(f"scp -P 8022 -i {SSH_KEY_PATH} {filepath} {TERMUX_USER}@{TERMUX_IP}:{remote_path}", shell=True, check=True)
                    print(f"✅ Copiado {filepath} a Termux")

        # Reiniciar servidor en Termux
        subprocess.run(f"ssh -p 8022 -i {SSH_KEY_PATH} {TERMUX_USER}@{TERMUX_IP} 'cd {TERMUX_PATH} && pkill -f servidor.py && python3 servidor.py &'", shell=True, check=True)
        print("✅ Servidor en Termux reiniciado.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error al sincronizar con Termux: {e}")
        return False

class ChangeHandler(FileSystemEventHandler):
    def __init__(self):
        self.previous_hashes = {}

    def on_modified(self, event):
        if not event.is_directory:
            filepath = event.src_path
            if filepath.startswith(AME_CORE_DIR):
                current_hash = calculate_hash(filepath)
                if filepath in self.previous_hashes:
                    if self.previous_hashes[filepath] != current_hash:
                        print(f"🔄 Cambio detectado en: {filepath}")
                        self.previous_hashes[filepath] = current_hash
                        self.handle_change(filepath)
                else:
                    self.previous_hashes[filepath] = current_hash
                    self.handle_change(filepath)

    def handle_change(self, filepath):
        print(f"🔄 Procesando cambio en {filepath}...")
        if build_apk():
            if copy_apk_to_desktop():
                sync_to_termux()

def main():
    global file_hashes

    # Guardar hashes iniciales
    for root, dirs, files in os.walk(AME_CORE_DIR):
        for file in files:
            if any([file.endswith(ext) for ext in [".html", ".js", ".css"]]):
                filepath = os.path.join(root, file)
                file_hashes[filepath] = calculate_hash(filepath)

    # Configurar el observador
    event_handler = ChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, AME_CORE_DIR, recursive=True)
    observer.start()

    print(f"👀 Monitoreando cambios en {AME_CORE_DIR}...")
    print("Presiona Ctrl+C para detener.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()