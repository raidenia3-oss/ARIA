"""
Módulo para manejar las rutas de la API de AURA.
Incluye endpoints seguros para diferentes funcionalidades.
"""

import json
import os
import sys
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from functools import wraps
from search_engine import handle_search_request
from database_manager import (
    save_osint_result,
    save_radar_scan,
    save_sentinel_alert,
    get_osint_history,
    get_radar_history,
    get_radar_history_with_details,
    get_sentinel_history,
    get_recent_activity,
    get_presence_analysis,
    analyze_presence_changes,
    save_presence_analysis,
)

# Importar el sistema de nodos tácticos
from Shadow_Core.Nodes.node_base import node_registry

# Importar Venice Shodan Scanner
try:
    from venice_shodan_scanner import VeniceShodanScanner

    SHODAN_SCANNER = VeniceShodanScanner()
except Exception as e:
    SHODAN_SCANNER = None
    print(f"⚠️ VeniceShodanScanner no disponible: {e}")

app = Flask(__name__)

# Configuración de la API Key maestra (debería estar en un archivo de configuración seguro)
MASTER_API_KEY = "AURA_MASTER_KEY_2026"

# Ruta para guardar las capturas de audio
AUDIO_CAPTURES_DIR = os.path.join(os.path.dirname(__file__), "Cerebro_Memoria", "Capturas_Audio")

# Ruta del archivo de versión
VERSION_FILE = os.path.join(os.path.dirname(__file__), "version.json")

# Ruta del APK compilado
APK_DISTRIBUTION_DIR = os.path.join(os.path.dirname(__file__), "dist")
APK_FILENAME = "AME_Client_v1.apk"

# Almacenar el último escaneo para análisis de presencia
last_scan_data = None


def ensure_audio_captures_dir():
    """Asegura que el directorio de capturas de audio exista."""
    if not os.path.exists(AUDIO_CAPTURES_DIR):
        os.makedirs(AUDIO_CAPTURES_DIR)


def load_version_info():
    """Carga la información de versión desde el archivo version.json."""
    try:
        with open(VERSION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {
            "version": "0.0.0",
            "build": 0,
            "release_date": "1970-01-01",
            "description": "Versión no disponible",
        }


def save_audio_capture(audio_file, metadata):
    """Guarda una captura de audio en el directorio correspondiente."""
    ensure_audio_captures_dir()

    # Generar nombre de archivo único
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"ALERTA_{timestamp}.wav"
    filepath = os.path.join(AUDIO_CAPTURES_DIR, filename)

    # Guardar el archivo
    audio_file.save(filepath)

    # Registrar la captura en la base de datos
    trigger_level = float(metadata.get("threshold", "60"))
    save_sentinel_alert(filepath, trigger_level)

    # Registrar la captura en un log de texto
    log_message = f"[{datetime.now().isoformat()}] Captura de audio guardada: {filename}\n"
    log_message += f"  - Umbral: {metadata.get('threshold', 'N/A')} dB\n"
    log_message += f"  - Nivel: {metadata.get('level', 'N/A')} dB\n"
    log_message += f"  - Ruta: {filepath}\n"

    with open(os.path.join(AUDIO_CAPTURES_DIR, "audio_logs.txt"), "a", encoding="utf-8") as f:
        f.write(log_message)

    return filename


def require_api_key(f):
    """
    Decorador para proteger las rutas con la API Key maestra.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get("X-API-KEY")
        if not api_key or api_key != MASTER_API_KEY:
            return jsonify({"status": "error", "message": "API Key no válida"}), 401
        return f(*args, **kwargs)

    return decorated_function


@app.route("/api/search", methods=["POST"])
@require_api_key
def search_osint():
    """
    Endpoint para realizar búsquedas OSINT.
    Recibe una consulta y una plataforma objetivo, y devuelve resultados formateados.
    Guarda los resultados en la base de datos.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No se proporcionaron datos"}), 400

        # Validar parámetros
        query = data.get("query", "").strip()
        target_platform = data.get("target_platform", "web").lower()
        max_results = data.get("max_results", 5)

        if not query:
            return (
                jsonify({"status": "error", "message": "El parámetro 'query' es obligatorio"}),
                400,
            )

        # Llamar al motor de búsqueda OSINT
        result = handle_search_request(
            {"query": query, "target_platform": target_platform, "max_results": max_results}
        )

        return jsonify(result)

    except Exception as e:
        return jsonify({"status": "error", "message": f"Error en la búsqueda: {str(e)}"}), 500


@app.route("/api/radar/scan", methods=["POST"])
@require_api_key
def radar_scan():
    """
    Endpoint para recibir escaneos de redes WiFi desde AME.
    Guarda los datos en la base de datos y realiza análisis de presencia.
    """
    global last_scan_data

    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No se proporcionaron datos"}), 400

        networks = data.get("networks", [])
        if not networks or not isinstance(networks, list):
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "El campo 'networks' es obligatorio y debe ser una lista",
                    }
                ),
                400,
            )

        # Validar estructura de cada red
        for network in networks:
            if not all(key in network for key in ["ssid", "bssid", "rssi"]):
                return (
                    jsonify(
                        {"status": "error", "message": "Cada red debe tener SSID, BSSID y RSSI"}
                    ),
                    400,
                )

        # Guardar cada red en la base de datos
        scan_ids = []
        for network in networks:
            scan_id = save_radar_scan(
                ssid=network.get("ssid", ""),
                bssid=network.get("bssid", ""),
                signal_strength=network.get("rssi", 0),
            )
            scan_ids.append(scan_id)

        # Almacenar el último escaneo para análisis de presencia
        last_scan_data = networks

        # Realizar análisis de presencia si hay escaneos anteriores
        presence_analysis = []
        if last_scan_data:
            perturbation_results = analyze_presence_changes(last_scan_data, networks)
            if perturbation_results:
                save_presence_analysis(perturbation_results, scan_ids[-1])
                presence_analysis = perturbation_results

        return jsonify(
            {
                "status": "success",
                "message": "Escaneo guardado correctamente en la base de datos",
                "networks_received": len(networks),
                "presence_analysis": presence_analysis,
            }
        )

    except Exception as e:
        return (
            jsonify({"status": "error", "message": f"Error al guardar el escaneo: {str(e)}"}),
            500,
        )


