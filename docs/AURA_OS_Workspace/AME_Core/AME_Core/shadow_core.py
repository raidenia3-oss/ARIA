"""
Shadow-Core: Microservicio aislado para operaciones avanzadas de OSINT.
Ejecuta comandos en hebras separadas y maneja errores de manera controlada.
Compatible con Windows (usa threading en vez de multiprocessing).
"""

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import threading
import queue
import json
import time
import signal
import sys
import os
from typing import Dict, Any, Optional
from pathlib import Path

# Importar módulos de seguridad y Shadow-Core
from security_shield import scan_for_threats, rotate_fingerprint, get_tor_proxy

# Importar módulo de autenticación biométrica
from Shadow_Core.biometric_auth import setup_biometric_auth, token_required

# Importar módulo de agente de correo
try:
    from Shadow_Core.email_agent import EmailAgent
    EMAIL_AGENT_AVAILABLE = True
    email_agent = None
except ImportError as e:
    EMAIL_AGENT_AVAILABLE = False
    email_agent = None

# Importar módulo de Obsidian
try:
    from obsidian_link import ObsidianIndexer
    OBSIDIAN_AVAILABLE = True
    obsidian_indexer = None
except ImportError:
    OBSIDIAN_AVAILABLE = False
    obsidian_indexer = None

# Inicializar variables de módulos
NET_RECON_AVAILABLE = False
EXFIL_AVAILABLE = False
run_recon = None
exfiltrate_file = None
prepare_exfil_report = None

# Intentar importar módulos
try:
    from Shadow_Core.net_recon_ghost import run_recon
    NET_RECON_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Error cargando net_recon_ghost: {e}")

try:
    from Shadow_Core.data_exfiltration_layer import exfiltrate_file, prepare_exfil_report
    EXFIL_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Error cargando data_exfiltration_layer: {e}")

# Configuración del Shadow-Core
SHADOW_CORE_PORT = 5001
TIMEOUT_SECONDS = 30  # Tiempo máximo de ejecución para un comando
MAX_WORKERS = 5       # Máximo de hebras concurrentes

# Inicializar la aplicación FastAPI
app = FastAPI(title="AURA Shadow-Core", version="1.0.0")

# Configurar autenticación biométrica
setup_biometric_auth(app)

# Inicializar el agente de correo si está disponible
if EMAIL_AGENT_AVAILABLE:
    email_agent = EmailAgent()
    email_agent.start()
    print("📧 Agente de correo iniciado y escaneando en segundo plano.")

# Cola thread-safe para comandos
command_queue = queue.Queue()

