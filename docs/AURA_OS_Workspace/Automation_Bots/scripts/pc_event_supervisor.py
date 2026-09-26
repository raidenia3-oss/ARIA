#!/usr/bin/env python3
"""
Script para el supervisor de eventos en la PC que recibe datos del nodo móvil.
"""

import json
import time
import os
from datetime import datetime

# Configuración
EVENT_LOG_DIR = "C:/Users/User/Downloads/AURA/logs/radar_events"
MAX_LOG_FILES = 5
LOG_FILE = os.path.join(EVENT_LOG_DIR, f"radar_events_{datetime.now().strftime('%Y%m%d')}.jsonl")

def ensure_log_directory():
    """Asegura que el directorio de logs existe."""
    os.makedirs(EVENT_LOG_DIR, exist_ok=True)

    # Limpiar logs antiguos
    files = sorted(os.listdir(EVENT_LOG_DIR), reverse=True)
    for f in files[MAX_LOG_FILES:]:
        os.remove(os.path.join(EVENT_LOG_DIR, f))

def log_event(event):
    """Guarda un evento en el log."""
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(json.dumps(event) + '\n')
        print(f"📝 Evento guardado en {LOG_FILE}")
    except Exception as e:
        print(f"❌ Error al guardar evento: {e}")

def process_event(event_data):
    """Procesa un evento de radar."""
    try:
        event = {
            "received_at": datetime.utcnow().isoformat() + "Z",
            "event_type": "radar_update",
            "data": event_data
        }

        print(f"📡 Evento recibido: {event['data']['sensor_id']} - {len(event['data']['metrics'])} targets")

        # Guardar en log
        log_event(event)

        # Procesar datos (ejemplo: imprimir en consola)
        for target in event['data']['metrics']:
            print(f"  - {target['target_id']}: {target['distance']}m, {target['velocity']}m/s, {target['angle']}°")

        return True

    except Exception as e:
        print(f"❌ Error al procesar evento: {e}")
        return False

def simulate_receive_events():
    """Simula la recepción de eventos desde el nodo móvil (para pruebas)."""
    print("📡 Simulando recepción de eventos desde el nodo móvil...")

    # Ejemplo de evento simulado
    sample_event = {
        "sensor_id": "LoRa_Node_1",
        "timestamp": "2026-06-05T16:30:45Z",
        "target_count": 2,
        "metrics": [
            {
                "target_id": "TGT_001",
                "distance": 125.3,
                "velocity": 18.7,
                "angle": 45.2,
                "signal_strength": -68
            },
            {
                "target_id": "TGT_002",
                "distance": 89.1,
                "velocity": 0.0,
                "angle": 135.0,
                "signal_strength": -72
            }
        ],
        "status": "active",
        "battery_level": 87
    }

    # Procesar evento simulado
    process_event(sample_event)

    # Simular recepción continua
    while True:
        time.sleep(2)
        print("\n🔄 Esperando eventos...")
        time.sleep(5)

def main():
    """Función principal."""
    ensure_log_directory()
    simulate_receive_events()

if __name__ == "__main__":
    main()