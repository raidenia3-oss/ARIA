import requests
import json
import logging
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import os

load_dotenv()

# Configuración de logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fetch_url(url, method="GET", data=None, headers=None, json_data=None, timeout=30):
    """
    Realiza una solicitud HTTP y maneja errores comunes.
    """
    try:
        if method.upper() == "POST":
            response = requests.post(url, data=data, json=json_data, headers=headers, timeout=timeout)
        else:
            response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status() # Lanza un HTTPError para códigos de estado 4xx/5xx
        return {"status": "success", "data": response.text, "json": response.json() if response.headers.get("Content-Type", "").startswith("application/json") else None}
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP Error para {url}: {e.response.status_code} - {e.response.text}")
        return {"status": "error", "message": f"HTTP Error: {e.response.status_code} - {e.response.text}"}
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
        return {"status": "success", "data": response.text, "json": None}
    except Exception as e:
        logger.error(f"Error inesperado al buscar {url}: {e}")
        return {"status": "error", "message": f"Error inesperado: {e}"}

def search_whatsmyname(username):
    """
    Simula la búsqueda en 'What's My Name' para un nombre de usuario.
    Nota: Esta herramienta es interactiva o requiere un wrapper CLI. 
    Aquí se simula una búsqueda genérica para plataformas comunes.
    Para una integración completa, se debería usar la CLI de whatsamename o una API de un servicio similar.
    """
    logger.info(f"Buscando nombre de usuario \'{username}\' en plataformas populares (simulado).")
    # Lista de sitios de ejemplo para simular la búsqueda
    sites = ["twitter.com", "facebook.com", "instagram.com", "github.com"]
    results = {}
    for site in sites:
        profile_url = f"https://{site}/{username}"
        # Simulación básica: se considera "encontrado" si el perfil de ejemplo no devuelve 404
        # En un escenario real, se usaría la herramienta whatsamename o APIs específicas.
        # Para propósitos de demostración, esto es un placeholder.
        response = fetch_url(profile_url)
        if response["status"] == "success" and response["returncode"] != 404:
            results[site] = {"found": True, "url": profile_url}
        else:
            results[site] = {"found": False, "url": profile_url, "error": response.get("message", "")}
    return {"tool": "What_s_My_Name", "target": username, "results": results}

def search_epio(email):
    """
    Realiza rastreo de correos y perfiles de Google usando Epio (simulado/conceptual).
    Nota: Epio es una herramienta más avanzada que requiere acceso a datos específicos o una integración directa.
    Aquí se hace una simulación conceptual. Para una integración real, se necesitaría un acceso a API o un wrapper para Epio.
    """
    logger.info(f"Rastreando correo electrónico \'{email}\' con Epio (conceptual).")
    results = {"google_profile": None, "associated_emails": [], "data_points": []}
    # Simular una búsqueda de perfil de Google
    google_search_url = f"https://www.google.com/search?q=\"{email}\" site:plus.google.com"
    response = fetch_url(google_search_url)
    if response["status"] == "success" and response["data"]:
        soup = BeautifulSoup(response["data"], "html.parser")
        # Aquí se debería parsear el HTML para encontrar enlaces relevantes o menciones.
        # Esto es altamente dependiente de la estructura actual de Google y puede romperse fácilmente.
        # Por ahora, es un placeholder.
        if "plus.google.com" in response["data"]: # Placeholder de busqueda muy básica
            results["google_profile"] = f"Posible perfil de Google encontrado para {email}"
            results["data_points"].append("Google search mentions email")
    
    # Simular búsqueda de brechas para este email (complemento con HIBP)
    hibp_result = check_haveibeenpwned(email)
    if hibp_result["status"] == "success" and hibp_result["breaches"]:
        results["associated_emails"].append(
            f"Brechas encontradas en HIBP: {len(hibp_result['breaches'])} subdominios"
        )

    return {"tool": "Epio", "target": email, "results": results}

def check_haveibeenpwned(email):
    """
    Verifica brechas de datos usando la API de Have I Been Pwned (HIBP).
    Requiere una clave API de HIBP si se excede el rate limiting sin autenticación.
    """
    logger.info(f"Verificando brechas para el correo: {email}" )
    HIBP_API_KEY = os.getenv("HIBP_API_KEY")
    headers = {"User-Agent": "AURA-OSINT-Tool", "hibp-api-key": HIBP_API_KEY} if HIBP_API_KEY else {"User-Agent": "AURA-OSINT-Tool"}
    url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}"
    
    response = fetch_url(url, headers=headers)
    
    if response["status"] == "success":
        return {"tool": "Have_I_Been_Pwned", "target": email, "breaches": response["json"] if response["json"] else []}
    else:
        return {"tool": "Have_I_Been_Pwned", "target": email, "breaches": [], "error": response["message"]}

# Ejemplo de uso (para pruebas)
if __name__ == "__main__":
    print("--- Probando What_s_My_Name (simulado) ---")
    whatsmyname_result = search_whatsmyname("johndoe123")
    print(json.dumps(whatsmyname_result, indent=2))

    print("\n--- Probando Have_I_Been_Pwned ---")
    # Asegúrate de tener la variable de entorno HIBP_API_KEY configurada si excedes el rate limit.
    hibp_result = check_haveibeenpwned("test@example.com")
    print(json.dumps(hibp_result, indent=2))

    print("\n--- Probando Epio (conceptual) ---")
    epio_result = search_epio("test@example.com")
    print(json.dumps(epio_result, indent=2))
