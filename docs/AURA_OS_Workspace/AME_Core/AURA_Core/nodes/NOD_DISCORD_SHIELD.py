#!/usr/bin/env python3
"""
NOD_DISCORD_SHIELD.py — Proxy interceptador para proteger cuentas de Discord
Intercepta tráfico de API de Discord y bloquea eventos peligrosos como kicks, bans y message deletes
"""

import os
import json
import time
import logging
import subprocess
from pathlib import Path
from datetime import datetime
from flask import Flask, jsonify
from mitmproxy import http, websockets, ctx, options, proxyconfig

# Configuración
PROXY_PORT = 8080
API_PORT = 5004
CONFIG_FILE = Path(__file__).resolve().parent.parent / "shield_config.json"
LOG_FILE = Path(__file__).resolve().parent.parent / "discord_shield.log"
CERT_DIR = Path(__file__).resolve().parent.parent / "mitmproxy_certs"
CERT_FILE = CERT_DIR / "discord_shield.crt"
KEY_FILE = CERT_DIR / "discord_shield.key"

# Inicializar Flask
app = Flask(__name__)

# Estado global
state = {
    "status": "stopped",
    "rules_active": {},
    "blocked_events": [],
    "last_updated": None
}

# Configuración por defecto
DEFAULT_CONFIG = {
    "block_kicks": True,
    "block_message_deletes": True,
    "block_bans": True,
    "block_suspensions": True,
    "log_all_events": False,
    "whitelist_servers": []
}

def setup_logging():
    """Configura logging para el escudo"""
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logging.getLogger().addHandler(console_handler)

def load_config():
    """Carga la configuración desde shield_config.json"""
    if not CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        return DEFAULT_CONFIG

    with open(CONFIG_FILE) as f:
        config = json.load(f)

    # Asegurar que tenga todas las claves por defecto
    for key, value in DEFAULT_CONFIG.items():
        if key not in config:
            config[key] = value

    return config

