#!/usr/bin/env python3
"""
Script integrado para monitorear eventos de radar y enviarlos al EventBus de AURA.
Combina la telemetría off-grid con el sistema existente de AME.
"""

import os
import sys
import json
import time
import threading
import subprocess
from datetime import datetime

# Configuración del sistema AME
AME_CORE_DIR = "AME_Core"
TERMUX_IP = "192.168.3.14"
TERMUX_USER = "u0_a1167"
TERMUX_PATH = "/home/u0_a1167/AME-termux"
SSH_KEY_PATH = os.path.expanduser("~/.ssh/id_rsa")

# Configuración de radar
RADAR_LOG_DIR = "/sdcard/aura_radar_logs"
RADAR_BUFFER_FILE = "/sdcard/aura_radar_buffer.bin"

# EventBus de AURA (simulado)
class AuraEventBus:
    def __init__(self):
        self.connected = False

    def connect(self):
        """Simula conexión al EventBus de AURA."""
        self.connected = True
        print("🌐 Conectado al EventBus de AURA")

    def publish(self, event_type, data):
        """Publica un evento en el EventBus de AURA."""
        if not self.connected:
            print("⚠️  No conectado al EventBus. Evento bufferizado localmente.")
            self._buffer_event(event_type, data)
            return

        event = {
            "event_type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "source": "LoRa_Radar_Node"
        }

        print(f"📡 EventBus AURA: {event_type} - {json.dumps(data)}")

        # Simular envío al servidor AURA
        try:
            # En un entorno real, esto enviaría el evento al servidor AURA
            # Ejemplo: usando requests o WebSocket
            print(f"🔄 Enviando evento a AURA: {event_type}")
            return True
        except Exception as e:
            print(f"❌ Error al enviar evento a AURA: {e}")
            self._buffer_event(event_type, data)
            return False

    def _buffer_event(self, event_type, data):
        """Guarda eventos en buffer local si no hay conexión."""
        try:
            os.makedirs(RADAR_LOG_DIR, exist_ok=True)

            event = {
                "event_type": event_type,
                "data": data,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "buffered_at": datetime.utcnow().isoformat() + "Z"
            }

            with open(os.path.join(RADAR_LOG_DIR, f"buffer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"), 'w') as f:
                json.dump(event, f)
            print(f"💾 Evento bufferizado localmente: {event_type}")
        except Exception as e:
            print(f"❌ Error al bufferizar evento: {e}")

    def check_connection(self):
        """Verifica conexión al EventBus de AURA (simulada)."""
        # En un entorno real, esto verificaría la conexión real
        return True

# Función para compilar y sincronizar APK
def build_and_sync_apk():
    """Compila el APK y sincroniza cambios con Termux."""
    print("🔧 Compilando APK con Capacitor...")
    try:
        # Compilar frontend
        subprocess.run(["npm", "run", "build"], check=True, cwd=".")

        # Sincronizar con Android
        subprocess.run(["npx", "capacitor", "sync", "android"], check=True, cwd=".")

        # Compilar APK
        subprocess.run(["./gradlew", "assembleDebug"], check=True, cwd="android/app")

        # Copiar APK al escritorio
        apk_path = os.path.join("android", "app", "build", "outputs", "apk", "debug", "app-debug.apk")
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop", "AME_PROD.apk")

        if os.path.exists(apk_path):
            subprocess.run(["copy", apk_path, desktop_path], shell=True, check=True)
            print(f"✅ APK copiado a: {desktop_path}")
            return True
        else:
            print("❌ No se encontró el APK generado.")
            return False
    except subprocess.CalledProcessError as e:
        print(f"❌ Error al compilar APK: {e}")
        return False

# Función para sincronizar cambios con Termux
def sync_to_termux():
    """Sincroniza archivos modificados a Termux usando SCP."""
    if not os.path.exists(SSH_KEY_PATH):
        print("⚠️  No se encontró clave SSH. Usando SCP con contraseña.")
        return False

    try:
        # Copiar archivos modificados
        files_to_copy = [
            "index.html",
            "dashboard.html",
            "static/js/**/*.js",
            "static/css/**/*.css",
            "templates/**/*.html"
        ]

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

# Función para procesar eventos de radar
def process_radar_event(event_data):
    """Procesa un evento de radar y lo envía al EventBus de AURA."""
    aura_event_bus = AuraEventBus()
    aura_event_bus.connect()

    # Formatear evento para el EventBus de AURA
    aura_event = {
        "module": "radar",
        "action": "update",
        "payload": event_data,
        "metadata": {
            "source": "LoRa_Radar_Node",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    }

    # Enviar evento al EventBus
    success = aura_event_bus.publish("radar_update", aura_event)
    if success:
        print("✅ Evento de radar enviado al EventBus de AURA")
    else:
        print("⚠️  Evento de radar bufferizado para envío posterior")

# Función para simular recepción de eventos de radar
def simulate_radar_events():
    """Simula la recepción de eventos de radar desde un dispositivo USB-OTG."""
    print("📡 Simulando recepción de eventos de radar...")

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

# Función principal
def main():
    print("🚀 Iniciando sistema integrado de monitoreo de radar y AME")

    # Iniciar hilo para simular eventos de radar
    radar_thread = threading.Thread(target=simulate_radar_events)
    radar_thread.daemon = True
    radar_thread.start()

    # Monitorear cambios en AME_Core
    print(f"👀 Monitoreando cambios en {AME_CORE_DIR} para compilación y sincronización...")

    try:
        while True:
            # Verificar si hay cambios en AME_Core (simplificado)
            # En un entorno real, usaríamos watchdog o inotify
            time.sleep(10)

            # Ejemplo: Compilar y sincronizar cada 30 segundos (para pruebas)
            if input("\nPresiona Enter para compilar y sincronizar APK (o Ctrl+C para salir): ") == "":
                if build_and_sync_apk():
                    sync_to_termux()

    except KeyboardInterrupt:
        print("\n🛑 Deteniendo el sistema integrado...")

if __name__ == "__main__":
    main()