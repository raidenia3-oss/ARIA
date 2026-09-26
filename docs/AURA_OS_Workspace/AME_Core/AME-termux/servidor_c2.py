"""
AURA C2 Universal — Servidor de Comando y Control con WebSockets
Sirve dashboard universal en / y permite a cualquier navegador
conectarse para recibir telemetria en tiempo real.
Puerto: 8000
"""
import os
import sys
import time
import socket
import logging
import threading
import psutil
from datetime import datetime
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
import eventlet
eventlet.monkey_patch()

logging.basicConfig(level=logging.INFO, format='%(asctime)s [C2] %(levelname)s %(message)s')
logger = logging.getLogger('c2')

# ── Inicializacion ──
app = Flask(__name__,
            template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
            static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = 'aura-c2-secret-2026'

# Importar CORS de manera opcional
try:
    from flask_cors import CORS
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)
except ImportError:
    logger.warning("flask_cors no instalado, CORS deshabilitado")

# SocketIO con CORS totalmente abierto
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='eventlet',
    ping_timeout=2000,
    ping_interval=10000,
    logger=False,
    engineio_logger=False
)

START_TIME = time.time()
connected_clients = set()


# ── Carga opcional de servicios del sistema ──
def _load_tactical_queue():
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Shadow-Core'))
        from tactical_queue import TacticalWorker, enqueue_command, get_tactical_stats
        return TacticalWorker, enqueue_command, get_tactical_stats
    except Exception as e:
        logger.warning("tactical_queue no disponible: %s", e)
        return None, None, None


def _load_stealth_tunnel():
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Shadow-Core', 'Network'))
        from StealthTunnel import get_status as stealth_status, is_tor_running, get_stealth_session
        return stealth_status, is_tor_running, get_stealth_session
    except Exception as e:
        logger.warning("StealthTunnel no disponible: %s", e)
        return None, None, None


TacticalWorker, enqueue_command, get_tactical_stats = _load_tactical_queue()
stealth_status, is_tor_running, get_stealth_session = _load_stealth_tunnel()

# Iniciar TacticalWorker daemon si esta disponible
tactical_worker_instance = None
if TacticalWorker:
    try:
        tactical_worker_instance = TacticalWorker()
        tactical_worker_instance.start()
        logger.info("TacticalWorker daemon iniciado")
    except Exception as e:
        logger.error("Error iniciando TacticalWorker: %s", e)


# ── RUTAS REST ──
@app.route('/')
def index():
    """Sirve el Dashboard Universal."""
    try:
        return render_template('dashboard_universal.html')
    except Exception as e:
        logger.error("Error al servir dashboard: %s", e)
        return f"<h1>AURA C2 Activo</h1><p>Dashboard no disponible: {e}</p>", 200


@app.route('/api/status')
def api_status():
    """Estado del sistema para polling REST."""
    ram = psutil.virtual_memory()
    queued = 0
    if get_tactical_stats:
        try:
            queued = get_tactical_stats().get('queued', 0)
        except Exception:
            pass
    return jsonify({
        'master_online': True,
        'uptime': format_uptime(time.time() - START_TIME),
        'cpu_percent': psutil.cpu_percent(interval=0.3),
        'ram_free_gb': round(ram.available / (1024**3), 2),
        'ram_total_gb': round(ram.total / (1024**3), 2),
        'connected_clients': len(connected_clients),
        'queued_tasks': queued,
        'c2_port': 8000
    })


@app.route('/api/services')
def api_services():
    """Estado de los servicios del sistema (Tactical Queue, StealthTunnel, etc)."""
    services = {
        'websocket': {'online': True, 'clients': len(connected_clients)},
        'tactical_queue': {
            'running': tactical_worker_instance is not None and tactical_worker_instance._running,
            'stats': get_tactical_stats() if get_tactical_stats else {}
        },
        'stealth_tunnel': stealth_status() if stealth_status else {'service_available': False},
        'apk_version': '1.0.2'
    }
    if services['stealth_tunnel'].get('daemon_running'):
        try:
            session = get_stealth_session() if get_stealth_session else None
            if session:
                r = session.get('https://api.ipify.org?format=json', timeout=5)
                if r.ok:
                    import json as _json
                    services['tor_ip'] = _json.loads(r.text).get('ip', 'N/A')
        except Exception:
            pass
    return jsonify(services)


