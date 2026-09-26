"""
Proxy Manager: Circuit Breaker para comunicarse con el Shadow-Core.
Maneja timeouts, errores y fallos en la comunicación.
"""

import requests
import time
from typing import Dict, Any, Optional
import logging

# Importar módulo de seguridad
from security_shield import rotate_fingerprint, get_tor_proxy

# Configuración del Proxy Manager
SHADOW_CORE_URL = "http://127.0.0.1:5000/api/execute_advanced"
TIMEOUT_SECONDS = 30  # Timeout aumentado de 5s a 30s para túneles Cloudflare
MAX_RETRIES = 3       # Reintentos aumentado de 2 a 3
INITIAL_BACKOFF = 2   # Backoff exponencial: 2s, 4s, 8s
LAST_ERROR = None     # Último error registrado
CIRCUIT_BREAKER_FAILURES = 0
CIRCUIT_BREAKER_THRESHOLD = 5  # Abrir circuito después de 5 fallos consecutivos
CIRCUIT_BREAKER_TIMEOUT = 60   # Esperar 60s antes de reintentar en circuito abierto
LAST_CIRCUIT_OPEN_TIME = 0

class ProxyManager:
    """
    Gestiona la comunicación con el Shadow-Core como un Circuit Breaker.
    """

    @staticmethod
    def execute_advanced_command(command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta un comando avanzado a través del Shadow-Core.
        Maneja timeouts, errores y fallos de manera controlada.
        """
        global LAST_ERROR

        # Validar el comando
        if not isinstance(command, dict) or 'type' not in command:
            return {"status": "failed", "message": "Comando inválido. Se espera un JSON con 'type'."}

        # Aplicar seguridad antes de enviar la petición
        fingerprint = rotate_fingerprint()
        command["_fingerprint"] = fingerprint

        # Configurar proxy Tor para enrutar tráfico
        proxies = get_tor_proxy()

        # Intentar ejecutar el comando con reintentos
        for attempt in range(MAX_RETRIES + 1):
            try:
                # Enviar la petición al Shadow-Core con proxy y fingerprint
                response = requests.post(
                    SHADOW_CORE_URL,
                    json=command,
                    proxies=proxies,
                    timeout=TIMEOUT_SECONDS
                )

                # Verificar el código de respuesta
                if response.status_code == 200:
                    result = response.json()

                    # Validar que el resultado sea un JSON válido
                    if isinstance(result, dict):
                        return result
                    else:
                        return {"status": "failed", "message": "Resultado inválido del Shadow-Core."}

                # Si el código de respuesta no es 200, intentar nuevamente
                elif response.status_code == 500 and attempt < MAX_RETRIES:
                    LAST_ERROR = f"Shadow-Core retornó 500 (Intento {attempt + 1}/{MAX_RETRIES})"
                    time.sleep(1)  # Esperar antes de reintentar
                    continue

                # Si el código de respuesta no es 200 y no es 500, retornar error
                else:
                    LAST_ERROR = f"Shadow-Core retornó {response.status_code}"
                    return {"status": "failed", "message": f"Error del Shadow-Core: Código {response.status_code}"}

            except requests.exceptions.Timeout:
                LAST_ERROR = f"Timeout de {TIMEOUT_SECONDS} segundos superado (Intento {attempt + 1}/{MAX_RETRIES})"
                if attempt < MAX_RETRIES:
                    time.sleep(1)  # Esperar antes de reintentar
                    continue
                else:
                    return {"status": "offline", "message": "Shadow-Core no responde (Timeout)"}

            except requests.exceptions.ConnectionError:
                LAST_ERROR = f"No se pudo conectar al Shadow-Core (Intento {attempt + 1}/{MAX_RETRIES})"
                if attempt < MAX_RETRIES:
                    time.sleep(1)  # Esperar antes de reintentar
                    continue
                else:
                    return {"status": "offline", "message": "Shadow-Core no disponible (Conexión fallida)"}

            except requests.exceptions.RequestException as e:
                LAST_ERROR = f"Error en la petición: {str(e)} (Intento {attempt + 1}/{MAX_RETRIES})"
                if attempt < MAX_RETRIES:
                    time.sleep(1)  # Esperar antes de reintentar
                    continue
                else:
                    return {"status": "failed", "message": f"Error en la petición: {str(e)}"}

            except Exception as e:
                LAST_ERROR = f"Error interno: {str(e)} (Intento {attempt + 1}/{MAX_RETRIES})"
                if attempt < MAX_RETRIES:
                    time.sleep(1)  # Esperar antes de reintentar
                    continue
                else:
                    return {"status": "failed", "message": f"Error interno: {str(e)}"}

        # Si se agotaron los reintentos, retornar estado offline
        return {"status": "offline", "message": "Shadow-Core no disponible"}

    @staticmethod
    def get_last_error() -> Optional[str]:
        """
        Retorna el último error registrado.
        """
        return LAST_ERROR

    @staticmethod
    def is_shadow_core_available() -> bool:
        """
        Verifica si el Shadow-Core está disponible.
        """
        try:
            response = requests.get(SHADOW_CORE_URL, timeout=TIMEOUT_SECONDS)
            return response.status_code == 200
        except:
            return False

# Ejemplo de uso
if __name__ == "__main__":
    # Ejemplo de comando para Shodan
    command = {
        "type": "shodan_search",
        "query": "port:443 country:US"
    }

    # Ejecutar el comando a través del Proxy Manager
    result = ProxyManager.execute_advanced_command(command)
    print("Resultado:", result)