@app.route("/api/radar/history", methods=["GET"])
@require_api_key
def get_radar_history():
    """
    Endpoint para obtener el historial de escaneos de radar con detalles enriquecidos.
    """
    try:
        limit = int(request.args.get("limit", 50))
        results = get_radar_history_with_details(limit)

        # Formatear los resultados para la respuesta
        formatted_results = []
        for row in results:
            formatted_results.append(
                {
                    "id": row["id"],
                    "ssid": row["ssid"],
                    "bssid": row["bssid"],
                    "signal_strength": row["signal_strength"],
                    "manufacturer": row["manufacturer"],
                    "device_type": row["device_type"],
                    "timestamp": (
                        row["timestamp"].isoformat()
                        if hasattr(row["timestamp"], "isoformat")
                        else str(row["timestamp"])
                    ),
                }
            )

        return jsonify(
            {
                "status": "success",
                "message": "Historial de escaneos de radar obtenido correctamente",
                "results": formatted_results,
            }
        )

    except Exception as e:
        return (
            jsonify({"status": "error", "message": f"Error al obtener el historial: {str(e)}"}),
            500,
        )


@app.route("/api/radar/presence", methods=["GET"])
@require_api_key
def get_presence_analysis():
    """
    Endpoint para obtener el análisis de perturbación de presencia.
    """
    try:
        limit = int(request.args.get("limit", 20))
        results = get_presence_analysis(limit)

        # Formatear los resultados para la respuesta
        formatted_results = []
        for row in results:
            formatted_results.append(
                {
                    "id": row["id"],
                    "scan_id": row["scan_id"],
                    "network_id": row["network_id"],
                    "ssid": row["ssid"],
                    "bssid": row["bssid"],
                    "manufacturer": row["manufacturer"],
                    "device_type": row["device_type"],
                    "rssi_initial": row["rssi_initial"],
                    "rssi_current": row["rssi_current"],
                    "perturbation_index": row["perturbation_index"],
                    "timestamp": (
                        row["timestamp"].isoformat()
                        if hasattr(row["timestamp"], "isoformat")
                        else str(row["timestamp"])
                    ),
                }
            )

        return jsonify(
            {
                "status": "success",
                "message": "Análisis de perturbación de presencia obtenido correctamente",
                "results": formatted_results,
            }
        )

    except Exception as e:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": f"Error al obtener el análisis de presencia: {str(e)}",
                }
            ),
            500,
        )


