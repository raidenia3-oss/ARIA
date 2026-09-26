#!/usr/bin/env python3
"""
Script para el nodo móvil AME que escucha datos de radar LoRa por USB-OTG y los transforma en eventos JSON.
"""

import serial
import serial.tools.list_ports
import json
import time
from datetime import datetime
import os
import zlib
import hashlib

# Configuración
USB_PORT = "/dev/ttyUSB0"  # Puerto USB-OTG (puede variar)
BAUD_RATE = 115200
TIMEOUT = 1
LOG_DIR = "/sdcard/aura_radar_logs"
BUFFER_FILE = "/sdcard/aura_radar_buffer.bin"
MAX_BUFFER_SIZE = 10485760  # 10MB

# EventBus local (simulado)
class EventBus:
    def __init__(self):
        self.subscribers = {}

    def publish(self, event_type, data):
        """Publica un evento en el EventBus."""
        event = {
            "event_type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        print(f"📡 EventBus: {event_type} - {json.dumps(data)}")

        # Guardar en buffer si no hay conexión
        if not self._check_network():
            self._buffer_event(event)

    def _check_network(self):
        """Verifica si hay conexión a internet (simplificado)."""
        # En un entorno real, esto debería verificar la conectividad
        return True  # Asumimos que hay conexión para este ejemplo

    def _buffer_event(self, event):
        """Guarda eventos en buffer local."""
        try:
            os.makedirs(LOG_DIR, exist_ok=True)

            # Comprimir y cifrar el evento
            compressed = zlib.compress(json.dumps(event).encode('utf-8'))
            digest = hashlib.sha256(compressed).hexdigest()

            # Guardar en buffer
            with open(BUFFER_FILE, 'ab') as f:
                f.write(digest.encode('utf-8'))
                f.write(b'\x00')  # Separador
                f.write(compressed)

            print(f"💾 Evento bufferizado: {event['event_type']}")

        except Exception as e:
            print(f"❌ Error al bufferizar evento: {e}")

# Función para parsear datos crudos del radar
def parse_radar_data(raw_data):
    """
    Convierte datos crudos del radar en formato JSON estructurado.
    Ejemplo de entrada: "TGT:001,125.3,18.7,45.2,-68|TGT:002,89.1,0.0,135.0,-72"
    """
    try:
        targets = []
        for target_str in raw_data.split('|'):
            if not target_str.strip():
                continue

            parts = target_str.split(',')
            if len(parts) != 5:
                continue

            target_id, distance, velocity, angle, signal_strength = parts
            targets.append({
                "target_id": target_id.strip(),
                "distance": float(distance),
                "velocity": float(velocity),
                "angle": float(angle),
                "signal_strength": int(signal_strength)
            })

        return {
            "sensor_id": "LoRa_Node_1",
            "target_count": len(targets),
            "metrics": targets,
            "status": "active",
            "battery_level": 85  # Valor simulado
        }

    except Exception as e:
        print(f"⚠️  Error al parsear datos del radar: {e}")
        return None

# Función principal
def main():
    event_bus = EventBus()

    print("🔍 Buscando puerto USB...")
    ports = serial.tools.list_ports.comports()
    usb_ports = [p for p in ports if "ttyUSB" in p.device or "ACM" in p.device]

    if not usb_ports:
        print("❌ No se encontraron puertos USB disponibles.")
        print("Puestos disponibles:", [p.device for p in ports])
        return

    print(f"🔌 Usando puerto: {USB_PORT}")
    try:
        ser = serial.Serial(USB_PORT, BAUD_RATE, timeout=TIMEOUT)
        print("📡 Escuchando datos del radar LoRa...")

        buffer = ""
        while True:
            if ser.in_waiting:
                line = ser.readline().decode('utf-8').strip()
                buffer += line

                # Buscar final de línea (simplificado)
                if '\n' in buffer:
                    lines = buffer.split('\n')
                    buffer = lines.pop()

                    for raw_line in lines:
                        if raw_line.strip():
                            print(f"📡 Datos crudos: {raw_line}")
                            parsed_data = parse_radar_data(raw_line)
                            if parsed_data:
                                event_bus.publish("radar_update", parsed_data)

            time.sleep(0.1)

    except serial.SerialException as e:
        print(f"❌ Error de comunicación serial: {e}")
    except KeyboardInterrupt:
        print("\n🛑 Deteniendo el puente serial...")
    finally:
        if 'ser' in locals():
            ser.close()
        print("🔌 Puente serial cerrado.")

if __name__ == "__main__":
    main()