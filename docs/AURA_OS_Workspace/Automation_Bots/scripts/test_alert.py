"""
test_alert.py - Script para enviar una alerta simulada al Decision Core
Este script simula una alerta de seguridad y envía una solicitud al Decision Core
para que procese la acción y la envíe a la Action Queue.
"""

import requests
import json
import time
from datetime import datetime

# Configuración del servidor
SERVER_URL = "http://localhost:5002/api/simulate"

def send_test_alert():
    """
    Envía una alerta simulada al Decision Core usando HTTP
    """
    # Datos de la alerta simulada
    alert_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "source": "security_threats",
        "id": f"test_alert_{int(time.time() * 1000)}",
        "type": "brute_force",
        "severity": "high",
        "title": "ALERTA: Intento de acceso no autorizado detectado",
        "description": "IP desconocida intentando acceder a servicios críticos",
        "details": [
            {"type": "source", "value": "198.51.100.78", "country": "RU", "asn": "AS12345"},
            {"type": "target", "value": "SSH", "port": 22, "attempts": 124},
            {"type": "pattern", "value": "admin:password123", "success": False}
        ],
        "metadata": {
            "ip": "198.51.100.78",
            "domain": "unknown.example.com",
            "port": 22,
            "confidence": 0.95,
            "last_seen": datetime.utcnow().isoformat()
        },
        "action_required": True,
        "action_type": "block_ip",
        "action_target": "198.51.100.78"
    }

    try:
        # Enviar la alerta al Decision Core
        print("Enviando alerta simulada al Decision Core...")
        response = requests.post(SERVER_URL, json=alert_data)

        if response.status_code == 200:
            print(f"Alerta enviada con éxito. Respuesta: {response.json()}")
            print("La alerta debería aparecer en la Action Queue para aprobación.")
        else:
            print(f"Error al enviar la alerta. Código de estado: {response.status_code}")
            print(f"Respuesta: {response.text}")

    except requests.exceptions.RequestException as e:
        print(f"Error de conexión: {str(e)}")

if __name__ == "__main__":
    print("Iniciando prueba de alerta simulada...")
    send_test_alert()
    print("Prueba completada.")