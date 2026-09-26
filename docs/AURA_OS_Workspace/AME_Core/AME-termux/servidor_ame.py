"""
AURA Command Center — Flask Server v2
Sirve:
  - Dashboard en '/' (dashboard.html)
  - /api/status → JSON con salud del sistema
  - /api/osint  → POST para ejecutar OSINT (PhoneInfoga / Mr. Holmes)
  - /start/<service>, /stop/<service> para control de bots
"""
import time
import json
import os
import sys
import signal
import subprocess
import threading
import psutil

from flask import Flask, send_from_directory, jsonify, request, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit

# ── Añadir AURA_Core al path para importar OSINTEngine ──
AURA_CORE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'AURA_Core')
if AURA_CORE_DIR not in sys.path:
    sys.path.insert(0, AURA_CORE_DIR)

try:
    from osint_engine import OSINTEngine  # type: ignore[import]
except ImportError:
    OSINTEngine = None
    print("⚠️  OSINTEngine no disponible (osint_engine.py no encontrado)")

# ── Importar Skills Forge ──
FORGE_DIR = AURA_CORE_DIR
if FORGE_DIR not in sys.path:
    sys.path.insert(0, FORGE_DIR)
try:
    from skills_forge import execute_skill_chain, list_available_tools, get_tool_info  # type: ignore[import]
    print("✅ Skills Forge cargado correctamente")
except ImportError:
    execute_skill_chain = None
    list_available_tools = None
    print("⚠️  Skills Forge no disponible (skills_forge.py no encontrado en AURA_Core/)")
except Exception as e:
    execute_skill_chain = None
    list_available_tools = None
    print(f"⚠️  Error cargando Skills Forge: {e}")

try:
    from telemetria_radio import generate_wifi_radar_data, start_wifi_watchdog, stop_wifi_watchdog, get_wifi_watchdog_status  # type: ignore[import]
    print("✅ Telemetría radio cargada correctamente")
except ImportError:
    generate_wifi_radar_data = None
    start_wifi_watchdog = None
    stop_wifi_watchdog = None
    get_wifi_watchdog_status = None
    print("⚠️  Telemetría radio no disponible (telemetria_radio.py no encontrado)")
except Exception as e:
    generate_wifi_radar_data = None
    start_wifi_watchdog = None
    stop_wifi_watchdog = None
    get_wifi_watchdog_status = None
    print(f"⚠️  Error cargando telemetria_radio: {e}")

# ──────────────────────── APP ────────────────────────
app = Flask(__name__)
app.config['SECRET_KEY'] = 'aura-2026-c2'
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
START_TIME = time.time()

# ──── Configuración de Servicios (Bots) ────
SERVICES = {
    "aura_master":    {"script": "aura_core.py",       "process": None, "name": "AURA Master"},
    "crypto_farmer":  {"script": "crypto_farmer_v2.py", "process": None, "name": "Crypto Farmer"},
    "discord_bot":    {"script": "discord_bot.py",      "process": None, "name": "Discord Bot"},
    "escudo_monitor": {"script": "escudo_monitor.py",   "process": None, "name": "Escudo Monitor"},
    "recon_agent":    {"script": "recon.py",            "process": None, "name": "Recon Agent"},
    "osint_engine":   {"script": "osint_engine.py",     "process": None, "name": "OSINT Engine"},
}

# ──── Instancia del Motor OSINT ────
osint_engine = None
if OSINTEngine is not None:
    osint_engine = OSINTEngine()

# ──────────────────────── TUNNEL MANAGER ────────────────────────
try:
    from tunnel_manager import TunnelManager
    tunnel_mgr = TunnelManager(tunnel_type='ngrok', port=5000)
    print("✅ Tunnel manager cargado correctamente")
except Exception as e:
    tunnel_mgr = None
    print(f"⚠️  Tunnel manager no disponible: {e}")

try:
    if start_wifi_watchdog is not None:
        start_wifi_watchdog()
        print("✅ WiFi watchdog iniciado")
except Exception as e:
    print(f"⚠️  No se pudo iniciar WiFi watchdog: {e}")

# --- Registrar endpoints biometricos ---
try:
    from biometric_endpoints import register_biometric_routes
    register_biometric_routes(app)
    print("Endpoints biometricos registrados")
except ImportError as e:
    print("biometric_endpoints no encontrado:", e)
except Exception as e:
    print("Error registrando endpoints biometricos:", e)

# ──────────────────── RUTAS ────────────────────

@app.route('/')
def index():
    """Sirve el dashboard AURA."""
    return send_from_directory(os.getcwd(), 'dashboard.html')


@app.route('/blue')
def blue_dashboard():
    """Sirve el dashboard B.L.U.E. Financial Node."""
    return render_template('blue_dashboard.html')


