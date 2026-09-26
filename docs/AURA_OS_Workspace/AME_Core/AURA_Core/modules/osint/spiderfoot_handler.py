import subprocess
import json
import logging
import time
import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Configuración de logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Configuración de SpiderFoot (asumimos que está instalado y configurado para API o CLI)
SPIDERFOOT_HOST = os.getenv("SPIDERFOOT_HOST", "http://127.0.0.1:5001")
SPIDERFOOT_API_KEY = os.getenv("SPIDERFOOT_API_KEY") # Opcional si no se usa la API, pero bueno tenerlo

def run_command(command):
    """
    Ejecuta un comando del sistema y captura su salida.
    """
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=600)  # 10 minutos de timeout
        return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}
    except subprocess.CalledProcessError as e:
        logger.error(f"Comando SpiderFoot fallido: {e.cmd}, Error: {e.stderr}")
        return {"stdout": e.stdout, "stderr": e.stderr, "returncode": e.returncode}
    except subprocess.TimeoutExpired as e:
        logger.error(f"Comando SpiderFoot excedió el tiempo de espera: {e.cmd}, Timeout: {e.timeout}")
        return {"stdout": e.stdout.decode(), "stderr": e.stderr.decode() + "\nError: Tiempo de espera excedido.", "returncode": -1}
    except FileNotFoundError:
        logger.error(f"Comando SpiderFoot no encontrado. Asegúrate de que SpiderFoot esté instalado y en el PATH.")
        return {"stdout": "", "stderr": "Error: Herramienta SpiderFoot no encontrada. Instala SpiderFoot.", "returncode": 127}
    except Exception as e:
        logger.error(f"Error inesperado al ejecutar SpiderFoot: {e}")
        return {"stdout": "", "stderr": f"Error inesperado: {e}", "returncode": 1}

def start_spiderfoot_scan_cli(target):
    """
    Inicia un escaneo de SpiderFoot a través de la línea de comandos y espera a que termine.
    Esto asume que SpiderFoot CLI está disponible.
    Nota: Para escaneos en segundo plano y recolección de resultados programática,
    es preferible usar la API de SpiderFoot si el servidor está corriendo.
    """
    logger.info(f"Iniciando escaneo SpiderFoot CLI para el objetivo: {target}")
    # Ejemplo de comando SpiderFoot CLI. Ajusta según tu instalación y módulos.
    # Por simplicidad, un escaneo básico. En un caso real, se especificarían módulos (-m) y output (-o).
    command = ["spiderfoot", "-s", target, "-o", "json,", "stdout"]
    return run_command(command)

def start_spiderfoot_scan_api(target, modules="all"):
    """
    Inicia un escaneo de SpiderFoot a través de su API.
    Requiere que el servidor SpiderFoot esté corriendo (sf.py -l 127.0.0.1:5001) y API_KEY configurada.
    """
    logger.info(f"Iniciando escaneo SpiderFoot API para el objetivo: {target} con módulos: {modules}")
    if not SPIDERFOOT_API_KEY:
        return {"tool": "SpiderFoot", "target": target, "status": "error", "message": "SPIDERFOOT_API_KEY no configurada para la API."}
    
    headers = {"Content-Type": "application/json", "x-api-key": SPIDERFOOT_API_KEY}
    start_scan_url = f"{SPIDERFOOT_HOST}/api/v1/scans"
    
    payload = {"target": target, "moduleGroups": [modules], "scanName": f"AURA_OSINT_Scan_{target}_{int(time.time())}"}
    
    try:
        response = requests.post(start_scan_url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        scan_info = response.json()
        scan_id = scan_info.get("scanId")
        if scan_id:
            logger.info(f"Escaneo SpiderFoot API iniciado, ID: {scan_id}")
            return {"tool": "SpiderFoot", "target": target, "status": "initiated", "scan_id": scan_id, "message": "Escaneo SpiderFoot iniciado vía API."}
        else:
            logger.error(f"No se pudo obtener el scanId de la respuesta de SpiderFoot: {response.text}")
            return {"tool": "SpiderFoot", "target": target, "status": "error", "message": f"No se pudo iniciar el escaneo vía API: {response.text}"}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error al iniciar escaneo SpiderFoot vía API: {e}")
        return {"tool": "SpiderFoot", "target": target, "status": "error", "message": f"Error de conexión o API: {e}"}

def get_spiderfoot_scan_results(scan_id):
    """
    Obtiene los resultados de un escaneo de SpiderFoot por su ID.
    """
    logger.info(f"Obteniendo resultados de escaneo SpiderFoot para ID: {scan_id}")
    if not SPIDERFOOT_API_KEY:
        return {"tool": "SpiderFoot", "scan_id": scan_id, "status": "error", "message": "SPIDERFOOT_API_KEY no configurada para la API."}

    headers = {"x-api-key": SPIDERFOOT_API_KEY}
    results_url = f"{SPIDERFOOT_HOST}/api/v1/scans/{scan_id}/elements?eventtypes=ALL"
    
    try:
        response = requests.get(results_url, headers=headers, timeout=120)
        response.raise_for_status()
        elements = response.json()
        return {"tool": "SpiderFoot", "scan_id": scan_id, "status": "completed", "results": elements}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error al obtener resultados de SpiderFoot vía API para ID {scan_id}: {e}")
        return {"tool": "SpiderFoot", "scan_id": scan_id, "status": "error", "message": f"Error al obtener resultados vía API: {e}"}


# Ejemplo de uso (para pruebas)
if __name__ == "__main__":
    target_test = "example.com"

    # Probar CLI (puede ser lento y requiere SpiderFoot CLI en PATH)
    # print("--- Probando SpiderFoot CLI (puede tomar varios minutos) ---")
    # cli_result = start_spiderfoot_scan_cli(target_test)
    # print(json.dumps(cli_result, indent=2))

    print("\n--- Probando SpiderFoot API (requiere servidor SpiderFoot y API Key) ---")
    # Asegúrate de que SpiderFoot esté corriendo en modo servidor y tengas la SPIDERFOOT_API_KEY en .env
    # Ejemplo de cómo iniciar el servidor SpiderFoot: python sf.py -l 127.0.0.1:5001
    
    # 1. Iniciar escaneo
    api_init_result = start_spiderfoot_scan_api(target_test, modules="all")
    print(json.dumps(api_init_result, indent=2))

    if api_init_result["status"] == "initiated":
        scan_id_test = api_init_result["scan_id"]
        print(f"Esperando a que el escaneo {scan_id_test} termine (simulado)...")
        time.sleep(30) # Esperar un tiempo prudencial para que el escaneo avance

        # 2. Obtener resultados
        api_results = get_spiderfoot_scan_results(scan_id_test)
        print(json.dumps(api_results, indent=2))
    else:
        print("No se pudo iniciar el escaneo vía API. Verifica configuración y servidor.")
