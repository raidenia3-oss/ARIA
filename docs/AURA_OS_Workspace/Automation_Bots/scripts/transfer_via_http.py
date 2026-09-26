#!/usr/bin/env python3
"""
Script para transferir archivos desde la PC a Termux usando un servidor HTTP temporal.
Este script crea un servidor HTTP en la PC y proporciona instrucciones para descargar los archivos desde Termux.
"""

import http.server
import socketserver
import os
import threading
import webbrowser
import time
import sys

# Configuración
PORT = 8000
DIRECTORY = "C:/Users/User/Downloads/AME-termux"
TERMUX_IP = "192.168.3.14"  # Cambiar por la IP real de Termux
TERMUX_DIR = "/sdcard/AME-termux"  # Directorio en Termux donde se guardarán los archivos

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

def run_server():
    """Inicia el servidor HTTP en un hilo separado."""
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Servidor HTTP iniciado en http://localhost:{PORT}")
        print(f"Accede a http://{TERMUX_IP}:{PORT} desde Termux para descargar archivos.")
        print(f"Directorio de origen: {DIRECTORY}")
        print(f"Directorio de destino en Termux: {TERMUX_DIR}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor detenido.")

def show_instructions():
    """Muestra instrucciones para descargar archivos desde Termux."""
    print("\n" + "="*60)
    print("INSTRUCCIONES PARA DESCARGAR ARCHIVOS DESDE TERMUX:")
    print("="*60)
    print(f"1. Abre Termux y ejecuta los siguientes comandos:")
    print(f"   mkdir -p {TERMUX_DIR}")
    print(f"   pkg install -y wget")
    print(f"")
    print(f"2. Descarga todos los archivos desde el servidor HTTP:")
    print(f"   cd {TERMUX_DIR}")
    print(f"   wget -r -np -nH --cut-dirs=3 -R \"index.html*\" http://{TERMUX_IP}:{PORT}/")
    print(f"   o individualmente:")
    print(f"   wget http://{TERMUX_IP}:{PORT}/archivo.py -O {TERMUX_DIR}/archivo.py")
    print(f"")
    print(f"3. Ejecuta el script de monitoreo:")
    print(f"   python3 {TERMUX_DIR}/simple_termux_watcher.py")
    print(f"")
    print(f"4. Inicia el servidor principal:")
    print(f"   python3 {TERMUX_DIR}/servidor.py")
    print("="*60)

def main():
    """Función principal del script."""
    print(f"Iniciando servidor HTTP en el puerto {PORT}...")
    print(f"Directorio de origen: {DIRECTORY}")

    # Iniciar el servidor en un hilo
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()

    # Esperar un momento para que el servidor inicie
    time.sleep(2)

    # Mostrar instrucciones
    show_instructions()

    # Mantener el script en ejecución hasta que el usuario lo detenga
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nDeteniendo el script...")
        sys.exit(0)

if __name__ == "__main__":
    main()