class CommandWorker(threading.Thread):
    """
    Hebra trabajadora que ejecuta comandos OSINT.
    Corre en background procesando comandos de la cola.
    """

    def __init__(self, worker_id: int):
        super().__init__(daemon=True, name=f"ShadowWorker-{worker_id}")
        self.worker_id = worker_id

    def run(self):
        while True:
            try:
                # Obtener (coladestino, comando) de la cola principal
                cmd_queue, command = command_queue.get()

                # Ejecutar el comando según su tipo
                cmd_type = command.get('type', '')
                if cmd_type == 'shodan_search':
                    result = self._execute_shodan(command)
                elif cmd_type == 'rtl_sdr_scan':
                    result = self._execute_rtl_sdr(command)
                elif cmd_type == 'tor_request':
                    result = self._execute_tor(command)
                else:
                    result = {"status": "failed", "message": f"Tipo de comando no soportado: {cmd_type}"}

                # Enviar el resultado a la cola del comando
                cmd_queue.put(result)

            except queue.Empty:
                pass
            except Exception as e:
                try:
                    cmd_queue.put({"status": "failed", "message": f"Error en la ejecución: {str(e)}"})
                except Exception:
                    pass

    def _execute_shodan(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta una búsqueda en Shodan (simulada)."""
        query = command.get('query', '')
        if not query:
            return {"status": "failed", "message": "La consulta Shodan está vacía."}
        results = [
            {"ip": "1.2.3.4", "port": 443, "data": f"Resultado de búsqueda para: {query}"},
            {"ip": "5.6.7.8", "port": 80, "data": f"Resultado adicional para: {query}"}
        ]
        return {
            "status": "ok",
            "type": "shodan_search",
            "query": query,
            "results": results,
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S')
        }

    def _execute_rtl_sdr(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta un escaneo con RTL-SDR (simulado)."""
        frequency = command.get('frequency', 100.0)
        duration = command.get('duration', 10)
        signals = []
        for i in range(3):
            signals.append({
                "frequency": frequency + i * 0.1,
                "signal_strength": -60 + i * 5,
                "modulation": "FM" if i % 2 == 0 else "AM"
            })
        return {
            "status": "ok",
            "type": "rtl_sdr_scan",
            "frequency": frequency,
            "duration": duration,
            "signals": signals,
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S')
        }

    def _execute_tor(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta una petición a través de Tor (simulada)."""
        url = command.get('url', '')
        if not url:
            return {"status": "failed", "message": "La URL está vacía."}
        response = {
            "status_code": 200,
            "headers": {"Content-Type": "text/html"},
            "body": f"<html><body>Resultado de la petición a través de Tor para: {url}</body></html>"
        }
        return {
            "status": "ok",
            "type": "tor_request",
            "url": url,
            "response": response,
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S')
        }

def execute_command(command: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ejecuta un comando en una hebra separada y retorna el resultado.
    """
    try:
        if not isinstance(command, dict) or 'type' not in command:
            return {"status": "failed", "message": "Comando inválido. Se espera un JSON con 'type'."}

        # Crear cola para recibir el resultado de este comando
        cmd_queue = queue.Queue()
        command_queue.put((cmd_queue, command))

        # Esperar el resultado con timeout
        try:
            result = cmd_queue.get(timeout=TIMEOUT_SECONDS)
            return result
        except queue.Empty:
            return {"status": "failed", "message": f"Timeout de {TIMEOUT_SECONDS} segundos superado."}

    except Exception as e:
        return {"status": "failed", "message": f"Error interno: {str(e)}"}

# Iniciar las hebras trabajadoras
def start_workers():
    """Inicia las hebras trabajadoras para manejar comandos OSINT."""
    for i in range(MAX_WORKERS):
        worker = CommandWorker(i)
        worker.start()

# Endpoint principal para ejecutar comandos avanzados (protegido con JWT)
@app.post("/api/execute_advanced")
@token_required
async def execute_advanced(request: Request):
    """
    Endpoint para ejecutar comandos avanzados de OSINT.
    Acepta un JSON con el tipo de comando y parámetros.
    Retorna un JSON con el resultado o un error controlado.
    """
    try:
        # Verificar amenazas antes de procesar cualquier comando
        threat_status = scan_for_threats()
        if threat_status != "CLEAN":
            return JSONResponse(
                status_code=403,
                content={"status": "failed", "message": f"Acceso denegado: {threat_status}"}
            )

        # Obtener el cuerpo de la petición
        body = await request.json()

        # Validar que sea un JSON válido
        if not isinstance(body, dict):
            return JSONResponse(
                status_code=400,
                content={"status": "failed", "message": "El cuerpo de la petición debe ser un JSON válido."}
            )

        # Rotar fingerprint para evitar fingerprinting
        fingerprint = rotate_fingerprint()
        body["_fingerprint"] = fingerprint

        # Ejecutar el comando en background
        result = execute_command(body)

        # Retornar el resultado
        return JSONResponse(content=result)

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "failed", "message": f"Error interno en Shadow-Core: {str(e)}"}
        )

# Endpoint de healthcheck para el heartbeat
@app.get("/health")
async def health_check():
    """Healthcheck para el heartbeat del Communication Bridge."""
    threat_status = scan_for_threats()
    return JSONResponse(content={
        "status": "alive",
        "threat_status": threat_status,
        "modules": {
            "net_recon": NET_RECON_AVAILABLE,
            "data_exfil": EXFIL_AVAILABLE,
            "biometric_auth": True,
            "email_agent": EMAIL_AGENT_AVAILABLE
        }
    })