@app.route("/api/alerts/audio", methods=["POST"])
@require_api_key
def receive_audio_alert():
    """
    Endpoint para recibir alertas de audio desde AME.
    Guarda los archivos de audio en Cerebro_Memoria/Capturas_Audio/ y registra en la base de datos.
    """
    try:
        if "audio" not in request.files:
            return jsonify({"status": "error", "message": "No se recibió archivo de audio"}), 400

        audio_file = request.files["audio"]
        metadata = {
            "threshold": request.form.get("threshold", "60"),
            "level": request.form.get("level", "N/A"),
            "source": "AME_Mobile",
        }

        if not audio_file.filename:
            return (
                jsonify({"status": "error", "message": "Nombre de archivo de audio inválido"}),
                400,
            )

        # Guardar el archivo de audio y registrar en la base de datos
        filename = save_audio_capture(audio_file, metadata)

        return jsonify(
            {
                "status": "success",
                "message": "Archivo de audio guardado correctamente",
                "filename": filename,
                "metadata": metadata,
            }
        )

    except Exception as e:
        return (
            jsonify(
                {"status": "error", "message": f"Error al guardar el archivo de audio: {str(e)}"}
            ),
            500,
        )


@app.route("/api/health", methods=["GET"])
def health_check():
    """
    Endpoint para verificar la salud del sistema.
    """
    return jsonify({"status": "success", "message": "AURA OSINT Engine is running"})


@app.route("/api/intelligence/history", methods=["GET"])
@require_api_key
def get_intelligence_history():
    """
    Endpoint para obtener el historial de inteligencia recolectada.
    """
    try:
        # Obtener parámetros de la consulta
        module = request.args.get("module", "all")
        limit = int(request.args.get("limit", 50))

        if module == "osint":
            results = get_osint_history(limit)
            return jsonify(
                {"status": "success", "module": "osint", "results": [dict(row) for row in results]}
            )
        elif module == "radar":
            results = get_radar_history(limit)
            return jsonify(
                {"status": "success", "module": "radar", "results": [dict(row) for row in results]}
            )
        elif module == "centinela":
            results = get_sentinel_history(limit)
            return jsonify(
                {
                    "status": "success",
                    "module": "centinela",
                    "results": [dict(row) for row in results],
                }
            )
        elif module == "presencia":
            results = get_presence_analysis(limit)
            return jsonify(
                {
                    "status": "success",
                    "module": "presencia",
                    "results": [dict(row) for row in results],
                }
            )
        else:  # 'all' o cualquier otro valor
            results = get_recent_activity(limit)
            return jsonify(
                {"status": "success", "module": "all", "results": [dict(row) for row in results]}
            )

    except Exception as e:
        return (
            jsonify({"status": "error", "message": f"Error al obtener el historial: {str(e)}"}),
            500,
        )


@app.route("/api/system/version", methods=["GET"])
def get_system_version():
    """
    Endpoint público para obtener la versión del sistema.
    """
    try:
        version_info = load_version_info()
        return jsonify({"status": "success", "version": version_info})
    except Exception as e:
        return (
            jsonify({"status": "error", "message": f"Error al obtener la versión: {str(e)}"}),
            500,
        )


@app.route("/descargar-ame", methods=["GET"])
def download_ame_apk():
    """
    Endpoint para descargar el último APK compilado de AME.
    """
    try:
        # Verificar que el APK exista
        apk_path = os.path.join(APK_DISTRIBUTION_DIR, APK_FILENAME)
        if not os.path.exists(apk_path):
            return jsonify({"status": "error", "message": "APK no encontrado"}), 404

        # Obtener la versión actual
        version_info = load_version_info()

        # Enviar el archivo APK
        return send_from_directory(
            directory=APK_DISTRIBUTION_DIR,
            path=APK_FILENAME,
            as_attachment=True,
            download_name=f"AME_v{version_info['version']}.apk",
        )
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error al descargar el APK: {str(e)}"}), 500


