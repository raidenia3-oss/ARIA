#!/usr/bin/env python3
"""
Script para manejar el buffer offline de eventos de radar.
Guarda eventos localmente en la tarjeta SD y los sincroniza cuando hay conexión.
"""

import os
import json
import zlib
import hashlib
import time
from datetime import datetime

# Configuración
LOG_DIR = "/sdcard/aura_radar_logs"
BUFFER_FILE = "/sdcard/aura_radar_buffer.bin"
MAX_BUFFER_SIZE = 10485760  # 10MB
SYNC_INTERVAL = 300  # 5 minutos

def check_network():
    """Verifica si hay conexión a internet (simplificado)."""
    # En un entorno real, esto debería verificar la conectividad real
    try:
        # Intentar conectar a un servidor conocido
        import urllib.request
        urllib.request.urlopen("http://www.google.com", timeout=5)
        return True
    except:
        return False

def load_buffer():
    """Carga eventos del buffer local."""
    if not os.path.exists(BUFFER_FILE):
        return []

    try:
        with open(BUFFER_FILE, 'rb') as f:
            buffer_data = f.read()

        events = []
        if buffer_data:
            # Procesar cada evento en el buffer
            parts = buffer_data.split(b'\x00')
            for part in parts:
                if len(part) < 64:  # SHA-256 tiene 64 caracteres
                    continue

                digest = part[:64].decode('utf-8')
                compressed = part[65:]

                # Verificar integridad (simplificado)
                test_digest = hashlib.sha256(compressed).hexdigest()
                if digest == test_digest:
                    try:
                        event = json.loads(zlib.decompress(compressed).decode('utf-8'))
                        events.append(event)
                    except:
                        continue

        return events

    except Exception as e:
        print(f"❌ Error al cargar buffer: {e}")
        return []

def clear_buffer():
    """Limpia el buffer después de sincronizar."""
    try:
        open(BUFFER_FILE, 'wb').close()
        print("🧹 Buffer limpiado.")
    except Exception as e:
        print(f"❌ Error al limpiar buffer: {e}")

def sync_buffer_to_pc():
    """Sincroniza eventos del buffer a la PC usando SCP (simulado)."""
    events = load_buffer()
    if not events:
        print("⚠️  No hay eventos para sincronizar.")
        return

    print(f"📤 Sincronizando {len(events)} eventos a la PC...")

    # En un entorno real, esto usaría SCP o HTTP
    for event in events:
        print(f"📤 Evento: {event['event_type']} - {event['data']['timestamp']}")

    # Simular sincronización exitosa
    clear_buffer()
    print("✅ Sincronización completada.")

def monitor_buffer():
    """Monitorea el buffer y sincroniza cuando hay conexión."""
    print("🔄 Monitoreando buffer offline...")

    while True:
        if check_network():
            print("🌐 Conexión a internet detectada. Sincronizando buffer...")
            sync_buffer_to_pc()
        else:
            print("📶 Sin conexión a internet. Esperando...")

        time.sleep(SYNC_INTERVAL)

def main():
    """Función principal."""
    # Crear directorio de logs si no existe
    os.makedirs(LOG_DIR, exist_ok=True)

    # Verificar si hay eventos en el buffer al inicio
    events = load_buffer()
    if events:
        print(f"⚠️  Se encontraron {len(events)} eventos en el buffer.")
        if input("¿Deseas sincronizarlos ahora? (s/n): ").lower() == 's':
            sync_buffer_to_pc()

    # Iniciar monitoreo del buffer
    monitor_buffer()

if __name__ == "__main__":
    main()