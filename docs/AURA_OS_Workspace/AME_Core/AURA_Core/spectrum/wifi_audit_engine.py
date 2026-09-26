"""
Módulo de Auditoría Pasiva de Espectro Wi-Fi para AURA.
Motor de reconocimiento pasivo que captura Beacon Frames sin emitir paquetes,
analiza fabricantes, clasifica dispositivos y detecta movimiento mediante fluctuaciones RSSI.
"""

import os
import sys
import threading
import time
import math
from datetime import datetime, timedelta
from collections import defaultdict, deque
import sqlite3
from scapy.all import *
from scapy.layers.dot11 import Dot11Beacon, RadioTap
from scapy.layers.dot11 import Dot11Elt
from python_oui.lookup import lookup
from flask import Flask, jsonify
import platform

# Configuración del módulo
MODULE_NAME = "WiFi Audit Engine"
MODULE_VERSION = "1.0.0"
API_PORT = 5001
MAX_RSSI_WINDOW = 60  # Ventana de 60 segundos para análisis de RSSI
MOVEMENT_THRESHOLD = 6.0  # Umbral de desviación estándar para detectar movimiento
MIN_CONFIDENCE = 0.7  # Confianza mínima para eventos de movimiento

# Base de datos OUI local (para evitar dependencias externas)
OUI_DATABASE = {
    "00:0C:29": "VMware, Inc.",
    "00:13:37": "Apple, Inc.",
    "00:14:22": "Apple, Inc.",
    "00:16:CB": "Apple, Inc.",
    "00:18:84": "Apple, Inc.",
    "00:1A:4B": "Apple, Inc.",
    "00:1B:63": "Apple, Inc.",
    "00:50:F2": "Microsoft Corporation",
    "00:0D:4B": "Huawei Technologies Co., Ltd",
    "00:16:3E": "Huawei Technologies Co., Ltd",
    "00:18:8B": "Huawei Technologies Co., Ltd",
    "00:1D:D1": "Samsung Electronics Co., Ltd",
    "00:1E:4F": "Samsung Electronics Co., Ltd",
    "00:23:12": "Samsung Electronics Co., Ltd",
    "00:0F:E2": "TP-Link Technologies Co., Ltd.",
    "00:11:2F": "TP-Link Technologies Co., Ltd.",
    "00:13:EF": "TP-Link Technologies Co., Ltd.",
    "00:18:F3": "Xiaomi Inc.",
    "00:1E:C2": "Xiaomi Inc.",
    "00:1F:33": "Xiaomi Inc.",
    "00:0C:42": "Intel Corporate",
    "00:1A:79": "Intel Corporate",
    "00:1C:1B": "Google, Inc.",
    "00:1E:8C": "Google, Inc.",
    "00:1F:5B": "Google, Inc.",
    "00:25:4B": "Amazon Technologies Inc.",
    "00:17:88": "Amazon Technologies Inc.",
    "00:1D:4F": "D-Link Corporation",
    "00:26:B0": "D-Link Corporation",
    "00:0F:1F": "Netgear, Inc.",
    "00:1D:0F": "Netgear, Inc.",
    "00:21:5A": "Netgear, Inc.",
}

# Inicialización de la aplicación Flask
app = Flask(__name__)

# Estructura de datos global para el mapa de dispositivos
devices_map = defaultdict(dict)
movement_events = deque(maxlen=100)
lock = threading.Lock()

def get_oui_manufacturer(mac_address):
    """Obtiene el fabricante de un dispositivo usando OUI Lookup."""
    if not mac_address or len(mac_address.split(':')) != 6:
        return "Fabricante desconocido"

    # Extraer los primeros 3 octetos (formato MAC)
    first_three = ':'.join(mac_address.split(':')[:3]).upper()

    # Intentar lookup con python-oui si está disponible
    try:
        result = lookup(mac_address)
        if result and result.manufacturer:
            return result.manufacturer
    except:
        pass

    # Caer a la base de datos local
    return OUI_DATABASE.get(first_three, "Fabricante desconocido")