def save_config(config):
    """Guarda la configuración en shield_config.json"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def log_event(event_type, details):
    """Registra un evento bloqueado"""
    timestamp = datetime.now().isoformat()
    log_entry = f"{timestamp} - [BLOCKED] {event_type}: {details}"

    # Registrar en archivo
    with open(LOG_FILE, 'a') as f:
        f.write(log_entry + "\n")

    # Registrar en memoria
    state["blocked_events"].append({
        "timestamp": timestamp,
        "type": event_type,
        "details": details
    })

    # Limitar el tamaño del log en memoria
    if len(state["blocked_events"]) > 100:
        state["blocked_events"] = state["blocked_events"][-100:]

    # Registrar con logging
    logging.info(log_entry)

def generate_certificates():
    """Genera certificados para mitmproxy"""
    CERT_DIR.mkdir(parents=True, exist_ok=True)

    # Verificar si ya existen certificados
    if CERT_FILE.exists() and KEY_FILE.exists():
        return True

    try:
        # Usar mitmdump para generar certificados
        cmd = [
            "mitmdump",
            "--set", "ssl_cert=/tmp/discord_shield.crt",
            "--set", "ssl_key=/tmp/discord_shield.key",
            "--set", "mode=transparent",
            "--set", "showhost=True",
            "--set", "quiet=True",
            "--set", "ssl_insecure=True",
            "--set", "no_keylog=True",
            "--set", "ignore_hosts=localhost,127.0.0.1",
            "--set", "listen_port=8080",
            "--set", "exit_on_close=True",
            "--set", "exit_on_idle=True",
            "--set", "exit_on_error=True",
            "--set", "exit_on_timeout=True",
            "--set", "exit_on_quit=True",
            "--set", "exit_on_eof=True",
            "--set", "exit_on_eof=True",
            "--set", "exit_on_eof=True",
            "--set", "exit_on_eof=True",
            "--set", "exit_on_eof=True"
        ]

        # Generar certificados con openssl
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", str(KEY_FILE),
            "-out", str(CERT_FILE),
            "-days", "365",
            "-nodes",
            "-subj", "/CN=discord.com"
        ], check=True)

        logging.info(f"✅ Certificados generados en {CERT_DIR}")
        return True
    except Exception as e:
        logging.error(f"❌ Error generando certificados: {e}")
        return False

def is_discord_traffic(flow):
    """Verifica si el tráfico es de Discord"""
    host = flow.request.host
    return host in ["discord.com", "discordapp.com", "canary.discord.com"]

def is_websocket(flow):
    """Verifica si es una conexión WebSocket"""
    return flow.request.headers.get("Upgrade", "").lower() == "websocket"

def analyze_http_request(flow):
    """Analiza solicitudes HTTP de Discord"""
    if not is_discord_traffic(flow):
        return

    config = load_config()
    body = flow.request.text

    # Analizar eventos de Discord (JSON)
    if body and body.startswith('{'):
        try:
            data = json.loads(body)
            event_type = data.get("op")  # WebSocket operation

            # Eventos peligrosos
            if event_type == 2:  # Dispatch (eventos)
                t = data.get("t")
                if t == "GUILD_MEMBER_REMOVE" and config["block_kicks"]:
                    log_event("KICK", f"User removed from guild: {data.get('d', {}).get('guild_id', 'unknown')}")
                    flow.response = http.HTTPResponse.make(
                        200,
                        b"{}",
                        {"Content-Type": "application/json"}
                    )
                    return

                elif t == "MESSAGE_DELETE" and config["block_message_deletes"]:
                    log_event("MESSAGE_DELETE", f"Message deleted: {data.get('d', {}).get('channel_id', 'unknown')}")
                    flow.response = http.HTTPResponse.make(
                        200,
                        b"{}",
                        {"Content-Type": "application/json"}
                    )
                    return

                elif t == "GUILD_BAN_ADD" and config["block_bans"]:
                    log_event("BAN", f"User banned: {data.get('d', {}).get('guild_id', 'unknown')}")
                    flow.response = http.HTTPResponse.make(
                        200,
                        b"{}",
                        {"Content-Type": "application/json"}
                    )
                    return

                elif t == "USER_UPDATE" and config["block_suspensions"]:
                    # Verificar si es una suspensión de cuenta
                    if "user" in data.get("d", {}) and "username" in data["d"]["user"]:
                        log_event("ACCOUNT_SUSPENSION", "Possible account suspension detected")
                        flow.response = http.HTTPResponse.make(
                            200,
                            b"{}",
                            {"Content-Type": "application/json"}
                        )
                        return

            # Log de todos los eventos si está activado
            if config["log_all_events"] and event_type == 2:
                log_event("DISCORD_EVENT", f"Event: {t}")

        except json.JSONDecodeError:
            pass

def analyze_websocket_message(flow):
    """Analiza mensajes WebSocket de Discord"""
    if not is_discord_traffic(flow) or not is_websocket(flow):
        return

    config = load_config()
    body = flow.request.text

    if body and body.startswith('{'):
        try:
            data = json.loads(body)
            event_type = data.get("op")

            if event_type == 2:  # Dispatch
                t = data.get("t")
                if t == "GUILD_MEMBER_REMOVE" and config["block_kicks"]:
                    log_event("KICK_WS", f"WebSocket kick detected: {data.get('d', {}).get('guild_id', 'unknown')}")
                    flow.response = websockets.WebSocketMessage(
                        b"{}",
                        websockets.WebSocketMessageType.TEXT
                    )
                    return

                elif t == "MESSAGE_DELETE" and config["block_message_deletes"]:
                    log_event("MESSAGE_DELETE_WS", f"WebSocket message delete: {data.get('d', {}).get('channel_id', 'unknown')}")
                    flow.response = websockets.WebSocketMessage(
                        b"{}",
                        websockets.WebSocketMessageType.TEXT
                    )
                    return

        except json.JSONDecodeError:
            pass

def filter_packet(flow):
    """Filtra paquetes según las reglas de configuración"""
    analyze_http_request(flow)
    analyze_websocket_message(flow)

def start_proxy():
    """Inicia el proxy mitmproxy"""
    try:
        # Generar certificados si no existen
        if not generate_certificates():
            logging.error("❌ No se pudieron generar certificados. Proxy no iniciado.")
            return False

        # Configuración de mitmproxy
        opts = options.Options(
            listen_port=PROXY_PORT,
            ssl_insecure=True,
            no_keylog=True,
            showhost=True,
            mode="transparent",
            ignore_hosts="localhost,127.0.0.1"
        )

        # Configuración de proxy
        config = proxyconfig.Config(
            listen_host="0.0.0.0",
            listen_port=PROXY_PORT,
            ssl_cert=str(CERT_FILE),
            ssl_key=str(KEY_FILE)
        )

        # Iniciar proxy
        ctx.options = opts
        ctx.proxy_config = config

        # Configurar addons
        ctx.addons.add(filter_packet)

        # Iniciar proxy en segundo plano
        import threading
        proxy_thread = threading.Thread(target=ctx.start_proxy)
        proxy_thread.daemon = True
        proxy_thread.start()

        state["status"] = "running"
        state["last_updated"] = datetime.now().isoformat()
        logging.info("✅ Proxy Discord Shield iniciado en localhost:8080")
        return True

    except Exception as e:
        logging.error(f"❌ Error iniciando proxy: {e}")
        state["status"] = "error"
        return False

@app.route('/status')
def get_status():
    """Endpoint para consultar el estado del escudo"""
    return jsonify(state)

@app.route('/config')
def get_config():
    """Endpoint para obtener la configuración actual"""
    config = load_config()
    return jsonify({
        "status": "ok",
        "config": config,
        "rules": state["rules_active"]
    })

@app.route('/log')
def get_log():
    """Endpoint para obtener el último log de eventos bloqueados"""
    return jsonify({
        "status": "ok",
        "events": state["blocked_events"]
    })

@app.route('/update_config', methods=['POST'])
def update_config():
    """Endpoint para actualizar la configuración"""
    try:
        new_config = request.json
        config = load_config()

        # Actualizar solo las claves proporcionadas
        for key, value in new_config.items():
            if key in config:
                config[key] = value

        save_config(config)
        state["rules_active"] = config
        state["last_updated"] = datetime.now().isoformat()

        return jsonify({
            "status": "ok",
            "message": "Configuración actualizada",
            "config": config
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error actualizando configuración: {str(e)}"
        }), 400

def execute(input_data=None):
    """Función principal para ejecutar el escudo"""
    setup_logging()
    load_config()

    # Iniciar proxy
    if not start_proxy():
        logging.error("❌ No se pudo iniciar el proxy")
        return False

    # Iniciar servidor Flask
    app.run(port=API_PORT, threaded=True)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Discord Shield Proxy")
    parser.add_argument("--port", type=int, default=API_PORT, help="Puerto para la API")
    args = parser.parse_args()

    print(f"🛡️  Iniciando Discord Shield en localhost:{args.port}")
    print(f"🔗  Proxy en localhost:8080")
    print(f"📄  Configuración: {CONFIG_FILE}")
    print(f"📝  Logs: {LOG_FILE}")

    execute()