# Endpoint para escaneo de red furtivo (net_recon_ghost) - protegido con JWT
@app.post("/api/net_recon")
@token_required
async def net_recon(request: Request):
    """
    Ejecuta un escaneo de red furtivo (SYN Stealth + ARP).
    Retorna JSON con hosts activos, puertos abiertos y servicios.
    """
    try:
        if not NET_RECON_AVAILABLE:
            return JSONResponse(
                status_code=501,
                content={"status": "failed", "message": "Módulo net_recon no disponible"}
            )

        # Verificar amenazas antes de procesar
        threat_status = scan_for_threats()
        if threat_status != "CLEAN":
            return JSONResponse(
                status_code=403,
                content={"status": "failed", "message": f"Acceso denegado: {threat_status}"}
            )

        # Obtener parámetros
        body = await request.json()
        subnet = body.get("subnet", None)
        ports = body.get("ports", None)

        # Ejecutar escaneo
        result = run_recon(subnet, ports)

        # Rotar fingerprint para evitar fingerprinting
        fingerprint = rotate_fingerprint()
        result["_fingerprint"] = fingerprint

        return JSONResponse(content=result)

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "failed", "message": f"Error en net_recon: {str(e)}"}
        )

# Endpoint para exfiltración de datos (data_exfiltration_layer) - protegido con JWT
@app.post("/api/data_exfil")
@token_required
async def data_exfil(request: Request):
    """
    Prepara un archivo para exfiltración encriptada (DNS/ICMP).
    Retorna JSON con detalles de los paquetes generados.
    """
    try:
        if not EXFIL_AVAILABLE:
            return JSONResponse(
                status_code=501,
                content={"status": "failed", "message": "Módulo data_exfil no disponible"}
            )

        # Verificar amenazas antes de procesar
        threat_status = scan_for_threats()
        if threat_status != "CLEAN":
            return JSONResponse(
                status_code=403,
                content={"status": "failed", "message": f"Acceso denegado: {threat_status}"}
            )

        # Obtener parámetros
        body = await request.json()
        filepath = body.get("filepath", None)
        channel = body.get("channel", "dns")

        if not filepath:
            return JSONResponse(
                status_code=400,
                content={"status": "failed", "message": "filepath requerido"}
            )

        # Ejecutar exfiltración
        result = exfiltrate_file(Path(filepath), channel)

        # Rotar fingerprint para evitar fingerprinting
        fingerprint = rotate_fingerprint()
        result["_fingerprint"] = fingerprint

        return JSONResponse(content=result)

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "failed", "message": f"Error en data_exfil: {str(e)}"}
        )

# Endpoint para buscar en la bóveda de Obsidian - protegido con JWT
@app.post("/api/obsidian/search")
@token_required
async def obsidian_search(request: Request):
    """
    Busca en la bóveda de Obsidian indexada.
    Retorna fragmentos de notas relevantes para la consulta.
    """
    try:
        # Verificar amenazas antes de procesar
        threat_status = scan_for_threats()
        if threat_status != "CLEAN":
            return JSONResponse(
                status_code=403,
                content={"status": "failed", "message": f"Acceso denegado: {threat_status}"}
            )

        # Obtener parámetros
        body = await request.json()
        query = body.get("query", "")
        limit = body.get("limit", 5)

        if not query:
            return JSONResponse(
                status_code=400,
                content={"status": "failed", "message": "La consulta 'query' es requerida"}
            )

        # Inicializar indexador si no está inicializado
        global obsidian_indexer
        if obsidian_indexer is None and OBSIDIAN_AVAILABLE:
            vault_path = os.environ.get("OBSIDIAN_VAULT_PATH", "C:/Users/User/ObsidianVault")
            try:
                obsidian_indexer = ObsidianIndexer(vault_path)
            except Exception as e:
                return JSONResponse(
                    status_code=500,
                    content={"status": "failed", "message": f"Error inicializando indexador: {str(e)}"}
                )

        # Verificar si el indexador está disponible
        if not OBSIDIAN_AVAILABLE or obsidian_indexer is None:
            return JSONResponse(
                status_code=501,
                content={"status": "failed", "message": "Módulo de Obsidian no disponible"}
            )

        # Buscar en las notas
        results = obsidian_indexer.search_notes(query, limit)

        # Formatear resultados para el cliente
        formatted_results = []
        for result in results:
            note = result["note"]
            formatted_results.append({
                "title": note.get("title", "Nota sin título"),
                "path": result["note_path"],
                "score": result["score"],
                "fragment": result["content"][:200] + ("..." if len(result["content"]) > 200 else ""),
                "tags": note.get("tags", []),
                "created": note.get("created", None),
                "modified": note.get("modified", None)
            })

        # Rotar fingerprint para evitar fingerprinting
        fingerprint = rotate_fingerprint()
        formatted_results = {"_fingerprint": fingerprint, "results": formatted_results}

        return JSONResponse(content=formatted_results)

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "failed", "message": f"Error en búsqueda de Obsidian: {str(e)}"}
        )