@app.route("/api/nodes/list", methods=["GET"])
@require_api_key
def list_nodes():
    """
    Endpoint para listar todos los nodos tácticos disponibles.
    """
    try:
        nodes_info = node_registry.list_nodes()
        return jsonify(
            {
                "status": "success",
                "nodes": nodes_info["nodes"],
                "total": nodes_info["total"],
                "timestamp": nodes_info["timestamp"],
            }
        )
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error al listar nodos: {str(e)}"}), 500


@app.route("/api/nodes/info/<node_id>", methods=["GET"])
@require_api_key
def get_node_info(node_id):
    """
    Endpoint para obtener información detallada de un nodo táctico específico.
    """
    try:
        # Intentar importar el módulo del nodo
        node_module = None
        try:
            node_module = __import__(f"Shadow_Core.Nodes.{node_id}", fromlist=[""])
        except ImportError:
            return jsonify({"status": "error", "message": f"Nodo {node_id} no encontrado"}), 404

        # Buscar la clase TacticalNode en el módulo
        node_class = None
        for name, obj in vars(node_module).items():
            if hasattr(obj, "node_id") and obj.node_id == node_id:
                node_class = obj
                break

        if not node_class:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"No se encontró clase TacticalNode en el módulo {node_id}",
                    }
                ),
                404,
            )

        # Crear instancia y obtener información
        node_instance = node_class()
        node_info = node_instance.get_info()

        return jsonify({"status": "success", "node": node_info})
    except Exception as e:
        return (
            jsonify(
                {"status": "error", "message": f"Error al obtener información del nodo: {str(e)}"}
            ),
            500,
        )


@app.route("/api/nodes/execute/<node_id>", methods=["POST"])
@require_api_key
def execute_node(node_id):
    """
    Endpoint para ejecutar un nodo táctico específico desde AME.
    Recibe los datos de entrada y devuelve la salida del nodo.
    """
    try:
        # Obtener los datos de entrada
        input_data = request.get_json()
        if not input_data:
            return (
                jsonify({"status": "error", "message": "No se proporcionaron datos de entrada"}),
                400,
            )

        # Ejecutar el nodo usando el registro
        execution_result = node_registry.execute_node(node_id, input_data)

        return jsonify(execution_result)

    except Exception as e:
        return jsonify({"status": "error", "message": f"Error al ejecutar el nodo: {str(e)}"}), 500


@app.route("/api/osint", methods=["POST"])
@require_api_key
def osint_shodan():
    """
    Endpoint para escaneo OSINT Shodan (módulo Venice).
    Recibe target (IP/dominio) y mode (host/vulns/search).
    Devuelve perfil de inteligencia formateado para Discord embed.
    """
    if SHODAN_SCANNER is None:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "VeniceShodanScanner no disponible. Verifica SHODAN_API_KEY.",
                }
            ),
            503,
        )

    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No se proporcionaron datos"}), 400

        target = data.get("target", "").strip()
        mode = data.get("mode", "host").lower()

        if not target:
            return (
                jsonify({"status": "error", "message": "El parámetro 'target' es obligatorio"}),
                400,
            )

        # Ejecutar escaneo según modo
        if mode == "host":
            result = SHODAN_SCANNER.scan_host(target)
        elif mode == "vulns":
            result = SHODAN_SCANNER.get_vulnerabilities(target)
        elif mode == "search":
            query = data.get("query", target)
            limit = data.get("limit", 10)
            result = SHODAN_SCANNER.search(query, limit)
        else:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"Modo no válido: {mode}. Use: host, vulns, search",
                    }
                ),
                400,
            )

        # Formatear para Discord embed
        embed = SHODAN_SCANNER.format_for_discord_embed(result)

        return jsonify(
            {"status": "success", "target": target, "mode": mode, "result": result, "embed": embed}
        )

    except Exception as e:
        return jsonify({"status": "error", "message": f"Error en escaneo OSINT: {str(e)}"}), 500