def classify_device(bssid_data):
    """
    Clasifica un dispositivo basado en su fabricante y patrón de RSSI.
    """
    ssid = bssid_data.get('ssid', '').lower()
    manufacturer = bssid_data.get('manufacturer', '').lower()
    rssi_values = bssid_data.get('rssi_values', [])

    # Clasificación basada en fabricante
    if manufacturer:
        if "apple" in manufacturer:
            if "iphone" in ssid or "ipad" in ssid:
                return "Teléfono Móvil (Apple)"
            elif "airport" in ssid or "time" in ssid:
                return "Punto de Acceso (Apple)"
            else:
                return "Dispositivo Apple (Clase desconocida)"

        elif "samsung" in manufacturer:
            if "galaxy" in ssid or "smart" in ssid:
                return "Teléfono Móvil (Samsung)"
            elif "smarttv" in ssid or "tv" in ssid:
                return "Smart TV (Samsung)"
            else:
                return "Dispositivo Samsung (Clase desconocida)"

        elif "huawei" in manufacturer or "honor" in manufacturer:
            if "huawei" in ssid or "honor" in ssid:
                return "Teléfono Móvil (Huawei)"
            else:
                return "Dispositivo Huawei (Clase desconocida)"

        elif "xiaomi" in manufacturer:
            if "mi" in ssid or "redmi" in ssid:
                return "Teléfono Móvil (Xiaomi)"
            elif "miwifi" in ssid:
                return "Punto de Acceso (Xiaomi)"
            else:
                return "Dispositivo Xiaomi (Clase desconocida)"

        elif "google" in manufacturer:
            if "google" in ssid or "nest" in ssid:
                return "Dispositivo Google (Asistente/IoT)"
            else:
                return "Dispositivo Google (Clase desconocida)"

        elif "amazon" in manufacturer:
            return "Dispositivo Amazon (Echo/Asistente)"

        elif "tp-link" in manufacturer or "d-link" in manufacturer or "netgear" in manufacturer:
            return "Punto de Acceso (Router)"

        elif "intel" in manufacturer or "broadcom" in manufacturer:
            return "Dispositivo con chipset (Laptop/PC)"

    # Clasificación basada en patrón de RSSI (si no hay fabricante)
    if rssi_values:
        avg_rssi = sum(rssi_values) / len(rssi_values) if rssi_values else -80
        std_rssi = math.sqrt(sum((x - avg_rssi) ** 2 for x in rssi_values) / len(rssi_values)) if len(rssi_values) > 1 else 0

        # Dispositivos móviles suelen tener RSSI muy variables
        if std_rssi > 8:
            return "Dispositivo Móvil (Patrón RSSI variable)"
        # Puntos de acceso suelen tener RSSI más estables
        elif std_rssi < 3:
            return "Punto de Acceso (Patrón RSSI estable)"

    # Clasificación por defecto
    if "smart" in ssid or "tv" in ssid:
        return "Smart TV/Dispositivo IoT"
    elif "phone" in ssid or "mobile" in ssid or "galaxy" in ssid or "mi" in ssid:
        return "Teléfono Móvil"
    elif "wifi" in ssid or "router" in ssid or "ap" in ssid:
        return "Punto de Acceso"
    else:
        return "Dispositivo Genérico"

def analyze_rssi_fluctuation(bssid, window_size=60):
    """
    Analiza la fluctuación de RSSI para un BSSID específico.
    Devuelve un evento si se detecta movimiento significativo.
    """
    with lock:
        if bssid not in devices_map:
            return None

        device_data = devices_map[bssid]
        rssi_values = device_data.get('rssi_values', [])

        # Filtrar RSSI de los últimos 'window_size' segundos
        cutoff_time = datetime.now() - timedelta(seconds=window_size)
        recent_rssi = [rssi for rssi, timestamp in rssi_values if timestamp >= cutoff_time]

        if len(recent_rssi) < 3:  # Necesitamos al menos 3 muestras
            return None

        avg_rssi = sum(recent_rssi) / len(recent_rssi)
        variance = sum((x - avg_rssi) ** 2 for x in recent_rssi) / len(recent_rssi)
        std_dev = math.sqrt(variance)

        # Calcular confianza (0-1)
        confidence = min(1.0, max(0.0, (std_dev - MOVEMENT_THRESHOLD) / 10.0))

        if std_dev > MOVEMENT_THRESHOLD and confidence >= MIN_CONFIDENCE:
            return {
                "bssid": bssid,
                "event": "movement_detected",
                "confidence": round(confidence, 2),
                "std_dev": round(std_dev, 2),
                "avg_rssi": round(avg_rssi, 2),
                "timestamp": datetime.now().isoformat()
            }
        return None

