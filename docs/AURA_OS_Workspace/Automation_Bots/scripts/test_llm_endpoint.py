import requests
import json

# Configuración del endpoint
url = "http://127.0.0.1:5000/api/llm/query"
headers = {"Content-Type": "application/json"}

# Payload con codificación UTF-8 correcta
payload = {
    "prompt": "¿Cómo puedo mejorar la seguridad en un sistema de OSINT como AURA?"
}

try:
    # Enviar solicitud POST
    response = requests.post(url, headers=headers, json=payload)
    print("Respuesta del servidor:")
    print(f"Código de estado: {response.status_code}")
    print(f"Respuesta: {response.text}")
except requests.exceptions.RequestException as e:
    print(f"Error al enviar la solicitud: {e}")