# Endpoint para el protocolo móvil (protegido con JWT)
@app.post("/api/mobile-protocol")
@token_required
async def mobile_protocol(request: Request):
    """
    Endpoint para manejar peticiones del protocolo móvil.
    """
    try:
        # Verificar amenazas antes de procesar
        threat_status = scan_for_threats()
        if threat_status != "CLEAN":
            return JSONResponse(
                status_code=403,
                content={"status": "failed", "message": f"Acceso denegado: {threat_status}"}
            )

        # Obtener el cuerpo de la petición
        body = await request.json()

        # Validar que sea un JSON válido
        if not isinstance(body, dict):
            return JSONResponse(
                status_code=400,
                content={"status": "failed", "message": "El cuerpo de la petición debe ser un JSON válido."}
            )

        # Procesar la petición según el tipo
        if body.get('type') == 'test':
            return JSONResponse(
                content={
                    "status": "ok",
                    "message": "Prueba de protocolo móvil exitosa",
                    "data": body,
                    "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S')
                }
            )
        elif body.get('type') == 'email_alert':
            return JSONResponse(
                content={
                    "status": "ok",
                    "message": "Notificación de correo recibida",
                    "data": body,
                    "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S')
                }
            )
        else:
            return JSONResponse(
                status_code=400,
                content={"status": "failed", "message": "Tipo de petición no soportado."}
            )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "failed", "message": f"Error en protocolo móvil: {str(e)}"}
        )

# Función para iniciar el Shadow-Core
def start_shadow_core():
    """Inicia el Shadow-Core con las hebras trabajadoras."""
    start_workers()
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=SHADOW_CORE_PORT,
        log_level="warning"
    )

# Función para detener el Shadow-Core de manera segura
def stop_shadow_core():
    """Detiene el Shadow-Core."""
    if EMAIL_AGENT_AVAILABLE and email_agent:
        email_agent.stop()
    sys.exit(0)

# Manejar señales para detener el servidor de manera segura
def handle_signal(signum, frame):
    print("🛑 Recibida señal de terminación. Deteniendo el Shadow-Core...")
    stop_shadow_core()

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

if __name__ == "__main__":
    print("🚀 Iniciando AURA Shadow-Core en el puerto 5001...")
    print("📧 Configuración del agente de correo:")
    print(f"   - Servidor IMAP: {os.getenv('EMAIL_IMAP_SERVER', 'No configurado')}")
    print(f"   - Usuario: {os.getenv('EMAIL_IMAP_USERNAME', 'No configurado')}")
    print(f"   - Palabras clave: {', '.join(os.getenv('EMAIL_SEARCH_KEYWORDS', 'Ninguna').split(','))}")
    print(f"   - Estado: {'Activo' if EMAIL_AGENT_AVAILABLE else 'No disponible'}")
    start_shadow_core()