def process_beacon_packet(packet):
    """
    Procesa un paquete Beacon y actualiza el mapa de dispositivos.
    """
    if not packet.haslayer(Dot11Beacon):
        return

    # Extraer información del paquete
    try:
        bssid = packet[Dot11].addr2
        ssid = packet[Dot11Elt].info.decode() if packet.haslayer(Dot11Elt) else "Hidden SSID"

        # Obtener RSSI (puede estar en RadioTap o en el paquete)
        rssi = -100  # Valor por defecto (muy débil)
        if packet.haslayer(RadioTap):
            rssi = packet[RadioTap].dBm_AntSignal
        elif packet.haslayer(Dot11Beacon) and hasattr(packet[Dot11Beacon], 'dBm_AntSignal'):
            rssi = packet[Dot11Beacon].dBm_AntSignal

        # Obtener fabricante
        manufacturer = get_oui_manufacturer(bssid)

        # Actualizar el mapa de dispositivos
        with lock:
            if bssid not in devices_map:
                devices_map[bssid] = {
                    'ssid': ssid,
                    'manufacturer': manufacturer,
                    'rssi_values': [],
                    'last_seen': datetime.now(),
                    'device_class': classify_device({
                        'ssid': ssid,
                        'manufacturer': manufacturer,
                        'rssi_values': []
                    }),
                    'location_estimate': None
                }

            # Actualizar datos del dispositivo
            device_data = devices_map[bssid]
            device_data['ssid'] = ssid
            device_data['manufacturer'] = manufacturer
            device_data['last_seen'] = datetime.now()
            device_data['rssi_values'].append((rssi, datetime.now()))

            # Limitar el tamaño de la ventana de RSSI
            cutoff_time = datetime.now() - timedelta(seconds=MAX_RSSI_WINDOW)
            device_data['rssi_values'] = [
                (rssi_val, ts) for rssi_val, ts in device_data['rssi_values']
                if ts >= cutoff_time
            ]

            # Analizar fluctuaciones de RSSI
            movement_event = analyze_rssi_fluctuation(bssid)
            if movement_event:
                with lock:
                    movement_events.append(movement_event)

    except Exception as e:
        print(f"⚠️ Error al procesar paquete Beacon: {e}")

def start_passive_monitor(interface="wlan0"):
    """
    Inicia el monitor pasivo de Wi-Fi en modo monitor.
    """
    try:
        # Verificar si la interfaz existe
        if interface not in get_if_list():
            print(f"❌ Interfaz {interface} no encontrada. Interfaces disponibles: {get_if_list()}")
            return False

        # Configurar la interfaz en modo monitor (requiere privilegios)
        print(f"🔧 Configurando interfaz {interface} en modo monitor...")
        os.system(f"sudo ifconfig {interface} down")
        os.system(f"sudo iwconfig {interface} mode monitor")
        os.system(f"sudo ifconfig {interface} up")

        # Verificar que la interfaz esté en modo monitor
        ifconfig_output = os.popen(f"iwconfig {interface}").read()
        if "Mode:Monitor" not in ifconfig_output:
            print(f"❌ No se pudo configurar {interface} en modo monitor.")
            return False

        print(f"✅ Interfaz {interface} configurada en modo monitor.")

        # Iniciar captura de paquetes en un hilo separado
        def capture_packets():
            print(f"📡 Iniciando captura pasiva en {interface}...")
            sniff(iface=interface,
                  prn=process_beacon_packet,
                  filter="type mgt subtype 8",  # Solo Beacon Frames
                  store=0,
                  timeout=None)

        # Iniciar el hilo de captura
        capture_thread = threading.Thread(target=capture_packets, daemon=True)
        capture_thread.start()

        return True

    except Exception as e:
        print(f"❌ Error al iniciar el monitor pasivo: {e}")
        return False

def get_system_interfaces():
    """Obtiene las interfaces de red disponibles en el sistema."""
    try:
        if platform.system() == "Windows":
            # En Windows, usar netsh
            import subprocess
            result = subprocess.run(['netsh', 'interface', 'show', 'interface'],
                                   capture_output=True, text=True)
            interfaces = []
            for line in result.stdout.split('\n'):
                if "Ethernet" in line or "Wireless" in line:
                    interface_name = line.split(':')[0].strip()
                    interfaces.append(interface_name)
            return interfaces
        else:
            # En Linux/macOS, usar ifconfig o ip
            return get_if_list()
    except:
        return []

