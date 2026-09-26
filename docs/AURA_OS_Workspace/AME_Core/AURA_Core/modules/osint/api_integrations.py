import requests
import json
import logging
import os
from dotenv import load_dotenv

load_dotenv()

# Configuración de logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fetch_api_data(url, headers=None, params=None, timeout=30):
    """
    Realiza una solicitud GET a una API y maneja errores comunes.
    """
    try:
        response = requests.get(url, headers=headers, params=params, timeout=timeout)
        response.raise_for_status()  # Lanza un HTTPError para códigos de estado 4xx/5xx
        return {"status": "success", "data": response.json(), "raw_response": response.text}
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP Error para {url}: {e.response.status_code} - {e.response.text}")
        return {"status": "error", "message": f"HTTP Error: {e.response.status_code} - {e.response.text}", "raw_response": e.response.text}
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Error de conexión para {url}: {e}")
        return {"status": "error", "message": f"Error de conexión: {e}"}
    except requests.exceptions.Timeout as e:
        logger.error(f"Timeout para {url}: {e}")
        return {"status": "error", "message": f"Tiempo de espera excedido: {e}"}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error de solicitud para {url}: {e}")
        return {"status": "error", "message": f"Error de solicitud: {e}"}
    except json.JSONDecodeError:
        logger.warning(f"No se pudo decodificar JSON de {url}. Devolviendo texto plano.")
        return {"status": "success", "data": None, "raw_response": response.text, "message": "Respuesta no JSON"}
    except Exception as e:
        logger.error(f"Error inesperado al buscar {url}: {e}")
        return {"status": "error", "message": f"Error inesperado: {e}"}

def shodan_search(query):
    """
    Realiza una búsqueda en Shodan para dispositivos IoT expuestos.
    Requiere SHODAN_API_KEY configurada como variable de entorno.
    """
    logger.info(f"Realizando búsqueda en Shodan para: {query}")
    SHODAN_API_KEY = os.getenv("SHODAN_API_KEY")
    if not SHODAN_API_KEY:
        return {"tool": "Shodan", "target": query, "results": [], "error": "SHODAN_API_KEY no configurada."}

    url = f"https://api.shodan.io/shodan/host/search?key={SHODAN_API_KEY}&query={query}"
    response = fetch_api_data(url)

    if response["status"] == "success" and response["data"]:
        return {"tool": "Shodan", "target": query, "results": response["data"].get("matches", [])}
    else:
        return {"tool": "Shodan", "target": query, "results": [], "error": response["message"]}

def intelx_search(query, search_type="selectors"):
    """
    Realiza una búsqueda profunda en Intel X para filtraciones.
    Requiere INTELX_API_KEY y INTELX_HOST configuradas como variables de entorno.
    search_type puede ser 'selectors' (emails, domains, IPs), 'data' (contenido) o 'files'.
    """
    logger.info(f"Realizando búsqueda en Intel X para: {query} (tipo: {search_type})")
    INTELX_API_KEY = os.getenv("INTELX_API_KEY")
    INTELX_HOST = os.getenv("INTELX_HOST", "https://public.api.intelx.io")

    if not INTELX_API_KEY:
        return {"tool": "IntelX", "target": query, "results": [], "error": "INTELX_API_KEY no configurada."}

    if not INTELX_HOST:
        return {"tool": "IntelX", "target": query, "results": [], "error": "INTELX_HOST no configurada."}

    # Intel X requiere un paso de "buscar" para obtener un ID de búsqueda, y luego "obtener resultados".
    # Esto es una implementación simplificada para el propósito del wrapper.
    # Para una integración completa, se necesitarían dos llamadas a la API.
    search_url = f"{INTELX_HOST}/v1/intelligence/search"
    headers = {"x-api-key": INTELX_API_KEY, "Content-Type": "application/json"}
    post_data = {
        "term": query,
        "maxresults": 100,
        "media": 0, # Todos los medios
        "terminateonmaxresults": True,
        "waituntilcomplete": True # Esperar a que la búsqueda esté completa
    }

    # Simular la búsqueda (Intel X es más complejo de automatizar directamente en una sola llamada)
    response = fetch_api_data(search_url, method="POST", json_data=post_data, headers=headers)
    
    if response["status"] == "success" and response["data"]:
        search_id = response["data"].get("id")
        if search_id:
            # En un entorno real, se haría otra llamada para obtener los resultados con el search_id.
            # Por simplicidad, aquí se devuelve el ID de búsqueda como un "resultado" simbólico.
            return {"tool": "IntelX", "target": query, "results": [{"type": "search_id", "value": search_id, "message": "Búsqueda en Intel X iniciada. Usa el ID para obtener resultados completos."}]}
        else:
            return {"tool": "IntelX", "target": query, "results": [], "error": "No se pudo iniciar la búsqueda en Intel X."}
    else:
        return {"tool": "IntelX", "target": query, "results": [], "error": response["message"]}


# Ejemplo de uso (para pruebas)
if __name__ == "__main__":
    # Asegúrate de configurar SHODAN_API_KEY, INTELX_API_KEY y INTELX_HOST en tu .env
    print("--- Probando Shodan ---")
    shodan_res = shodan_search("nginx country:US")
    print(json.dumps(shodan_res, indent=2))

    print("\n--- Probando Intel X (simulado) ---")
    intelx_res = intelx_search("example@domain.com", "selectors")
    print(json.dumps(intelx_res, indent=2))