@app.route('/api/descargar-ame', methods=['GET'])
def api_descargar_ame():
    """Endpoint OTA para el APK."""
    from flask import send_from_directory
    apk_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'AME_PROD.apk')
    if os.path.exists(apk_path):
        return send_from_directory(os.path.dirname(apk_path), 'AME_PROD.apk',
                                   mimetype='application/vnd.android.package-archive',
                                   as_attachment=True, download_name='AME_v1.0.2.apk')
    return jsonify({'status': 'error', 'message': 'APK no disponible'}), 404


def format_uptime(seconds):
    """Formatea segundos a HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


# ── WEBSOCKET EVENTS ──
@socketio.on('connect')
def handle_connect():
    from flask import request
    client_id = request.sid
    connected_clients.add(client_id)
    logger.info("Cliente C2 conectado: %s (total: %d)", client_id, len(connected_clients))
    emit('heartbeat', {
        'status': 'connected',
        'timestamp': datetime.now().isoformat(),
        'uptime': format_uptime(time.time() - START_TIME),
        'master': 'aura-c2-universal'
    })
    socketio.emit('clients_count', len(connected_clients))
    emit('real_time_update', {
        'message': 'Navegador conectado al C2 AURA',
        'level': 'info',
        'cpu_percent': psutil.cpu_percent(interval=0.3),
        'ram_free_gb': round(psutil.virtual_memory().available / (1024**3), 2)
    })


@socketio.on('disconnect')
def handle_disconnect():
    from flask import request
    client_id = request.sid
    connected_clients.discard(client_id)
    logger.info("Cliente C2 desconectado: %s (total: %d)", client_id, len(connected_clients))
    socketio.emit('clients_count', len(connected_clients))


@socketio.on('telemetry_report')
def handle_telemetry(data):
    socketio.emit('real_time_update', data)


@socketio.on('command')
def handle_command(cmd):
    socketio.emit('real_time_update', {'message': 'Comando: ' + str(cmd), 'level': 'info'})


def telemetry_broadcaster():
    while True:
        try:
            time.sleep(3)
            if not connected_clients:
                continue
            ram = psutil.virtual_memory()
            payload = {
                'cpu_percent': psutil.cpu_percent(interval=0.1),
                'ram_free_gb': round(ram.available / (1024**3), 2),
                'uptime': format_uptime(time.time() - START_TIME)
            }
            socketio.emit('heartbeat', payload)
        except Exception as e:
            logger.debug("Telemetry broadcaster: %s", e)


broadcast_thread = threading.Thread(target=telemetry_broadcaster, daemon=True, name='c2-broadcaster')
broadcast_thread.start()


# ── MAIN ──
if __name__ == '__main__':
    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return '127.0.0.1'

    local_ip = get_local_ip()
    print("=" * 60)
    print("AURA C2 UNIVERSAL — DASHBOARD EN TIEMPO REAL")
    print("=" * 60)
    print(f"Escuchando en:  0.0.0.0:8000")
    print(f"Dashboard en:   http://{local_ip}:8000/")
    print(f"WebSocket:      ws://{local_ip}:8000/socket.io/")
    print(f"OTA APK:        http://{local_ip}:8000/api/descargar-ame")
    print(f"CORS:           * (cualquier origen permitido)")
    print(f"Servicios:      Tactical Queue + StealthTunnel + WebSocket")
    print("=" * 60)

    try:
        socketio.run(app, host='0.0.0.0', port=8000, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)
    except OSError as e:
        logger.error("Puerto 8000 ocupado: %s. Intentando 8080...", e)
        socketio.run(app, host='0.0.0.0', port=8080, debug=False, use_reloader=False)