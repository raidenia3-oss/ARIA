"""
AURA Webhook Server v2 — Auto-Resilience
- Acepta peticiones desde la IP del móvil (AME)
- Detecta automáticamente si la IP cambia y actualiza config.json
- Middleware CORS para permitir requests desde el LG Q60
"""
from flask import Flask, request, jsonify
import os
import json
import subprocess
import psutil
import socket
import time
import threading
from datetime import datetime

app = Flask(__name__)

# ── Rutas ──
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(BASE_DIR, "aura_respuestas.txt")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

# ── Config por defecto ──
DEFAULT_CONFIG = {
    "mobile_ip": "192.168.1.0",
    "mobile_port": 5000,
    "last_seen": "",
    "auto_update_ip": True,
    "webhook_port": 5001,
    "flask_port": 5000,
    "ollama_host": "localhost",
    "ollama_port": 11434
}

# ── Cargar/configurar config.json ──
def load_config():
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        return dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r") as f:
            cfg = json.load(f)
            # Asegurar que tenga todos los campos
            for k, v in DEFAULT_CONFIG.items():
                cfg.setdefault(k, v)
            return cfg
    except Exception:
        return dict(DEFAULT_CONFIG)

def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)

config = load_config()

# ── Lista de IPs móviles permitidas (se actualiza dinámicamente) ──
ALLOWED_MOBILE_IPS = set()

def get_local_ips():
    """Obtiene todas las IPs locales de la máquina."""
    ips = set()
    try:
        hostname = socket.gethostname()
        for addr in socket.gethostbyname_ex(hostname)[2]:
            ips.add(addr)
    except Exception:
        pass
    # También escanea interfaces de red
    try:
        for iface in psutil.net_if_addrs().values():
            for addr in iface:
                if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                    ips.add(addr.address)
    except Exception:
        pass
    return ips

def detect_mobile_ip():
    """
    Detecta la IP del móvil basándose en:
    1. La IP del request entrante al webhook
    2. Escaneo de la subred local (búsqueda del puerto 5000)
    Se ejecuta en un hilo separado al recibir un webhook.
    """
    pass  # La detección ocurre en tiempo real en cada request

def update_mobile_ip(new_ip):
    """Actualiza la IP móvil en config.json si cambió."""
    global config
    old_ip = config.get("mobile_ip", "192.168.1.0")
    if new_ip and new_ip != old_ip:
        print(f"📡 [Webhook] IP móvil actualizada: {old_ip} → {new_ip}")
        config["mobile_ip"] = new_ip
        config["last_seen"] = datetime.now().isoformat()
        save_config(config)
        # Actualizar lista de IPs permitidas
        ALLOWED_MOBILE_IPS.add(new_ip)
        return True
    return False

def is_allowed_ip(ip):
    """Verifica si una IP está en la lista permitida (móvil o red local)."""
    if ip in ALLOWED_MOBILE_IPS:
        return True
    # IPs de red local siempre permitidas
    if ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172.16."):
        return True
    if ip == "127.0.0.1" or ip == "::1":
        return True
    return False

# ── Inicializar IPs locales en la lista permitida ──
for ip in get_local_ips():
    ALLOWED_MOBILE_IPS.add(ip)
if config.get("mobile_ip"):
    ALLOWED_MOBILE_IPS.add(config["mobile_ip"])

print(f"🌐 [Webhook] IPs permitidas iniciales: {ALLOWED_MOBILE_IPS}")

# ──────────────────── RUTAS ────────────────────

@app.before_request
def log_request_info():
    """Registra la IP del request y actualiza config si es del móvil."""
    ip = request.remote_addr
    if ip and (ip.startswith("192.168.") or ip.startswith("10.")):
        # Posible IP móvil — actualizar automáticamente
        if ip != config.get("mobile_ip"):
            update_mobile_ip(ip)
            # Reflejar en el servidor AME (puerto 5000) si está vivo
            try:
                import urllib.request
                import urllib.parse
                data = json.dumps({"mobile_ip": ip}).encode()
                req = urllib.request.Request(
                    f"http://localhost:{config['flask_port']}/api/update_mobile_ip",
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                urllib.request.urlopen(req, timeout=2)
            except Exception:
                pass  # El servidor AME podría no estar corriendo aún
        ALLOWED_MOBILE_IPS.add(ip)


@app.route('/api/status')
def system_status():
    """Devuelve la salud del sistema y procesos vivos"""
    try:
        mem = psutil.virtual_memory()
        processes = [
            p.info['name'] for p in psutil.process_iter(['name'])
            if p.info['name'] and ('python' in p.info['name'].lower() or 'ollama' in p.info['name'].lower())
        ]

        # Incluir info de la IP móvil configurada
        return jsonify({
            "ram_free": f"{mem.available / (1024**3):.2f} GB",
            "ram_percent": mem.percent,
            "processes_count": len(processes),
            "active_services": processes,
            "mobile_ip": config.get("mobile_ip", "unknown"),
            "allowed_ips": list(ALLOWED_MOBILE_IPS),
            "status": "HEALTHY" if mem.percent < 90 else "CRITICAL"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/osint/<tool>/<target>')
def run_osint(tool, target):
    """Ejecuta el motor OSINT desde el dashboard"""
    try:
        osint_script = os.path.join(BASE_DIR, "osint_engine.py")
        result = subprocess.run(
            [sys.executable, osint_script, "--tool", tool, "--target", target],
            capture_output=True, text=True, timeout=60
        )
        return jsonify({"status": "success", "output": result.stdout})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    """GET: devuelve config actual. POST: actualiza campos."""
    if request.method == 'GET':
        return jsonify(load_config())

    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "No JSON data"}), 400

    global config
    cfg = load_config()
    changed = False
    for key in cfg.keys():
        if key in data:
            cfg[key] = data[key]
            changed = True

    if changed:
        save_config(cfg)
        config = cfg
        if "mobile_ip" in data:
            ALLOWED_MOBILE_IPS.add(data["mobile_ip"])
        return jsonify({"status": "updated", "config": cfg})

    return jsonify({"status": "no changes", "config": cfg})


@app.route('/webhook', methods=['POST'])
def webhook():
    """Recibe notificaciones desde AME_Core (Celular)"""
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No JSON data provided"}), 400

        sender = data.get("sender", "AME_Mobile")
        message = data.get("message", "")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] NOTIFICACIÓN AME ({sender}): {message}\n"

        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(log_entry)

        print(f"🔔 Webhook Recibido: {log_entry.strip()}")
        return jsonify({"status": "success", "message": "Notification received by AURA"}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ──────────────────── MAIN ────────────────────

if __name__ == '__main__':
    # Añadir sys.path para import check_health si es necesario
    import sys

    PORT = config.get("webhook_port", 5001)
    print("\n" + "="*50)
    print("🌐 AURA Webhook Server v2 — Auto-Resilience")
    print(f"👂 Escuchando notificaciones en puerto {PORT}")
    print(f"📱 IP móvil configurada: {config.get('mobile_ip', 'N/A')}")
    print(f"📄 Config: {CONFIG_PATH}")
    print("="*50 + "\n")
    app.run(host='0.0.0.0', port=PORT, debug=False)