def run_wifi_audit(interface=None):
    """
    Función principal para iniciar el motor de auditoría Wi-Fi.
    """
    global devices_map, movement_events

    # Obtener interfaz si no se proporciona
    if not interface:
        available_interfaces = get_system_interfaces()
        if not available_interfaces:
            print("❌ No se encontraron interfaces de red disponibles.")
            return False

        # Intentar encontrar una interfaz Wi-Fi
        wifi_interfaces = [iface for iface in available_interfaces if "wlan" in iface.lower()]
        if not wifi_interfaces:
            print("❌ No se encontraron interfaces Wi-Fi disponibles.")
            return False

        interface = wifi_interfaces[0]
        print(f"🔍 Usando interfaz Wi-Fi por defecto: {interface}")

    # Iniciar el monitor pasivo
    if not start_passive_monitor(interface):
        return False

    # Iniciar el servidor API en un hilo separado
    def run_api_server():
        print(f"🚀 Servidor API iniciado en http://localhost:{API_PORT}")
        app.run(port=API_PORT, host='127.0.0.1', threaded=True)

    api_thread = threading.Thread(target=run_api_server, daemon=True)
    api_thread.start()

    print(f"🎯 {MODULE_NAME} v{MODULE_VERSION} iniciado correctamente.")
    print(f"📌 Acceso al API: http://localhost:{API_PORT}/api/devices")
    print(f"📌 Interfaz de monitorización: {interface}")
    print(f"📌 Modo: Pasivo (solo captura Beacon Frames)")

    return True

# Endpoints de la API
@app.route('/api/devices', methods=['GET'])
def get_devices():
    """Devuelve el mapa completo de dispositivos detectados."""
    with lock:
        return jsonify({
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "devices": {
                bssid: {
                    "ssid": data["ssid"],
                    "manufacturer": data["manufacturer"],
                    "device_class": data["device_class"],
                    "last_seen": data["last_seen"].isoformat(),
                    "rssi_history": [
                        {"value": rssi, "timestamp": ts.isoformat()}
                        for rssi, ts in data["rssi_values"]
                    ],
                    "location_estimate": data["location_estimate"]
                }
                for bssid, data in devices_map.items()
            },
            "movement_events": [
                {
                    "bssid": event["bssid"],
                    "event": event["event"],
                    "confidence": event["confidence"],
                    "std_dev": event["std_dev"],
                    "avg_rssi": event["avg_rssi"],
                    "timestamp": event["timestamp"]
                }
                for event in movement_events
            ]
        })

@app.route('/api/health', methods=['GET'])
def health_check():
    """Verifica que el módulo esté funcionando correctamente."""
    with lock:
        return jsonify({
            "status": "success",
            "module": MODULE_NAME,
            "version": MODULE_VERSION,
            "devices_detected": len(devices_map),
            "movement_events": len(movement_events),
            "timestamp": datetime.now().isoformat()
        })

@app.route('/api/stop', methods=['POST'])
def stop_monitor():
    """Detiene el monitor pasivo (solo para pruebas)."""
    # En un entorno real, esto requeriría un mecanismo más robusto
    return jsonify({
        "status": "info",
        "message": "El módulo debe reiniciarse para detener el monitor.",
        "action": "Reinicia el script para detener la captura."
    })

if __name__ == "__main__":
    # Verificar dependencias
    try:
        import scapy
        from python_oui import lookup
    except ImportError as e:
        print(f"❌ Dependencias no instaladas: {e}")
        print("🔧 Instala las dependencias con: pip install scapy python-oui")
        sys.exit(1)

    # Obtener interfaz por línea de comandos o usar la primera disponible
    parser = argparse.ArgumentParser(description=f"{MODULE_NAME} - Motor de Auditoría Pasiva Wi-Fi")
    parser.add_argument("--interface", help="Interfaz Wi-Fi para monitorizar (ej: wlan0)", default=None)
    args = parser.parse_args()

    # Iniciar el motor de auditoría
    if not run_wifi_audit(args.interface):
        sys.exit(1)