#!/usr/bin/env python3
"""
cloud_sync.py - Sincroniza la IP de la PC con el móvil
Soluciona 'Failed to fetch' en el APK de AME.
Detecta IP local y la sirve en puerto 5000 para que Termux la consuma.
"""

import socket
import json
import os
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

CONFIG_FILE = "aura_urls.json"
SERVER_PORT = 5000

def get_local_ip():
    """Detecta la IP local de la LAN"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def get_public_ip():
    """Obtiene IP pública (opcional, vía servicio externo)"""
    try:
        import urllib.request
        return urllib.request.urlopen("https://api.ipify.org", timeout=5).read().decode()
    except:
        return None

def create_config(ip, port=SERVER_PORT):
    """Crea el archivo de configuración para el APK"""
    config = {
        "server_ip": ip,
        "server_port": port,
        "api_url": f"http://{ip}:{port}",
        "ws_url": f"ws://{ip}:{port}",
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "aura_version": "1.0"
    }
    return config

def save_config(config, path=CONFIG_FILE):
    """Guarda la configuración en JSON"""
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"✅ Config guardada en {path}")
    return config

class ConfigHandler(BaseHTTPRequestHandler):
    """Handler HTTP minimalista para servir la config"""
    
    def do_GET(self):
        if self.path == "/aura_urls.json" or self.path == "/config":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            try:
                with open(CONFIG_FILE, "r") as f:
                    self.wfile.write(f.read().encode())
            except:
                self.wfile.write(b'{"error":"config_not_found"}')
        elif self.path == "/health":
            # TDD endpoint: verificación cruda
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"alive","service":"aura_sync"}')
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error":"not_found"}')
    
    def do_HEAD(self):
        # Soporte para curl -I (TDD check)
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Silenciar logs de acceso
        pass

def start_http_server(ip, port=SERVER_PORT):
    """Inicia servidor HTTP en background"""
    server = HTTPServer((ip, port), ConfigHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"🌐 Servidor HTTP en http://{ip}:{port}")
    print(f"   GET /aura_urls.json -> config del APK")
    print(f"   GET /health         -> TDD check")
    return server

def sync_to_termux(config, termux_path="/sdcard/aura_config.json"):
    """
    Sincroniza la config con Termux.
    Requiere ADB conectado o termux:boot.
    """
    try:
        result = os.system(f'adb push "{os.path.abspath(CONFIG_FILE)}" "{termux_path}"')
        if result == 0:
            print(f"✅ Config sincronizada a {termux_path} vía ADB")
            return True
    except:
        pass

    # Fallback: escribir en ubicación compartida
    shared_path = os.path.join(os.path.dirname(__file__), "..", CONFIG_FILE)
    save_config(config, shared_path)
    print(f"⚠️  ADB no disponible. Config guardada localmente en {shared_path}")
    return False

def test_connection(ip, port=SERVER_PORT):
    """TDD: Verifica que la IP funciona con curl -I"""
    try:
        import subprocess
        result = subprocess.run(
            ["curl", "-I", "-s", "--max-time", "3",
             f"http://{ip}:{port}/health"],
            capture_output=True, text=True
        )
        if "200" in result.stdout or "alive" in result.stdout:
            print(f"✅ Conexión OK: http://{ip}:{port}")
            return True
        else:
            print(f"❌ Conexión falló: {result.stdout[:100]}")
            return False
    except Exception as e:
        print(f"❌ Error probando conexión: {e}")
        return False

def main():
    """Pipeline completo de sincronización"""
    print("🔄 Cloud Config Sync - Detectando IP...")

    # 1. Detectar IP
    local_ip = get_local_ip()
    public_ip = get_public_ip()
    print(f"📍 IP Local: {local_ip}")
    if public_ip:
        print(f"🌐 IP Pública: {public_ip}")

    # 2. Crear configuración
    config = create_config(local_ip)

    # 3. Guardar localmente
    save_config(config)

    # 4. Iniciar servidor HTTP
    server = start_http_server(local_ip)

    # 5. Sincronizar con Termux
    sync_to_termux(config)

    # 6. TDD: Probar conexión
    print("\n🔍 Probando conexión (TDD)...")
    if test_connection(local_ip):
        print("🎉 Todo OK - El APK debería conectarse correctamente")
    else:
        print("⚠️  Puerto 5000 no responde - Verifica que el servidor esté corriendo")

    # 7. Mantener servidor vivo
    print(f"\n📡 Servidor corriendo en http://{local_ip}:{SERVER_PORT}")
    print("   Presiona Ctrl+C para detener")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n⏹ Deteniendo servidor...")
        server.shutdown()

if __name__ == "__main__":
    main()