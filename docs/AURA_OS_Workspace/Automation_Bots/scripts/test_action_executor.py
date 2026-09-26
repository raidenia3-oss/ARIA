"""
test_action_executor.py - Script para probar el Action Executor
Este script simula una acción aprobada y verifica que se guarde correctamente en Obsidian.
"""

import requests
import json
import time
from datetime import datetime
import os
import sys

# Configuración del servidor
ACTION_EXECUTOR_URL = "http://localhost:5003/execute_action"

def test_action_executor():
    """
    Prueba el Action Executor enviando una acción simulada de guardar en Obsidian
    """
    # Datos de la acción simulada (similar a una alerta OSINT)
    action_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "source": "osint_news",
        "id": f"test_action_{int(time.time() * 1000)}",
        "type": "security_news",
        "severity": "medium",
        "title": "Prueba de Action Executor - Vulnerabilidad crítica detectada",
        "description": "Se ha detectado una vulnerabilidad crítica en un sistema popular. "
                       "Los detalles técnicos indican que podría ser explotada para "
                       "obtener acceso no autorizado a sistemas internos.",
        "details": [
            {"type": "url", "value": "https://example.com/security/alert"},
            {"type": "source", "value": "The Hacker News"},
            {"type": "published", "value": datetime.utcnow().isoformat()},
            {"type": "keywords", "value": ["vulnerability", "critical", "exploit"]}
        ],
        "metadata": {
            "url": "https://example.com/security/alert",
            "source": "The Hacker News",
            "confidence": 0.95,
            "last_seen": datetime.utcnow().isoformat(),
            "published": datetime.utcnow().isoformat()
        },
        "action_required": True,
        "action_type": "save_to_obsidian",
        "action_target": "Vulnerabilidad crítica detectada"
    }

    try:
        # Enviar la acción al Action Executor usando HTTP POST
        print("Enviando acción aprobada al Action Executor...")
        response = requests.post(ACTION_EXECUTOR_URL, json=action_data)

        if response.status_code == 200:
            result = response.json()
            print(f"Respuesta del Action Executor: {result}")

            if result.get('status') == 'success':
                print("✅ La acción se ejecutó con éxito!")
                print(f"Archivo guardado: {result.get('message', 'Desconocido')}")
            else:
                print(f"❌ Error al ejecutar la acción: {result.get('message', 'Desconocido')}")
        else:
            print(f"Error en la solicitud HTTP. Código de estado: {response.status_code}")
            print(f"Respuesta: {response.text}")

    except Exception as e:
        print(f"Error al probar el Action Executor: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Iniciando prueba del Action Executor...")
    test_action_executor()
    print("Prueba completada.")