"""
NODO_RECON_PRO - Escaneo avanzado de puertos TCP con detección de OS y versiones.
"""

import os
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional
from scapy.all import *
from scapy.layers.inet import IP, TCP
from scapy.layers.l2 import Ether

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("NOD_RECON_PRO")

# Base de datos simplificada de firmas de OS
OS_FINGERPRINTS = {
    'Windows': {
        'ttl_range': (120, 130),
        'window_size_range': (512, 65535),
        'tcp_flags': ['SA', 'SAc', 'SAcR']
    },
    'Linux': {
        'ttl_range': (50, 70),
        'window_size_range': (5840, 65535),
        'tcp_flags': ['SA', 'SAc']
    },
    'Cisco': {
        'ttl_range': (250, 255),
        'window_size_range': (4096, 8192),
        'tcp_flags': ['SA']
    }
}

# Diccionario de servicios comunes
SERVICE_DB = {
    21: 'ftp',
    22: 'ssh',
    23: 'telnet',
    25: 'smtp',
    53: 'dns',
    80: 'http',
    110: 'pop3',
    143: 'imap',
    443: 'https',
    3306: 'mysql',
    3389: 'rdp',
    8080: 'http-alt'
}

def execute(input_data: Dict) -> Dict:
    """
    Ejecuta el escaneo de puertos TCP furtivo con detección de OS y versiones.

    INPUT_INTERFACE:
    {
        "target_ip": "string",
        "port_range": "string (ej: '1-65535')",
        "aggressive": "boolean"
    }

    OUTPUT_INTERFACE:
    {
        "target_ip": "string",
        "scan_timestamp": "string",
        "os_detected": "string",
        "open_ports": [{"port": int, "service": "string", "version": "string"}],
        "scan_duration": "float"
    }
    """
    # Validar entrada
    if not all(key in input_data for key in ['target_ip', 'port_range']):
        return {
            "target_ip": input_data.get('target_ip', ''),
            "scan_timestamp": datetime.now().isoformat(),
            "os_detected": "error",
            "open_ports": [],
            "scan_duration": 0.0,
            "error": "Faltan parámetros obligatorios (target_ip, port_range)"
        }

    target_ip = input_data['target_ip']
    port_range = input_data['port_range']
    aggressive = input_data.get('aggressive', False)

    # Procesar rango de puertos
    try:
        if '-' in port_range:
            start_port, end_port = map(int, port_range.split('-'))
        else:
            start_port = int(port_range)
            end_port = start_port
    except ValueError:
        return {
            "target_ip": target_ip,
            "scan_timestamp": datetime.now().isoformat(),
            "os_detected": "error",
            "open_ports": [],
            "scan_duration": 0.0,
            "error": "Formato de port_range inválido. Usar '1-65535' o '80'"
        }

    # Iniciar medición de tiempo
    start_time = time.time()

    # Configuración de paquetes SYN furtivos
    syn_packet = IP(dst=target_ip) / TCP(dport=0, flags="S")

    # Lista para almacenar puertos abiertos
    open_ports = []

    # Escaneo de puertos
    for port in range(start_port, end_port + 1):
        try:
            # Crear paquete SYN con puerto destino
            packet = syn_packet.copy()
            packet[TCP].dport = port

            # Enviar paquete y esperar respuesta
            response = sr1(packet, timeout=1, verbose=0)

            if response and response.haslayer(TCP):
                if response[TCP].flags == 0x12:  # SYN-ACK (puerto abierto)
                    open_ports.append({
                        'port': port,
                        'service': SERVICE_DB.get(port, f'unknown_{port}'),
                        'version': ''
                    })

                    # Si se requiere escaneo agresivo, intentar banner grabbing
                    if aggressive:
                        try:
                            # Intentar conexión TCP para banner grabbing
                            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            conn.settimeout(2)
                            conn.connect((target_ip, port))

                            # Enviar comando genérico para obtener banner
                            conn.send(b"\r\n")
                            banner = conn.recv(1024).decode().strip()
                            conn.close()

                            # Actualizar servicio y versión
                            if open_ports[-1]['service'] == f'unknown_{port}':
                                if 'http' in banner.lower() or 'apache' in banner.lower():
                                    open_ports[-1]['service'] = 'http'
                                elif 'ssh' in banner.lower():
                                    open_ports[-1]['service'] = 'ssh'
                                elif 'mysql' in banner.lower():
                                    open_ports[-1]['service'] = 'mysql'

                            open_ports[-1]['version'] = banner.split()[0] if banner else 'unknown'

                        except:
                            pass

        except Exception as e:
            logger.debug(f"Error en puerto {port}: {e}")
            continue

    # Detección de OS basada en TCP stack fingerprinting
    os_detected = "unknown"
    max_confidence = 0.0

    if open_ports:
        # Usar el primer puerto abierto para fingerprinting
        try:
            # Crear paquete SYN para fingerprinting
            fingerprint_packet = IP(dst=target_ip) / TCP(dport=open_ports[0]['port'], flags="S")
            response = sr1(fingerprint_packet, timeout=1, verbose=0)

            if response and response.haslayer(TCP):
                # Analizar TTL y Window Size
                ttl = response[IP].ttl
                window_size = response[TCP].window

                # Calcular confianza para cada OS
                for os_name, os_pattern in OS_FINGERPRINTS.items():
                    confidence = 0.0

                    # Verificar TTL
                    if os_pattern['ttl_range'][0] <= ttl <= os_pattern['ttl_range'][1]:
                        confidence += 0.4

                    # Verificar Window Size
                    if os_pattern['window_size_range'][0] <= window_size <= os_pattern['window_size_range'][1]:
                        confidence += 0.4

                    # Verificar flags TCP (simplificado)
                    if hasattr(response[TCP], 'flags') and str(response[TCP].flags) in os_pattern['tcp_flags']:
                        confidence += 0.2

                    # Actualizar mejor coincidencia
                    if confidence > max_confidence:
                        max_confidence = confidence
                        os_detected = os_name

        except Exception as e:
            logger.debug(f"Error en fingerprinting: {e}")

    # Calcular duración del escaneo
    scan_duration = time.time() - start_time

    return {
        "target_ip": target_ip,
        "scan_timestamp": datetime.now().isoformat(),
        "os_detected": os_detected,
        "open_ports": open_ports,
        "scan_duration": round(scan_duration, 2)
    }

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NOD_RECON_PRO - Escaneo avanzado de puertos TCP")
    parser.add_argument("target_ip", help="Dirección IP objetivo")
    parser.add_argument("port_range", help="Rango de puertos (ej: '1-65535' o '80')")
    parser.add_argument("--aggressive", action="store_true", help="Habilitar escaneo agresivo con banner grabbing")
    args = parser.parse_args()

    input_data = {
        "target_ip": args.target_ip,
        "port_range": args.port_range,
        "aggressive": args.aggressive
    }

    result = execute(input_data)
    print(result)