@app.route("/api/osint/status/<task_id>", methods=["GET"])
@require_api_key
def osint_task_status(task_id):
    """
    Endpoint para consultar estado de tarea OSINT encolada.
    """
    # TODO: Integrar con task_dispatcher para consultar estado real
    return jsonify(
        {
            "status": "pending",
            "task_id": task_id,
            "message": "Consulta de estado no implementada aún. Usar task_dispatcher directamente.",
        }
    )


@app.route("/api/hud/mobile", methods=["GET"])
def get_mobile_hud():
    """
    Endpoint para obtener el HUD móvil optimizado para Android.
    Sirve el archivo HTML del CYBER-HUD v5.0 desde assets.
    """
    try:
        hud_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "AME_ECOSYSTEM",
            "ame_app_android",
            "app",
            "src",
            "main",
            "assets",
            "aura_mobile_hud.html",
        )
        if not os.path.exists(hud_path):
            return jsonify({"status": "error", "message": "Archivo HUD móvil no encontrado"}), 404
        with open(hud_path, "r", encoding="utf-8") as f:
            content = f.read()
        return content, 200, {"Content-Type": "text/html; charset=utf-8"}
    except Exception as e:
        return (
            jsonify({"status": "error", "message": f"Error al obtener el HUD móvil: {str(e)}"}),
            500,
        )


@app.route("/api/hud/desktop", methods=["GET"])
def get_desktop_hud():
    """
    Endpoint para obtener el HUD de escritorio CYBER-HUD v5.0.
    """
    try:
        hud_path = os.path.join(
            os.path.dirname(__file__), "..", "AME_Core", "templates", "aura_cyberpunk_hud.html"
        )
        if not os.path.exists(hud_path):
            return (
                jsonify({"status": "error", "message": "Archivo HUD de escritorio no encontrado"}),
                404,
            )
        with open(hud_path, "r", encoding="utf-8") as f:
            content = f.read()
        return content, 200, {"Content-Type": "text/html; charset=utf-8"}
    except Exception as e:
        return (
            jsonify(
                {"status": "error", "message": f"Error al obtener el HUD de escritorio: {str(e)}"}
            ),
            500,
        )


# ──────────────────────────────────────────────────────
# Loop Engine - Desarrollo iterativo con IA
# Basado en: "Loop Engineering" (Fazt, 2026)
# ──────────────────────────────────────────────────────


