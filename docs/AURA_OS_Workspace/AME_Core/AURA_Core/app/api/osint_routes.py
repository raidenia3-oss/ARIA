"""
OSINT Recon Suite - FastAPI Router
Endpoint central para ejecutar las 10 herramientas OSINT en paralelo.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import asyncio
import logging
import time

# Importar módulos OSINT
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'modules', 'osint'))

from harvester_recon import run_theharvester, run_recon_ng
from web_scrapers import search_whatsmyname, search_epio, check_haveibeenpwned
from api_integrations import shodan_search, intelx_search
from spiderfoot_handler import start_spiderfoot_scan_api, get_spiderfoot_scan_results

# Configuración de logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/osint", tags=["OSINT Recon Suite"])

# ─── Modelos de datos ───
class OSINTRequest(BaseModel):
    target: str
    target_type: str = "auto"  # "username", "email", "domain", "ip", "auto"
    tools: Optional[list] = None  # Lista de herramientas específicas a ejecutar, None = todas

class GoogleDorkRequest(BaseModel):
    term: str
    file_type: str = "pdf"  # pdf, doc, xls, ppt, etc.
    site: Optional[str] = None  # Sitio específico opcional

# ─── Funciones auxiliares de detección ───
def detect_target_type(target: str) -> str:
    """Detecta automáticamente el tipo de objetivo."""
    import re
    if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', target):
        return "email"
    if re.match(r'^\d{1,3}(\.\d{1,3}){3}$', target):
        return "ip"
    if re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z]{2,})+$', target):
        return "domain"
    return "username"

# ─── Ejecución paralela de herramientas ───
async def run_tool_async(tool_func, *args, **kwargs):
    """Ejecuta una función de herramienta de forma asíncrona con manejo de errores."""
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: tool_func(*args, **kwargs))
        return result
    except Exception as e:
        logger.error(f"Error en herramienta {tool_func.__name__}: {e}")
        return {"tool": tool_func.__name__, "status": "error", "message": str(e)}

async def execute_osint_tools(target: str, target_type: str, tools: list = None):
    """Ejecuta las herramientas OSINT relevantes en paralelo."""
    tasks = []
    
    # Determinar qué herramientas ejecutar según el tipo de objetivo
    if target_type == "email":
        tasks.append(("HIBP", run_tool_async(check_haveibeenpwned, target)))
        tasks.append(("Epio", run_tool_async(search_epio, target)))
        tasks.append(("What_s_My_Name", run_tool_async(search_whatsmyname, target)))
        tasks.append(("IntelX", run_tool_async(intelx_search, target, "selectors")))
        tasks.append(("Harvester", run_tool_async(run_theharvester, target)))
    elif target_type == "username":
        tasks.append(("What_s_My_Name", run_tool_async(search_whatsmyname, target)))
        tasks.append(("Harvester", run_tool_async(run_theharvester, target)))
        tasks.append(("IntelX", run_tool_async(intelx_search, target, "selectors")))
    elif target_type == "domain":
        tasks.append(("Harvester", run_tool_async(run_theharvester, target)))
        tasks.append(("Shodan", run_tool_async(shodan_search, f"hostname:{target}")))
        tasks.append(("SpiderFoot", run_tool_async(start_spiderfoot_scan_api, target)))
        tasks.append(("What_s_My_Name", run_tool_async(search_whatsmyname, target)))
    elif target_type == "ip":
        tasks.append(("Shodan", run_tool_async(shodan_search, f"ip:{target}")))
        tasks.append(("Harvester", run_tool_async(run_theharvester, target)))
    
    # Si se especificaron herramientas específicas, filtrar
    if tools:
        tasks = [(name, task) for name, task in tasks if name.lower() in [t.lower() for t in tools]]
    
    # Ejecutar todas las tareas en paralelo
    if not tasks:
        return []
    
    results = []
    task_names = [name for name, _ in tasks]
    task_coros = [task for _, task in tasks]
    
    logger.info(f"Ejecutando {len(tasks)} herramientas OSINT en paralelo para: {target}")
    gathered = await asyncio.gather(*task_coros, return_exceptions=True)
    
    for name, result in zip(task_names, gathered):
        if isinstance(result, Exception):
            results.append({"tool": name, "status": "error", "message": str(result)})
        else:
            results.append(result)
    
    return results

# ─── Endpoints ───

@router.get("/health")
async def health_check():
    """Verifica el estado del módulo OSINT."""
    return {
        "status": "active",
        "module": "OSINT Recon Suite",
        "version": "1.0.0",
        "tools_available": [
            "theHarvester", "recon-ng", "What's My Name", "Epio",
            "Have I Been Pwned", "Shodan", "Intel X", "SpiderFoot",
            "Google Dorks Generator", "OSINT Framework Menu"
        ]
    }

@router.post("/scan-target")
async def scan_target(request: OSINTRequest):
    """
    Ejecuta las herramientas OSINT correspondientes al tipo de objetivo.
    Acepta username, email, dominio o IP.
    Devuelve un JSON estructurado, unificado y limpio.
    """
    start_time = time.time()
    
    # Detectar tipo de objetivo si es automático
    target_type = request.target_type
    if target_type == "auto":
        target_type = detect_target_type(request.target)
    
    # Validar tipo de objetivo
    valid_types = ["username", "email", "domain", "ip"]
    if target_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Tipo de objetivo inválido: {target_type}. Usa: {valid_types}")
    
    # Ejecutar herramientas en paralelo
    raw_results = await execute_osint_tools(request.target, target_type, request.tools)
    
    # Unificar y limpiar resultados
    unified_results = {
        "target": request.target,
        "target_type": target_type,
        "scan_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "execution_time_seconds": round(time.time() - start_time, 2),
        "tools_executed": len(raw_results),
        "tools_with_results": sum(1 for r in raw_results if r.get("status") != "error" and r.get("results")),
        "sections": {}
    }
    
    # Organizar resultados por sección
    for result in raw_results:
        tool_name = result.get("tool", result.get("module", "unknown"))
        if result.get("status") == "error":
            unified_results["sections"][tool_name] = {
                "status": "error",
                "error": result.get("message", "Error desconocido")
            }
        else:
            unified_results["sections"][tool_name] = {
                "status": "success",
                "data": result.get("results", result.get("breaches", result.get("data", [])))
            }
    
    return unified_results

@router.post("/google-dork")
async def generate_google_dork(request: GoogleDorkRequest):
    """
    Genera un enlace de Google Dorks basado en el término y tipo de archivo.
    Abre automáticamente el navegador con la sintaxis correcta.
    """
    # Construir la query de Google Dork
    dork_query = f'filetype:{request.file_type} "{request.term}"'
    if request.site:
        dork_query += f' site:{request.site}'
    
    google_url = f"https://www.google.com/search?q={dork_query.replace(' ', '+')}"
    
    return {
        "status": "success",
        "dork_query": dork_query,
        "google_url": google_url,
        "instructions": "Copia y pega esta URL en tu navegador, o haz clic en el enlace.",
        "file_type": request.file_type,
        "term": request.term,
        "site": request.site
    }

@router.get("/framework-tree")
async def get_osint_framework_tree():
    """
    Devuelve un árbol de categorías basado en OSINT Framework para exploración manual.
    """
    framework_tree = {
        "name": "OSINT Framework",
        "categories": [
            {
                "name": "Identity",
                "icon": "👤",
                "tools": [
                    {"name": "Namechk", "url": "https://namechk.com", "description": "Verifica disponibilidad de usernames"},
                    {"name": "WhatsMyName", "url": "https://whatsmyname.app", "description": "Busca perfiles en 1500+ sitios"},
                    {"name": " Sherlock", "url": "https://github.com/sherlock-project/sherlock", "description": "Busca usernames en redes sociales"},
                    {"name": "KnowEm", "url": "https://knowem.com", "description": "Busca usernames en 500+ redes sociales"}
                ]
            },
            {
                "name": "Email",
                "icon": "📧",
                "tools": [
                    {"name": "Have I Been Pwned", "url": "https://haveibeenpwned.com", "description": "Verifica brechas de datos"},
                    {"name": "Hunter.io", "url": "https://hunter.io", "description": "Encuentra emails corporativos"},
                    {"name": "Epio", "url": "https://epieos.com", "description": "Rastreo de correos y perfiles de Google"},
                    {"name": "EmailRep", "url": "https://emailrep.io", "description": "Reputación de emails"}
                ]
            },
            {
                "name": "Domain/IP",
                "icon": "🌐",
                "tools": [
                    {"name": "Shodan", "url": "https://shodan.io", "description": "Motor de búsqueda para IoT"},
                    {"name": "Censys", "url": "https://censys.io", "description": "Búsqueda de hosts y certificados"},
                    {"name": "VirusTotal", "url": "https://virustotal.com", "description": "Análisis de URLs y archivos"},
                    {"name": "SecurityTrails", "url": "https://securitytrails.com", "description": "Historial DNS y datos de dominios"}
                ]
            },
            {
                "name": "Social Media",
                "icon": "📱",
                "tools": [
                    {"name": "Social Searcher", "url": "https://social-searcher.com", "description": "Buscador de redes sociales"},
                    {"name": "TweetDeck", "url": "https://tweetdeck.twitter.com", "description": "Monitoreo de Twitter"},
                    {"name": "Social Blade", "url": "https://socialblade.com", "description": "Estadísticas de redes sociales"}
                ]
            },
            {
                "name": "Data Breaches",
                "icon": "🔓",
                "tools": [
                    {"name": "DeHashed", "url": "https://dehashed.com", "description": "Base de datos de filtraciones"},
                    {"name": "IntelX", "url": "https://intelx.io", "description": "Búsqueda profunda de filtraciones"},
                    {"name": "LeakCheck", "url": "https://leakcheck.io", "description": "Verificación de filtraciones"},
                    {"name": "Pwndb", "url": "https://pwndb.com", "description": "Base de datos de credenciales filtradas"}
                ]
            },
            {
                "name": "Network",
                "icon": "📡",
                "tools": [
                    {"name": "Nmap", "url": "https://nmap.org", "description": "Escáner de puertos y red"},
                    {"name": "theHarvester", "url": "https://github.com/laramies/theHarvester", "description": "Recolección de emails y subdominios"},
                    {"name": "Recon-ng", "url": "https://github.com/lanmaster53/recon-ng", "description": "Framework de reconocimiento"},
                    {"name": "SpiderFoot", "url": "https://github.com/smicallef/spiderfoot", "description": "Automatización de OSINT"}
                ]
            },
            {
                "name": "People Search",
                "icon": "🔍",
                "tools": [
                    {"name": "Pipl", "url": "https://pipl.com", "description": "Búsqueda de personas"},
                    {"name": "Spokeo", "url": "https://spokeo.com", "description": "Directorio de personas"},
                    {"name": "WhitePages", "url": "https://whitepages.com", "description": "Directorio telefónico"}
                ]
            }
        ]
    }
    return framework_tree

@router.get("/google-dork-templates")
async def get_google_dork_templates():
    """
    Devuelve plantillas predefinidas de Google Dorks para uso rápido.
    """
    templates = {
        "file_types": {
            "pdf": "filetype:pdf",
            "doc": "filetype:doc OR filetype:docx",
            "xls": "filetype:xls OR filetype:xlsx",
            "ppt": "filetype:ppt OR filetype:pptx",
            "sql": "filetype:sql",
            "txt": "filetype:txt",
            "csv": "filetype:csv",
            "log": "filetype:log",
            "conf": "filetype:conf",
            "env": "filetype:env"
        },
        "common_dorks": [
            {"name": "Archivos expuestos", "query": "intitle:\"index of\""},
            {"name": "Configuraciones expuestas", "query": "filetype:env \"DB_PASSWORD\""},
            {"name": "Logs expuestos", "query": "filetype:log \"password\" OR \"error\""},
            {"name": "Archivos SQL expuestos", "query": "filetype:sql \"INSERT INTO\" \"password\""},
            {"name": "Cámaras IP", "query": "intitle:\"Live View / AXIS\" | intitle:\"Live View / Linksys\""},
            {"name": "Panel de administración", "query": "intitle:\"Admin Login\" | intitle:\"Admin Panel\""},
            {"name": "Documentos confidenciales", "query": "filetype:pdf \"confidential\" OR \"internal\" OR \"restricted\""},
            {"name": "Herramientas de hacking", "query": "filetype:py \"import nmap\" OR \"import scapy\""}
        ]
    }
    return templates