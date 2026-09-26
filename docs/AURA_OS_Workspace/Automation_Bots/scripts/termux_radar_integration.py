#!/usr/bin/env python3
"""
Script para integrar la telemetría de radar con el servidor existente en Termux.
Este script se ejecutará en Termux y enviará eventos de radar al servidor local.
"""

import os
import sys
import json
import time
import threading
import subprocess
from datetime import datetime

# Configuración de Termux
TERMUX_RADAR_DIR = "/sdcard/aura_radar_logs"
TERMUX_BUFFER_FILE = "/sdcard/aura_radar_buffer.bin"
SERVER_PATH = "/home/u0_a1167/AME-termux/servidor.py"
LOG_DIR = "/home/u0_a1167/AME-termux/logs"

# EventBus local en Termux
class TermuxEventBus:
    def __init__(self):
        self.connected = False

    def connect(self):
        """Simula conexión al servidor local en Termux."""
        self.connected = True
        print("🌐 Conectado al servidor local en Termux")

    def publish(self, event_type, data):
        """Publica un evento al servidor local en Termux."""
        if not self.connected:
            print("⚠️  No conectado al servidor. Evento bufferizado localmente.")
            self._buffer_event(event_type, data)
            return False

        event = {
            "event_type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "source": "LoRa_Radar_Node"
        }

        print(f"📡 EventBus Termux: {event_type} - {json.dumps(data)}")

        # Simular envío al servidor local
        try:
            # En un entorno real, esto enviaría el evento al servidor usando sockets o HTTP
            print(f"🔄 Enviando evento al servidor local: {event_type}")
            return True
        except Exception as e:
            print(f"❌ Error al enviar evento al servidor: {e}")
            self._buffer_event(event_type, data)
            return False

    def _buffer_event(self, event_type, data):
        """Guarda eventos en buffer local si no hay conexión."""
        try:
            os.makedirs(TERMUX_RADAR_DIR, exist_ok=True)

            event = {
                "event_type": event_type,
                "data": data,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "buffered_at": datetime.utcnow().isoformat() + "Z"
            }

            with open(os.path.join(TERMUX_RADAR_DIR, f"buffer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"), 'w') as f:
                json.dump(event, f)
            print(f"💾 Evento bufferizado localmente: {event_type}")
        except Exception as e:
            print(f"❌ Error al bufferizar evento: {e}")

    def check_connection(self):
        """Verifica conexión al servidor local (simulada)."""
        # En un entorno real, esto verificaría la conexión real al servidor
        return True

# Función para procesar eventos de radar
def process_radar_event(event_data):
    """Procesa un evento de radar y lo envía al EventBus local."""
    event_bus = TermuxEventBus()
    event_bus.connect()

    # Formatear evento para el EventBus local
    termux_event = {
        "module": "radar",
        "action": "update",
        "payload": event_data,
        "metadata": {
            "source": "LoRa_Radar_Node",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    }

    # Enviar evento al EventBus local
    success = event_bus.publish("radar_update", termux_event)
    if success:
        print("✅ Evento de radar enviado al servidor local")
    else:
        print("⚠️  Evento de radar bufferizado para envío posterior")

# Función para simular recepción de eventos de radar
def simulate_radar_events():
    """Simula la recepción de eventos de radar desde un dispositivo USB-OTG."""
    print("📡 Simulando recepción de eventos de radar en Termux...")

    # Ejemplo de eventos simulados
    sample_events = [
        {
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
        },
        {
            "sensor_id": "LoRa_Node_1",
            "timestamp": "2026-06-05T16:31:00Z",
            "target_count": 1,
            "metrics": [
                {
                    "target_id": "TGT_003",
                    "distance": 200.5,
                    "velocity": 22.3,
                    "angle": 90.0,
                    "signal_strength": -65
                }
            ],
            "status": "active",
            "battery_level": 86
        }
    ]

    # Procesar eventos simulados
    for event in sample_events:
        process_radar_event(event)
        time.sleep(2)

    # Simular recepción continua
    while True:
        print("\n🔄 Esperando nuevos eventos de radar...")
        time.sleep(5)

# Función para reiniciar el servidor en Termux
def restart_server():
    """Reinicia el servidor en Termux."""
    try:
        print("🔄 Reiniciando servidor en Termux...")
        subprocess.run(["pkill", "-f", "python3.*servidor.py"], shell=True, check=True)
        time.sleep(1)
        subprocess.Popen(["python3", SERVER_PATH], cwd=os.path.dirname(SERVER_PATH))
        print("✅ Servidor reiniciado.")
    except Exception as e:
        print(f"❌ Error al reiniciar servidor: {e}")

# Función principal
def main():
    print("🚀 Iniciando integración de radar con servidor en Termux")

    # Crear directorios necesarios
    os.makedirs(TERMUX_RADAR_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

    # Iniciar hilo para simular eventos de radar
    radar_thread = threading.Thread(target=simulate_radar_events)
    radar_thread.daemon = True
    radar_thread.start()

    # Reiniciar servidor
    restart_server()

    print(f"👀 Monitoreando eventos de radar en Termux...")
    print("Presiona Ctrl+C para detener.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Deteniendo integración de radar...")

if __name__ == "__main__":
    main()