@app.route("/api/loop/run", methods=["POST"])
def loop_engine_run():
    """
    Endpoint para ejecutar un loop de Loop Engineering.
    POST /api/loop/run
    Body: {"task": "descripcion", "language": "python", "max_iterations": 5}
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No se proporcionaron datos"}), 400

        task = data.get("task", "").strip()
        if not task:
            return jsonify({"status": "error", "message": "El campo 'task' es obligatorio"}), 400

        language = data.get("language", "python")
        max_iterations = min(data.get("max_iterations", 5), 10)  # max 10 por seguridad

        # Importar dinámicamente para no romper si falta algo
        sys.path.insert(0, os.path.dirname(__file__))
        from loop_engine import LoopEngine

        engine = LoopEngine(language=language, max_iterations=max_iterations)
        result = engine.run(task)

        return jsonify(
            {
                "status": "success",
                "task_id": result.task_id,
                "result_status": result.status,
                "iterations": result.total_iterations,
                "duration_seconds": result.total_duration,
                "provider": result.best_provider,
                "code": result.final_code,
            }
        )

    except Exception as e:
        return jsonify({"status": "error", "message": f"Error en Loop Engine: {str(e)}"}), 500


@app.route("/api/loop/history", methods=["GET"])
def loop_engine_history():
    """
    Endpoint para obtener el historial de loops ejecutados.
    """
    try:
        loop_log_dir = os.path.join(os.path.dirname(__file__), "loop_logs")
        if not os.path.exists(loop_log_dir):
            return jsonify({"status": "success", "loops": []})

        logs = []
        for filename in sorted(os.listdir(loop_log_dir), reverse=True)[:20]:
            if filename.endswith(".json"):
                with open(os.path.join(loop_log_dir, filename), "r", encoding="utf-8") as f:
                    log_data = json.load(f)
                    # Resumir: solo info clave
                    logs.append(
                        {
                            "task_id": log_data.get("task_id"),
                            "task_description": log_data.get("task_description", "")[:100],
                            "status": log_data.get("status"),
                            "iterations": log_data.get("total_iterations"),
                            "duration": log_data.get("total_duration"),
                            "provider": log_data.get("best_provider"),
                            "created_at": log_data.get("created_at"),
                        }
                    )

        return jsonify({"status": "success", "loops": logs})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


from automation_engine import get_engine
from task_queue_manager import get_task_queue, TaskStatus


@app.route("/api/automation/run", methods=["POST"])
def run_automation():
    """Ejecuta una tarea de automatización web usando Playwright"""
    try:
        data = request.get_json() or {}
        task_type = data.get("task", "navigate")
        task_queue = get_task_queue()
        task = task_queue.enqueue(task_type, data)

        async def execute():
            try:
                task_queue.update_status(task.task_id, TaskStatus.RUNNING, progress=10)
                engine = await get_engine()
                if task_type == "initialize":
                    result = await engine.initialize()
                elif task_type == "navigate":
                    url = data.get("url", "https://example.com")
                    result = await engine.navigate(url)
                elif task_type == "capture_dom":
                    result = await engine.capture_dom()
                elif task_type == "screenshot":
                    result = await engine.screenshot()
                elif task_type == "close":
                    result = await engine.close()
                else:
                    result = {"error": f"Unknown task: {task_type}"}
                task_queue.update_status(
                    task.task_id, TaskStatus.COMPLETED, result=result, progress=100
                )
                return result
            except Exception as e:
                task_queue.update_status(task.task_id, TaskStatus.FAILED, error=str(e))
                raise

        def run_async():
            asyncio.run(execute())

        thread = threading.Thread(target=run_async)
        thread.start()

        return jsonify({"status": "accepted", "task_id": task.task_id})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    """Obtiene la lista de tareas en la cola"""
    try:
        task_queue = get_task_queue()
        status = request.args.get("status")
        limit = int(request.args.get("limit", 50))
        if status:
            try:
                status_enum = TaskStatus(status)
                tasks = task_queue.get_tasks_by_status(status_enum, limit)
            except ValueError:
                return jsonify({"status": "error", "message": f"Estado no válido: {status}"}), 400
        else:
            tasks = task_queue.get_all_tasks(limit)
        return jsonify({"status": "success", "tasks": tasks})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/tasks/<task_id>", methods=["GET"])
def get_task(task_id):
    """Obtiene el detalle de una tarea específica"""
    try:
        task_queue = get_task_queue()
        task = task_queue.get_task(task_id)
        if not task:
            return jsonify({"status": "error", "message": "Tarea no encontrada"}), 404
        return jsonify({"status": "success", "task": task.to_dict()})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/tasks/<task_id>/cancel", methods=["POST"])
def cancel_task(task_id):
    """Cancela una tarea pendiente"""
    try:
        task_queue = get_task_queue()
        if task_queue.cancel_task(task_id):
            return jsonify({"status": "success", "message": "Tarea cancelada"})
        return jsonify({"status": "error", "message": "No se pudo cancelar la tarea"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/ws/tasks")
def ws_tasks():
    """WebSocket para reporte de progreso de tareas en tiempo real"""
    from flask_socketio import emit

    task_queue = get_task_queue()

    @socketio.on("connect", namespace="/ws/tasks")
    def handle_connect():
        emit("connected", {"message": "Task WebSocket conectado"})

    @socketio.on("disconnect", namespace="/ws/tasks")
    def handle_disconnect():
        pass

    return "OK"


@socketio.on("subscribe_tasks", namespace="/ws/tasks")
def handle_subscribe_tasks(data):
    from flask_socketio import emit

    task_queue = get_task_queue()
    task_id = data.get("task_id")
    if task_id:
        task = task_queue.get_task(task_id)
        if task:
            emit("task_update", task.to_dict())


def broadcast_task_update(task):
    from flask_socketio import emit

    try:
        emit("task_update", task.to_dict(), namespace="/ws/tasks", broadcast=True)
    except Exception:
        pass


if __name__ == "__main__":
    # Asegurar que los directorios existan al iniciar el servidor
    ensure_audio_captures_dir()
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