@app.route('/api/core-log', methods=['POST'])
def api_core_log():
    """
    Guarda una nota en knowledge_base vía core_log.py.
    Body JSON: { "content": "texto", "tags": ["tag1"], "source": "manual" }
    """
    data = request.get_json(force=True)
    if not data or not data.get("content"):
        return jsonify({"status": "error", "message": "content requerido"}), 400

    try:
        sys.path.insert(0, AURA_CORE_DIR)
        from core_log import save_note
        result = save_note(
            content=data["content"],
            tags=data.get("tags", []),
            source=data.get("source", "manual"),
            sync_firebase=True,
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/void/save', methods=['POST'])
def api_void_save():
    """
    Guarda una nota en VOID (knowledge_base/void/).
    Body JSON: { "content": "texto", "tags": ["tag1"] }
    """
    data = request.get_json(force=True)
    if not data or not data.get("content"):
        return jsonify({"status": "error", "message": "content requerido"}), 400

    try:
        sys.path.insert(0, AURA_CORE_DIR)
        from void import save_to_void
        result = save_to_void(
            content=data["content"],
            tags=data.get("tags", ["void"]),
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/void/list', methods=['GET'])
def api_void_list():
    """Lista las notas guardadas en VOID."""
    try:
        sys.path.insert(0, AURA_CORE_DIR)
        from void import list_void
        tag = request.args.get("tag")
        limit = request.args.get("limit", 20, type=int)
        notes = list_void(tag=tag, limit=limit)
        return jsonify({"status": "ok", "notes": notes})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/chat', methods=['POST'])
def api_chat():
    """
    Envía un mensaje al AURA Cognitive Router y recibe respuesta.
    Usa route_with_void() para interceptar comandos VOID ("guarda:", "void:", etc.)
    Body: { "message": "...", "context": {} }
    """
    data = request.get_json(force=True)
    if not data or not data.get("message"):
        return jsonify({"status": "error", "error": "message requerido"}), 400

    try:
        sys.path.insert(0, AURA_CORE_DIR)
        from ai_router import AuraCognitiveRouter
        router = AuraCognitiveRouter()
        result = router.route_with_void(data["message"], data.get("context"))
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route('/api/briefing', methods=['GET'])
def api_briefing():
    """Obtiene el briefing más reciente."""
    try:
        sys.path.insert(0, AURA_CORE_DIR)
        from osint_radar import get_latest_briefing
        briefing = get_latest_briefing()
        if briefing:
            return jsonify({"status": "ok", "briefing": briefing})
        return jsonify({"status": "ok", "briefing": None, "message": "No hay briefing aún. Usa POST /api/briefing/refresh"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/briefing/refresh', methods=['POST'])
def api_briefing_refresh():
    """Fuerza la generación de un nuevo briefing."""
    try:
        sys.path.insert(0, AURA_CORE_DIR)
        from osint_radar import fetch_morning_briefing
        data = request.get_json(force=True) or {}
        feeds = data.get("feeds")
        briefing = fetch_morning_briefing(feeds=feeds)
        return jsonify({"status": "ok", "briefing": briefing})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/void/search', methods=['GET'])
def api_void_search():
    """Busca notas en VOID por palabra clave."""
    query = request.args.get("q", "")
    if not query:
        return jsonify({"status": "error", "message": "Parámetro 'q' requerido"}), 400
    try:
        sys.path.insert(0, AURA_CORE_DIR)
        from void import search_void
        results = search_void(query)
        return jsonify({"status": "ok", "results": results})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/core-log/list', methods=['GET'])
def api_core_log_list():
    """Lista las notas guardadas en knowledge_base."""
    try:
        sys.path.insert(0, AURA_CORE_DIR)
        from core_log import list_notes
        tag = request.args.get("tag")
        limit = request.args.get("limit", 20, type=int)
        notes = list_notes(tag=tag, limit=limit)
        return jsonify({"status": "ok", "notes": notes})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/tools/execute', methods=['POST'])
def api_tools_execute():
    """
    Ejecuta una herramienta del Skills Forge directamente.
    Body JSON: { "tool_name": "...", "params": {...}, "run_in_background": false }
    """
    data = request.get_json(force=True)
    if not data:
        return jsonify({"status": "error", "message": "Body JSON requerido"}), 400

    tool_name = data.get("tool_name", "").strip()
    params = data.get("params", {})
    run_in_background = data.get("run_in_background", True)

    if not tool_name:
        return jsonify({"status": "error", "message": "tool_name requerido"}), 400

    try:
        from skills_forge import execute_single_tool, get_tool_info
        tool_info = get_tool_info(tool_name)
        if not tool_info:
            return jsonify({"status": "error", "message": f"Herramienta '{tool_name}' no registrada"}), 404

        result = execute_single_tool(
            tool_name,
            params=params,
            run_in_background=run_in_background
        )
        return jsonify({"status": result.get("status", "ok"), "result": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/status')
def api_status():
    """
    JSON con el estado de salud completo del sistema.
    Ejemplo:
    {
      "master_online": true,
      "bots": { "crypto_farmer": true, "discord_bot": false, ... },
      "ram_free_gb": 6.2,
      "ram_total_gb": 16.0,
      "cpu_percent": 23.5,
      "uptime": "0:12:34",
      "system_health": "healthy" | "degraded",
      "active_services": 3,
      "total_services": 6
    }
    """
    # ── RAM ──
    ram = psutil.virtual_memory()
    ram_free_gb  = round(ram.available / (1024**3), 2)
    ram_total_gb = round(ram.total / (1024**3), 2)

    # ── CPU ──
    cpu_percent = psutil.cpu_percent(interval=0.3)

    # ── Uptime ──
    elapsed = time.time() - START_TIME
    hours   = int(elapsed // 3600)
    minutes = int((elapsed % 3600) // 60)
    seconds = int(elapsed % 60)
    uptime_str = f"{hours}:{minutes:02d}:{seconds:02d}"

    # ── Estado de cada servicio ──
    bots_status = {}
    online_count = 0
    master_online = False
    for key, srv in SERVICES.items():
        is_alive = srv["process"] is not None and srv["process"].poll() is None
        bots_status[key] = is_alive
        if is_alive:
            online_count += 1
            if key == "aura_master":
                master_online = True

    # ── Health check ──
    system_health = "healthy" if master_online else "degraded"

    return jsonify({
        "master_online":  master_online,
        "bots":           bots_status,
        "online_count":   online_count,
        "total_services": len(SERVICES),
        "ram_free_gb":    ram_free_gb,
        "ram_total_gb":   ram_total_gb,
        "cpu_percent":    cpu_percent,
        "uptime":         uptime_str,
        "system_health":  system_health
    })


@app.route('/api/osint', methods=['POST'])
def api_osint():
    """
    Ejecuta una herramienta OSINT (PhoneInfoga o Mr. Holmes).
    Body JSON: { "tool": "phone" | "email", "target": "+34..." }
    """
    if OSINTEngine is None or osint_engine is None:
        return jsonify({"error": "OSINTEngine no disponible. Verifica osint_engine.py en AURA_Core/"}), 500

    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "Body JSON requerido"}), 400

    tool   = data.get("tool", "").strip().lower()
    target = data.get("target", "").strip()

    if not tool or tool not in ("phone", "email"):
        return jsonify({"error": "tool debe ser 'phone' o 'email'"}), 400
    if not target:
        return jsonify({"error": "target requerido"}), 400

    try:
        # Ejecutamos síncrono (el dashboard espera resultado completo)
        result = osint_engine.execute(tool, target, sync=True)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Error ejecutando OSINT: {str(e)}"}), 500


@app.route('/api/osint/result/<task_id>')
def api_osint_result(task_id):
    """Recupera resultado de una tarea OSINT asíncrona (task_id)."""
    if osint_engine is None:
        return jsonify({"error": "OSINTEngine no disponible"}), 500
    result = osint_engine.get_task_result(task_id)
    return jsonify(result)


@app.route('/api/osint/status/<task_id>')
def api_osint_status(task_id):
    """Estado actual de una tarea OSINT (progreso + últimas líneas)."""
    if osint_engine is None:
        return jsonify({"error": "OSINTEngine no disponible"}), 500
    result = osint_engine.get_task_status(task_id)
    return jsonify(result)


@app.route('/api/osint/logs/<task_id>')
def api_osint_logs(task_id):
    """Devuelve las líneas de log de una tarea OSINT."""
    if osint_engine is None:
        return jsonify({"error": "OSINTEngine no disponible"}), 500
    max_lines = request.args.get('max', 100, type=int)
    result = osint_engine.get_task_logs(task_id, max_lines=max_lines)
    return jsonify(result)


@app.route('/api/osint/cancel/<task_id>', methods=['POST'])
def api_osint_cancel(task_id):
    """Cancela una tarea OSINT en ejecución."""
    if osint_engine is None:
        return jsonify({"error": "OSINTEngine no disponible"}), 500
    result = osint_engine.cancel_task(task_id)
    return jsonify(result)


@app.route('/api/osint/list')
def api_osint_list():
    """Lista todas las tareas OSINT activas y completadas."""
    if osint_engine is None:
        return jsonify({"error": "OSINTEngine no disponible"}), 500
    result = osint_engine.list_tasks()
    return jsonify(result)


@app.route('/api/osint/background', methods=['POST'])
def api_osint_background():
    """
    Lanza una tarea OSINT en segundo plano (background).
    Body JSON: { "tool": "phone"|"email"|"domain", "target": "...", "task_id": "opcional" }
    """
    if osint_engine is None:
        return jsonify({"error": "OSINTEngine no disponible"}), 500

    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "Body JSON requerido"}), 400

    tool   = data.get("tool", "").strip().lower()
    target = data.get("target", "").strip()
    task_id = data.get("task_id", None)

    if not tool or tool not in ("phone", "email", "domain"):
        return jsonify({"error": "tool debe ser 'phone', 'email' o 'domain'"}), 400
    if not target:
        return jsonify({"error": "target requerido"}), 400

    try:
        result = osint_engine.execute(tool, target, sync=False)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Error lanzando OSINT background: {str(e)}"}), 500


@app.route('/api/export/watchlist', methods=['GET'])
def api_export_watchlist():
    """Exporta la watchlist en formato JSON."""
    return jsonify({
        "status": "ok",
        "format": "json",
        "export_timestamp": time.strftime('%Y-%m-%dT%H:%M:%S'),
        "watchlist": WATCHLIST_STORE
    })


@app.route('/api/export/alerts', methods=['GET'])
def api_export_alerts():
    """Exporta el histórico de alertas en formato JSON."""
    alerts = _load_ticker()
    return jsonify({
        "status": "ok",
        "format": "json",
        "export_timestamp": time.strftime('%Y-%m-%dT%H:%M:%S'),
        "total_alerts": len(alerts),
        "alerts": alerts
    })


@app.route('/api/import/watchlist', methods=['POST'])
def api_import_watchlist():
    """
    Importa una watchlist desde JSON.
    Body: { "watchlist": {...} }
    """
    data = request.get_json(force=True)
    imported = data.get("watchlist", {})
    
    if not isinstance(imported, dict):
        return jsonify({"status": "error", "message": "watchlist debe ser un dict"}), 400
    
    # Merge con existente (opcional)
    merge = request.args.get("merge", "true").lower() == "true"
    
    if merge:
        WATCHLIST_STORE.update(imported)
    else:
        WATCHLIST_STORE.clear()
        WATCHLIST_STORE.update(imported)
    
    _save_watchlist(WATCHLIST_STORE)
    
    return jsonify({
        "status": "ok",
        "imported_count": len(imported),
        "total_watchlist": len(WATCHLIST_STORE)
    })


@app.route('/api/system/verify', methods=['GET'])
def api_system_verify():
    """
    Verifica la integridad del sistema y persistencia de datos.
    """
    verification = {
        "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S'),
        "checks": {}
    }
    
    # Check 1: Watchlist persistencia
    watchlist_ok = os.path.exists(WATCHLIST_FILE)
    verification["checks"]["watchlist_file"] = {
        "exists": watchlist_ok,
        "path": WATCHLIST_FILE,
        "count": len(WATCHLIST_STORE)
    }
    
    # Check 2: Alerts persistencia
    alerts_ok = os.path.exists(TICKER_FILE)
    alerts = _load_ticker()
    verification["checks"]["alerts_file"] = {
        "exists": alerts_ok,
        "path": TICKER_FILE,
        "count": len(alerts)
    }
    
    # Check 3: Componentes AURA
    components = {
        "ai_router": False,
        "osint_engine": False,
        "skills_forge": False
    }
    
    try:
        from ai_router import AuraCognitiveRouter
        components["ai_router"] = True
    except:
        pass
    
    if OSINTEngine is not None:
        components["osint_engine"] = True
    
    if execute_skill_chain is not None:
        components["skills_forge"] = True
    
    verification["checks"]["components"] = components
    
    # Check 4: Permisos de escritura
    try:
        test_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.write_test')
        with open(test_file, 'w') as f:
            f.write('')
        os.remove(test_file)
        write_ok = True
    except:
        write_ok = False
    
    verification["checks"]["write_permission"] = {
        "status": "ok" if write_ok else "denied",
        "directory": os.path.dirname(os.path.abspath(__file__))
    }
    
    # Overall status
    all_ok = watchlist_ok and alerts_ok and write_ok and all(components.values())
    verification["overall_status"] = "healthy" if all_ok else "warning" if (watchlist_ok and alerts_ok) else "critical"
    
    return jsonify(verification)


@app.route('/api/stats/summary', methods=['GET'])
def api_stats_summary():
    """Resumen de estadísticas del sistema."""
    stats = {
        "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S'),
        "watchlist": {
            "total": len(WATCHLIST_STORE),
            "active": len([t for t in WATCHLIST_STORE.values() if t.get("status") == "active"]),
            "by_priority": {
                "high": len([t for t in WATCHLIST_STORE.values() if t.get("priority") == "high"]),
                "medium": len([t for t in WATCHLIST_STORE.values() if t.get("priority") == "medium"]),
                "low": len([t for t in WATCHLIST_STORE.values() if t.get("priority") == "low"])
            },
            "by_type": {}
        },
        "alerts": {
            "total": len(_load_ticker()),
            "by_type": {
                "critical": 0,
                "warning": 0,
                "info": 0
            },
            "by_source": {}
        }
    }
    
    # Count by type (watchlist)
    for entry in WATCHLIST_STORE.values():
        ttype = entry.get("type", "unknown")
        stats["watchlist"]["by_type"][ttype] = stats["watchlist"]["by_type"].get(ttype, 0) + 1
    
    # Count alerts
    for alert in _load_ticker():
        alert_type = alert.get("type", "info")
        if alert_type in stats["alerts"]["by_type"]:
            stats["alerts"]["by_type"][alert_type] += 1
        
        source = alert.get("source", "unknown")
        stats["alerts"]["by_source"][source] = stats["alerts"]["by_source"].get(source, 0) + 1
    
    return jsonify(stats)


@app.route('/status')
def legacy_status():
    """Endpoint legacy para compatibilidad."""
    status_map = {}
    for key, srv in SERVICES.items():
        if srv["process"] and srv["process"].poll() is None:
            status_map[key] = "ONLINE"
        else:
            status_map[key] = "OFFLINE"
    return jsonify(status_map)


@app.route('/start/<service>')
def start_service(service):
    """Inicia un servicio/bot específico."""
    if service not in SERVICES:
        return jsonify({"error": f"Servicio '{service}' no encontrado"}), 404

    srv = SERVICES[service]
    if srv["process"] and srv["process"].poll() is None:
        return jsonify({"message": f"{srv['name']} ya está activo"}), 200

    try:
        # Determinar el directorio base (AME_Core)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(script_dir, srv["script"])

        cmd = [sys.executable, script_path]
        log_path = os.path.join(script_dir, f"log_{service}.txt")

        with open(log_path, "a") as log_file:
            srv["process"] = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=log_file,
                cwd=script_dir
            )
        return jsonify({"message": f"{srv['name']} iniciado", "service": service})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/stop/<service>')
def stop_service(service):
    """Detiene un servicio/bot específico."""
    if service not in SERVICES:
        return jsonify({"error": f"Servicio '{service}' no encontrado"}), 404

    srv = SERVICES[service]
    if not srv["process"] or srv["process"].poll() is not None:
        return jsonify({"message": f"{srv['name']} no está activo"}), 200

    try:
        # Intentar terminación gradual, luego forzar
        proc = srv["process"]
        if os.name == 'nt':
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            proc.terminate()

        # Esperar hasta 3s
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

        srv["process"] = None
        return jsonify({"message": f"{srv['name']} detenido", "service": service})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/health-log')
def api_health_log():
    """Devuelve las últimas 50 líneas del system_health.log."""
    health_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'AURA_Core', 'system_health.log')
    try:
        if os.path.exists(health_log_path):
            with open(health_log_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            # Últimas 50 líneas relevantes (saltar comentarios)
            log_entries = [l.strip() for l in lines if l.strip() and not l.startswith('#')]
            return jsonify({"entries": log_entries[-50:]})
        return jsonify({"entries": []})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/evolution/proposals', methods=['GET'])
def api_evolution_proposals():
    """
    Endpoint para obtener propuestas de automejora.
    Retorna propuestas generadas por evolution_core.py.
    """
    try:
        sys.path.insert(0, AURA_CORE_DIR)
        from evolution_core import EvolutionEngine
        engine = EvolutionEngine()
        files = [
            'AURA_Core/ai_router.py',
            'AME_Core/servidor_ame.py',
            'AURA_Core/osint_radar.py'
        ]
        result = engine.generate_proposals(files)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/intelrift/predictive', methods=['GET'])
def api_intelrift_predictive():
    """
    Endpoint para búsqueda predictiva de anomalías.
    Consulta fuentes de OSINT y detecta patrones inusuales.
    """
    try:
        sys.path.insert(0, AURA_CORE_DIR)
        from intelrift_search import IntelriftSearch
        search = IntelriftSearch()
        result = search.predictive_search()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/sensor/wifi_csi', methods=['POST'])
def api_sensor_wifi_csi():
    """
    Endpoint para recibir datos de CSI Wi-Fi desde sensores perimetrales.
    Body JSON: { "nodes": {"ALPHA": -45, "BETA": -52, ...}, "perturbation": 12.5, "timestamp": "ISO" }
    """
    data = request.get_json(force=True)
    if not data:
        return jsonify({"status": "error", "message": "Body JSON requerido"}), 400

    # Validar estructura mínima
    if "nodes" not in data or "perturbation" not in data:
        return jsonify({"status": "error", "message": "nodes y perturbation requeridos"}), 400

    # Inyectar alerta en ticker si hay alta perturbación
    if data["perturbation"] > 40:
        try:
            _inject_ticker_alert("warning", f"📡 ALTA PERTURBACIÓN CSI: {data['perturbation']}%", "sensor")
        except:
            pass

    return jsonify({"status": "standby", "received": True, "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S')})

@app.route('/api/sensor/acoustic', methods=['POST'])
def api_sensor_acoustic():
    """
    Endpoint para recibir datos de radar acústico (eco).
    Body JSON: { "frequency": 2400, "amplitude": 0.8, "echo_time": 0.002, "timestamp": "ISO" }
    """
    data = request.get_json(force=True)
    if not data:
        return jsonify({"status": "error", "message": "Body JSON requerido"}), 400

    # Validar estructura mínima
    if "frequency" not in data or "amplitude" not in data:
        return jsonify({"status": "error", "message": "frequency y amplitude requeridos"}), 400

    # Inyectar alerta en ticker si hay eco anómalo
    if data["amplitude"] > 1.2:
        try:
            _inject_ticker_alert("critical", f"🔊 ECO ACÚSTICO ANÓMALO: {data['amplitude']} @ {data['frequency']}Hz", "sensor")
        except:
            pass

    return jsonify({"status": "standby", "received": True, "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S')})


@app.route('/api/skill-forge', methods=['POST'])
def skill_forge_execute():
    """
    Recibe una cadena de habilidades desde el dashboard y la ejecuta
    mediante skills_forge.execute_skill_chain().
    Body: { "skills": ["blackbird", "osint"], "target": "..." }
    """
    data = request.get_json(force=True)
    if not data:
        return jsonify({"status": "error", "message": "No payload"}), 400

    # Obtener la cadena de habilidades desde el payload
    skills = data.get('skills', [])
    flow = data.get('flow', 'custom')
    target = data.get('target', None)
    combined = data.get('combined_flow')
    edges = data.get('edges', [])

    # Si no hay skills explícitas, inferir desde edges
    if not skills and edges:
        tool_map_ids = {'master', 'ollama', 'osint', 'termux', 'exiftool', 'blackbird', 'photon'}
        connected = set()
        for e in edges:
            s, t = e.get('source'), e.get('target')
            if s in tool_map_ids and s != 'master': connected.add(s)
            if t in tool_map_ids and t != 'master': connected.add(t)
        skills = list(connected)

    if not skills:
        return jsonify({"status": "error", "error": "No skills provided or detected"}), 400

    print(f"⚒️ [Skill Forge] Flow: {flow} | Skills: {skills} | Target: {target}")

    # ── Ejecutar con skills_forge.py si está disponible ──
    if execute_skill_chain is not None:
        try:
            targets = {"_default": target} if target else {}
            # Usar un hilo para no bloquear el servidor
            thread_result = {}

            def run_in_thread():
                try:
                    result = execute_skill_chain(
                        skills_list=skills,
                        targets=targets,
                        output_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'forge_output')
                    )
                    thread_result['result'] = result
                except Exception as e:
                    thread_result['error'] = str(e)

            t = threading.Thread(target=run_in_thread, daemon=True)
            t.start()
            t.join(timeout=300)  # 5 min timeout

            if 'error' in thread_result:
                return jsonify({"status": "error", "error": thread_result['error']}), 500

            result = thread_result.get('result', {})
            return jsonify({
                "status": result.get('status', 'completed'),
                "flow": flow,
                "skills": skills,
                "target": target,
                "total_steps": result.get('total_steps', 0),
                "completed": result.get('completed', 0),
                "all_ok": result.get('all_ok', False),
                "results": result.get('results', []),
                "chain": result.get('chain', [])
            })

        except Exception as e:
            return jsonify({"status": "error", "error": str(e)}), 500

    # ── Fallback simulado (si skills_forge.py no está disponible) ──
    tool_names = {
        'osint': '🔍 OSINT Engine', 'blackbird': '🐦 Blackbird/Nexfil',
        'photon': '🌐 Photon Crawler', 'exiftool': '📸 ExifTool',
        'termux': '📱 Termux Sync', 'ollama': '🧠 Ollama LLM',
    }
    results = {}
    for skill in skills:
        name = tool_names.get(skill, skill)
        results[skill] = f"✅ {name} ejecutado (simulado — skills_forge.py no disponible)"

    if combined:
        flow_label = combined.get('label', 'custom')
        results['pipeline'] = f"🔄 Flujo combinado: {flow_label} (simulado)"

    return jsonify({
        "status": "completed",
        "flow": flow,
        "skills": skills,
        "results": results,
        "note": "simulated — install skills_forge.py for real execution"
    })


@app.route('/api/radar', methods=['GET'])
def api_radar():
    """
    OSINT Radar endpoint.
    Devuelve un resumen ejecutivo táctico generado por IA desde feeds RSS.
    Auto-genera briefing si no existe uno reciente (< 6h).
    """
    try:
        sys.path.insert(0, AURA_CORE_DIR)
        from osint_radar import get_latest_briefing, fetch_morning_briefing
        briefing = get_latest_briefing()
        now = time.time()

        # Si no hay briefing o tiene más de 6 horas, refrescar automáticamente
        needs_refresh = False
        if briefing is None:
            needs_refresh = True
        else:
            try:
                from datetime import datetime, timezone
                ts = datetime.fromisoformat(briefing["timestamp"])
                age_hours = (datetime.now(timezone.utc).timestamp() - ts.replace(tzinfo=timezone.utc).timestamp()) / 3600
                if age_hours > 6:
                    needs_refresh = True
            except Exception:
                needs_refresh = True

        if needs_refresh:
            print("[Radar] Generando nuevo briefing automático...")
            briefing = fetch_morning_briefing()

        if briefing and briefing.get("summary"):
            return jsonify({
                "status": "ok",
                "timestamp": briefing.get("timestamp"),
                "total_sources": briefing.get("total_sources", 0),
                "total_headlines": briefing.get("total_headlines", 0),
                "summary": briefing["summary"],
                "tactical_html": briefing.get("tactical_html", ""),
                "headlines": briefing.get("headlines", [])[:5],
                "auto_refreshed": needs_refresh
            })

        return jsonify({
            "status": "ok",
            "summary": "📡 Radar sin datos. Verifica conexión a internet y feeds RSS.",
            "tactical_html": "<p>📡 Radar sin datos. Verifica conexión a internet y feeds RSS.</p>",
            "headlines": [],
            "auto_refreshed": False
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/update_mobile_ip', methods=['POST'])
def update_mobile_ip():
    """Recibe actualización de IP móvil desde el webhook de AURA_Core."""
    data = request.get_json(force=True)
    if not data or 'mobile_ip' not in data:
        return jsonify({"error": "mobile_ip requerido"}), 400
    new_ip = data['mobile_ip']
    # Guardar en archivo auxiliar para persistencia entre reinicios
    ip_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'AURA_Core', 'config.json')
    try:
        if os.path.exists(ip_file):
            with open(ip_file, 'r') as f:
                cfg = json.load(f)
        else:
            cfg = {}
        cfg['mobile_ip'] = new_ip
        cfg['last_seen'] = time.strftime('%Y-%m-%dT%H:%M:%S')
        with open(ip_file, 'w') as f:
            json.dump(cfg, f, indent=2)
        print(f"📱 [AME Server] IP móvil actualizada vía webhook: {new_ip}")
        return jsonify({"status": "ok", "mobile_ip": new_ip})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/wifi_radar', methods=['GET'])
def api_wifi_radar():
    """
    CSI Spectrum Scanner mejorado. Procesa Channel State Information (CSI).
    Detecta perturbaciones electromagnéticas, interferencia y presencia.
    Integración con telemetria_radio.py para datos reales.
    """
    if generate_wifi_radar_data is None:
        return jsonify({"status": "error", "message": "WiFi telemetry module unavailable"}), 500

    try:
        wifi_data = generate_wifi_radar_data()
        if wifi_data.get("presence_detected") and wifi_data.get("perturbation_index", 0) > 40:
            try:
                _inject_ticker_alert(
                    "warning",
                    f"📡 PRESENCIA DETECTADA — CSI Perturbation: {wifi_data['perturbation_index']}% | SNR: {wifi_data['snr_avg']}dB",
                    "wifi_radar"
                )
            except Exception:
                pass
        return jsonify(wifi_data)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/wifi_watchdog/start', methods=['POST'])
def api_wifi_watchdog_start():
    if start_wifi_watchdog is None:
        return jsonify({"status": "error", "message": "WiFi watchdog unavailable"}), 500
    started = start_wifi_watchdog()
    return jsonify({"status": "ok", "watchdog_started": started})


@app.route('/api/wifi_watchdog/stop', methods=['POST'])
def api_wifi_watchdog_stop():
    if stop_wifi_watchdog is None:
        return jsonify({"status": "error", "message": "WiFi watchdog unavailable"}), 500
    stopped = stop_wifi_watchdog()
    return jsonify({"status": "ok", "watchdog_stopped": stopped})


@app.route('/api/wifi_watchdog/status', methods=['GET'])
def api_wifi_watchdog_status():
    if get_wifi_watchdog_status is None:
        return jsonify({"status": "error", "message": "WiFi watchdog unavailable"}), 500
    return jsonify(get_wifi_watchdog_status())


@app.route('/api/wifi_radar/spectrum', methods=['GET'])
def api_wifi_spectrum():
    """
    Análisis avanzado de espectro Wi-Fi.
    Retorna datos de ocupancia por canal, interferencia y recomendaciones.
    """
    import math
    import random as _rnd

    t = time.time() * 0.1
    
    # Espectro de 2.4 GHz (canales 1-13, 20 MHz de ancho)
    spectrum_analysis = {}
    
    for ch in range(1, 14):
        center_freq = 2407 + (ch * 5)  # Frecuencia central en MHz
        occupancy = round(25 + abs(math.sin(t + ch * 0.2)) * 20 + _rnd.gauss(0, 8), 1)
        occupancy = min(100, max(0, occupancy))
        
        spectrum_analysis[f"ch_{ch}"] = {
            "channel": ch,
            "freq_mhz": center_freq,
            "occupancy_percent": occupancy,
            "interference_risk": "high" if occupancy > 70 else "medium" if occupancy > 40 else "low",
            "ap_count": _rnd.randint(0, 8) if occupancy > 30 else 0
        }
    
    # Recomendar mejor canal (menos interferencia)
    best_channel = min(
        spectrum_analysis.items(),
        key=lambda x: x[1]["occupancy_percent"]
    )
    
    # Canales problemáticos
    congested_channels = [
        ch for ch, data in spectrum_analysis.items()
        if data["interference_risk"] == "high"
    ]

    return jsonify({
        "status": "ok",
        "spectrum": spectrum_analysis,
        "recommended_channel": best_channel[0],
        "recommended_freq": best_channel[1]["freq_mhz"],
        "congested_channels": congested_channels,
        "overall_health": "good" if len(congested_channels) <= 2 else "fair" if len(congested_channels) <= 5 else "poor"
    })


@app.route('/health')
def health():
    """Healthcheck simple."""
    return jsonify({"status": "alive", "uptime": time.time() - START_TIME})


# ─────────────────────────────────────────────────────
# MÓDULOS DE EXPANSIÓN — Preparados para futuras herramientas
# ─────────────────────────────────────────────────────

# ── Watchlist: Seguimiento de objetivos (CON PERSISTENCIA) ──
WATCHLIST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'watchlist.json')

def _load_watchlist():
    """Carga watchlist desde JSON."""
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def _save_watchlist(watchlist):
    """Persiste watchlist a JSON."""
    try:
        with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
            json.dump(watchlist, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️  Error guardando watchlist: {e}")

WATCHLIST_STORE = _load_watchlist()

@app.route('/api/watchlist', methods=['GET'])
def api_watchlist_list():
    """Lista todos los objetivos en la watchlist."""
    return jsonify({"status": "ok", "watchlist": list(WATCHLIST_STORE.values())})


@app.route('/api/watchlist', methods=['POST'])
def api_watchlist_add():
    """
    Añade un objetivo a la watchlist con persistencia en JSON.
    Body: { "target": "ejemplo.com", "type": "domain|email|phone", "tags": [], "priority": "high" }
    """
    data = request.get_json(force=True)
    if not data or not data.get("target"):
        return jsonify({"status": "error", "message": "target requerido"}), 400

    import uuid
    entry_id = str(uuid.uuid4())[:8]
    WATCHLIST_STORE[entry_id] = {
        "id": entry_id,
        "target": data["target"],
        "type": data.get("type", "domain"),
        "tags": data.get("tags", []),
        "priority": data.get("priority", "medium"),
        "added": time.strftime('%Y-%m-%dT%H:%M:%S'),
        "status": "active"
    }
    _save_watchlist(WATCHLIST_STORE)
    
    # Inyectar alerta en ticker
    try:
        _inject_ticker_alert(
            "warning",
            f"🎯 Nuevo objetivo añadido: {data['target']} [{data.get('type', 'domain')}]"
        )
    except:
        pass
    
    return jsonify({"status": "ok", "entry": WATCHLIST_STORE[entry_id]})


@app.route('/api/watchlist/<entry_id>', methods=['DELETE'])
def api_watchlist_remove(entry_id):
    """Elimina un objetivo de la watchlist."""
    if entry_id in WATCHLIST_STORE:
        removed = WATCHLIST_STORE.pop(entry_id)
        _save_watchlist(WATCHLIST_STORE)
        return jsonify({"status": "ok", "removed": removed})
    return jsonify({"status": "error", "message": "ID no encontrado"}), 404


@app.route('/api/watchlist/<entry_id>', methods=['PATCH'])
def api_watchlist_update(entry_id):
    """Actualiza un objetivo de la watchlist."""
    if entry_id not in WATCHLIST_STORE:
        return jsonify({"status": "error", "message": "ID no encontrado"}), 404
    
    data = request.get_json(force=True)
    entry = WATCHLIST_STORE[entry_id]
    
    if "status" in data:
        entry["status"] = data["status"]
    if "tags" in data:
        entry["tags"] = data["tags"]
    if "priority" in data:
        entry["priority"] = data["priority"]
    
    entry["modified"] = time.strftime('%Y-%m-%dT%H:%M:%S')
    _save_watchlist(WATCHLIST_STORE)
    
    return jsonify({"status": "ok", "entry": entry})


# ── Ticker: Alertas globales con integración OSINT ──
TICKER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'alerts.json')

def _load_ticker():
    """Carga alertas desde JSON."""
    if os.path.exists(TICKER_FILE):
        try:
            with open(TICKER_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return _default_alerts()
    return _default_alerts()

def _default_alerts():
    """Alertas por defecto."""
    return [
        {"type": "info",    "message": "🟢 Sistema AURA operativo", "source": "system"},
        {"type": "info",    "message": "🟡 Monitor de amenazas activo", "source": "system"},
        {"type": "info",    "message": "🔵 VOID memory sincronizada", "source": "system"},
    ]

def _save_ticker(alerts):
    """Persiste alertas a JSON."""
    try:
        with open(TICKER_FILE, 'w', encoding='utf-8') as f:
            json.dump(alerts, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️  Error guardando ticker: {e}")

def _inject_ticker_alert(alert_type, message, source="system"):
    """Inyecta alerta en ticker (interno)."""
    alerts = _load_ticker()
    alerts.append({
        "type": alert_type,
        "message": message,
        "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S'),
        "source": source
    })
    # Mantener máximo 100 alertas
    if len(alerts) > 100:
        alerts = alerts[-100:]
    _save_ticker(alerts)

TICKER_MESSAGES = _load_ticker()

@app.route('/api/ticker', methods=['GET'])
def api_ticker():
    """
    Devuelve alertas globales del sistema.
    Incluye alertas de OSINT Radar y eventos del sistema.
    """
    TICKER_MESSAGES.clear()
    TICKER_MESSAGES.extend(_load_ticker())
    
    return jsonify({"status": "ok", "alerts": TICKER_MESSAGES})


@app.route('/api/get_latest_intel', methods=['GET'])
def api_get_latest_intel():
    """Devuelve las alertas del ticker formateadas para marquee dinámico."""
    TICKER_MESSAGES.clear()
    TICKER_MESSAGES.extend(_load_ticker())
    formatted_items = []
    for alert in TICKER_MESSAGES[-12:]:
        icon = "⎔" if alert["type"] == "info" else "⚠" if alert["type"] == "critical" else "◈"
        formatted_items.append(f"{icon} {alert['message']}")
    return jsonify({
        "status": "ok",
        "items": formatted_items if formatted_items else ["📡 AURA OPERATIVO · Sistema en línea"]
    })


@app.route('/api/ticker/push', methods=['POST'])
def api_ticker_push():
    """
    Endpoint para que otros módulos inyecten alertas al ticker.
    Body: { "type": "critical|warning|info", "message": "...", "source": "osint|wifi|system" }
    """
    data = request.get_json(force=True)
    if not data or not data.get("message"):
        return jsonify({"status": "error", "message": "message requerido"}), 400

    alert_type = data.get("type", "info")
    message = data["message"]
    source = data.get("source", "system")
    
    _inject_ticker_alert(alert_type, message, source)
    
    return jsonify({"status": "ok", "alert_injected": {"type": alert_type, "message": message, "source": source}})


@app.route('/api/ticker/clear', methods=['POST'])
def api_ticker_clear():
    """Limpia el historial de alertas."""
    _save_ticker(_default_alerts())
    return jsonify({"status": "ok", "message": "Alertas reiniciadas"})


@app.route('/api/osint/integrate', methods=['POST'])
def api_osint_integrate():
    """
    Integración OSINT: Procesa briefings de osint_radar y inyecta alertas.
    Body: { "briefing": {...} }
    """
    data = request.get_json(force=True)
    briefing = data.get("briefing", {})
    
    if not briefing:
        return jsonify({"status": "error", "message": "briefing requerido"}), 400
    
    # Procesar cada alert del briefing
    alerts = briefing.get("alerts", [])
    for alert in alerts:
        severity = alert.get("severity", "info").lower()
        title = alert.get("title", "Alerta OSINT")
        
        # Mapear severidad a tipo de alerta
        alert_type_map = {"critical": "critical", "high": "warning", "medium": "warning", "low": "info"}
        alert_type = alert_type_map.get(severity, "info")
        
        message = f"📡 {title}: {alert.get('description', '')[:80]}"
        _inject_ticker_alert(alert_type, message, "osint_radar")
    
    return jsonify({"status": "ok", "alerts_processed": len(alerts)})


@app.route('/api/situation-report', methods=['GET'])
def api_situation_report():
    """
    Reporte integrado: combina WiFi Radar + OSINT + Watchlist + Ticker
    para crear un "Situation Room" completo del estado del sistema.
    """
    import requests as req
    
    report = {
        "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S'),
        "system_health": "unknown",
        "wifi_status": {},
        "osint_briefing": {},
        "watchlist_summary": {},
        "active_alerts": [],
        "threat_level": "GREEN"
    }
    
    try:
        # 1. WiFi Radar
        wifi_resp = api_wifi_radar()
        wifi_data = json.loads(wifi_resp[0].get_data(as_text=True))
        report["wifi_status"] = {
            "perturbation": wifi_data.get("perturbation_index"),
            "presence_detected": wifi_data.get("presence_detected"),
            "link_quality": wifi_data.get("link_quality"),
            "active_channels": wifi_data.get("active_channels", [])
        }
    except Exception as e:
        report["wifi_status"]["error"] = str(e)
    
    try:
        # 2. OSINT Briefing
        if OSINTEngine is not None:
            try:
                from osint_radar import get_latest_briefing
                briefing = get_latest_briefing()
                if briefing:
                    report["osint_briefing"] = {
                        "threat_count": len(briefing.get("alerts", [])),
                        "critical_alerts": len([a for a in briefing.get("alerts", []) if a.get("severity") == "critical"]),
                        "top_threats": [a.get("title") for a in briefing.get("alerts", [])[:3]]
                    }
            except:
                pass
    except Exception as e:
        report["osint_briefing"]["error"] = str(e)
    
    try:
        # 3. Watchlist Summary
        active_targets = [t for t in WATCHLIST_STORE.values() if t.get("status") == "active"]
        report["watchlist_summary"] = {
            "total": len(WATCHLIST_STORE),
            "active": len(active_targets),
            "high_priority": len([t for t in active_targets if t.get("priority") == "high"]),
            "targets_by_type": {}
        }
        # Contar por tipo
        for t in active_targets:
            ttype = t.get("type", "unknown")
            report["watchlist_summary"]["targets_by_type"][ttype] = report["watchlist_summary"]["targets_by_type"].get(ttype, 0) + 1
    except Exception as e:
        report["watchlist_summary"]["error"] = str(e)
    
    try:
        # 4. Active Alerts (últimas 10)
        alerts = _load_ticker()[-10:]
        report["active_alerts"] = [
            {
                "type": a.get("type"),
                "message": a.get("message"),
                "source": a.get("source"),
                "timestamp": a.get("timestamp")
            }
            for a in alerts
        ]
    except Exception as e:
        report["active_alerts"] = []
    
    # 5. Threat Level Assessment
    threat_score = 0
    if report["wifi_status"].get("presence_detected"):
        threat_score += 30
    if report["wifi_status"].get("perturbation", 0) > 50:
        threat_score += 25
    if report["watchlist_summary"].get("high_priority", 0) > 0:
        threat_score += 20
    if report["osint_briefing"].get("critical_alerts", 0) > 0:
        threat_score += 25
    
    if threat_score >= 75:
        report["threat_level"] = "RED"
        report["system_health"] = "critical"
    elif threat_score >= 50:
        report["threat_level"] = "YELLOW"
        report["system_health"] = "degraded"
    else:
        report["threat_level"] = "GREEN"
        report["system_health"] = "healthy"
    
    report["threat_score"] = threat_score
    
    return jsonify(report)


# ──── FIN MÓDULOS DE EXPANSIÓN ────


# ──────────────────────── TUNNEL ENDPOINTS ────────────────────────

@app.route('/api/tunnel/start', methods=['POST'])
def api_tunnel_start():
    """Inicia un túnel remoto (ngrok o cloudflared)."""
    if tunnel_mgr is None:
        return jsonify({"status": "error", "message": "Tunnel manager not available"}), 500
    
    data = request.get_json(force=True) or {}
    tunnel_type = data.get('type', 'ngrok')
    
    try:
        if tunnel_type == 'ngrok':
            result = tunnel_mgr.start_ngrok()
        elif tunnel_type == 'cloudflared':
            result = tunnel_mgr.start_cloudflared()
        else:
            return jsonify({"status": "error", "message": "Invalid tunnel type"}), 400
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/tunnel/stop', methods=['POST'])
def api_tunnel_stop():
    """Detiene el túnel activo."""
    if tunnel_mgr is None:
        return jsonify({"status": "error", "message": "Tunnel manager not available"}), 500
    
    return jsonify(tunnel_mgr.stop())


@app.route('/api/tunnel/status', methods=['GET'])
def api_tunnel_status():
    """Obtiene el estado del túnel."""
    if tunnel_mgr is None:
        return jsonify({"status": "unavailable"}), 500
    
    return jsonify(tunnel_mgr.status())


# ──────────────────────── WEBSOCKET EVENTS ────────────────────────

@socketio.on('connect')
def handle_connect():
    """Cliente navegador conectado via WebSocket."""
    print(f"[WS] Cliente conectado: {request.sid}")
    emit('heartbeat', {'status': 'connected', 'server': 'AURA C2'})

@socketio.on('disconnect')
def handle_disconnect():
    """Cliente navegador desconectado."""
    print(f"[WS] Cliente desconectado: {request.sid}")

@socketio.on('telemetry')
def handle_telemetry(data):
    """Recibe telemetria de nodos y la difunde a todos los navegadores."""
    socketio.emit('telemetry_broadcast', data)

@socketio.on('command')
def handle_command(data):
    """Recibe comandos del navegador y los procesa."""
    print(f"[WS] Comando recibido: {data}")
    emit('command_ack', {'status': 'ok', 'received': data})

def emit_event(event_type, data):
    """Funcion global para que otros modulos emitan eventos a navegadores."""
    socketio.emit(event_type, data)

@app.route('/api/descargar-ame', methods=['GET'])
def api_descargar_ame():
    """Endpoint OTA para que el celular descargue el APK directamente."""
    return send_from_directory(os.getcwd(), 'AME_PROD.apk', mimetype='application/vnd.android.package-archive', as_attachment=True, download_name='AME_v1.0.2.apk')

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🚀 AURA Command Center — Servidor Flask v3 + WebSocket")
    print(f"📡 Escuchando en: http://0.0.0.0:5000")
    print(f"📊 Dashboard:    http://localhost:5000/")
    print(f"🔧 API Status:   http://localhost:5000/api/status")
    print(f"📱 OTA APK:      http://0.0.0.0:5000/api/descargar-ame")
    print(f"🔌 WebSocket:    ws://0.0.0.0:5000 (CORS: *)")
    print("="*50 + "\n")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False)
