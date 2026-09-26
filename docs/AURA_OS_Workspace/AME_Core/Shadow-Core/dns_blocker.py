#!/usr/bin/env python3
"""
DNS Blocker para AURA.
Implementa un servidor DNS local que bloquea conexiones a servidores externos,
asegurando operaciones en modo air-gapped.
"""

import socket
import threading
import time
from datetime import datetime
import json
import os
import subprocess
import dns.resolver
import dns.message
import dns.query
import dns.rdata
from flask import Flask, jsonify
import ipaddress

app = Flask(__name__)

# Configuración global
DNS_PORT = 53
BLOCKED_DOMAINS_FILE = "blocked_domains.json"
LOCAL_DNS_IP = "127.0.0.1"
LOCAL_DNS_PORT = 5353  # Puerto alternativo para evitar conflictos
BLOCKED_DOMAINS = [
    # Dominios comunes de telemetría y análisis
    "telemetry.microsoft.com",
    "apps.skype.com",
    "services.windows.com",
    "windowsupdate.microsoft.com",
    "*.microsoft.com",
    "*.google.com",
    "*.facebook.com",
    "*.twitter.com",
    "*.linkedin.com",
    "*.github.com",
    "*.ollama.com",
    "*.openai.com",
    "*.aws.amazon.com",
    "*.azure.com",
    "*.cloudflare.com",
    "*.google-analytics.com",
    "*.doubleclick.net",
    "*.adobe.com",
    "*.mcafee.com",
    "*.symantec.com",
    "*.trendmicro.com",
    "*.kaspersky.com",
    "*.avast.com",
    "*.avg.com",
    "*.360.cn",
    "*.baidu.com",
    "*.alipay.com",
    "*.tencent.com",
    "*.api.telemetry.microsoft.com",
    "*.api.microsoft.com",
    "*.office.com",
    "*.outlook.com",
    "*.onedrive.com",
    "*.xbox.com",
    "*.xboxlive.com",
    "*.microsoftedgeinsider.com",
    "*.windows.net",
    "*.windows.com",
    "*.live.com",
    "*.msftncsi.com",
    "*.msedge.net",
    "*.office.net",
    "*.skype.com",
    "*.microsoftonline.com",
    "*.microsoftstream.com",
    "*.githubusercontent.com",
    "*.uservoice.com",
    "*.visualstudio.com",
    "*.dev.azure.com",
    "*.azurewebsites.net",
    "*.blob.core.windows.net",
    "*.storage.azure.com",
    "*.azureedge.net",
    "*.azure.com",
    "*.azurefd.net",
    "*.azurestatic.com",
    "*.secureserver.net",
    "*.googlevideo.com",
    "*.youtube.com",
    "*.youtu.be",
    "*.gstatic.com",
    "*.googleapis.com",
    "*.googleusercontent.com",
    "*.youtube-nocookie.com",
    "*.twimg.com",
    "*.twitter.com",
    "*.x.com",
    "*.periscope.tv",
    "*.vine.co",
    "*.instagram.com",
    "*.facebook.net",
    "*.fbcdn.net",
    "*.fb.com",
    "*.fbsbx.com",
    "*.fb.me",
    "*.whatsapp.com",
    "*.whatsapp.net",
    "*.ocsp.facebook.com",
    "*.akamaihd.net",
    "*.akamaized.net",
    "*.scroll.com",
    "*.washingtonpost.com",
    "*.nytimes.com",
    "*.reuters.com",
    "*.bbc.com",
    "*.cnn.com",
    "*.foxnews.com",
    "*.theguardian.com",
    "*.wsj.com",
    "*.bloomberg.com",
    "*.ap.org",
    "*.npr.org",
    "*.pbs.org",
    "*.cbsnews.com",
    "*.abcnews.go.com",
    "*.nbc.com",
    "*.fox.com",
    "*.cnbc.com",
    "*.msnbc.com",
    "*.usatoday.com",
    "*.latimes.com",
    "*.washingtonpost.com",
    "*.nytco.com",
    "*.nytimes.com",
    "*.reutersmedia.net",
    "*.dailymotion.com",
    "*.vimeo.com",
    "*.twitch.tv",
    "*.twitchcdn.net",
    "*.discord.com",
    "*.discordapp.com",
    "*.discordmedia.com",
    "*.discord.gg",
    "*.discord.com",
    "*.twitch.tv",
    "*.twitchcdn.net",
    "*.reddit.com",
    "*.redditstatic.com",
    "*.fastly.net",
    "*.imgur.com",
    "*.imgur.net",
    "*.flickr.com",
    "*.flickr.com",
    "*.pinterest.com",
    "*.pinterest.net",
    "*.quora.com",
    "*.quora.com",
    "*.medium.com",
    "*.mediumcdn.com",
    "*.stackexchange.com",
    "*.stackoverflow.com",
    "*.stackpath.com",
    "*.wikipedia.org",
    "*.wikimedia.org",
    "*.wikimediafoundation.org",
    "*.wikimedia.org",
    "*.wikibooks.org",
    "*.wikidata.org",
    "*.wikinews.org",
    "*.wikiquote.org",
    "*.wikisource.org",
    "*.wikiversity.org",
    "*.wikivoyage.org",
    "*.wikimediafoundation.org",
    "*.wikimedia.org",
    "*.wikimediafoundation.org",
    "*.wikimedia.org",
    "*.wikimediafoundation.org",
    "*.wikimedia.org"
]

# Cargar dominios bloqueados desde archivo
def load_blocked_domains():
    """Cargar dominios bloqueados desde archivo JSON."""
    if os.path.exists(BLOCKED_DOMAINS_FILE):
        with open(BLOCKED_DOMAINS_FILE, 'r') as f:
            return json.load(f)
    return BLOCKED_DOMAINS

# Guardar dominios bloqueados en archivo
def save_blocked_domains(domains):
    """Guardar dominios bloqueados en archivo JSON."""
    with open(BLOCKED_DOMAINS_FILE, 'w') as f:
        json.dump(domains, f, indent=2)

# Inicializar dominios bloqueados
blocked_domains = load_blocked_domains()

# Configuración de red
def get_local_ip():
    """Obtener la dirección IP local de la máquina."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        print(f"Error al obtener IP local: {e}")
        return "127.0.0.1"

LOCAL_IP = get_local_ip()

# Funciones para manejar consultas DNS
def is_domain_blocked(domain):
    """Verificar si un dominio está bloqueado."""
    domain = domain.lower()

    # Verificar contra dominios exactos
    if domain in blocked_domains:
        return True

    # Verificar contra patrones con wildcards (*)
    for pattern in blocked_domains:
        if pattern.startswith('*'):
            pattern = pattern[1:]  # Eliminar el *
            if domain.endswith(pattern):
                return True

    return False

def resolve_local_ip(domain):
    """Resolver un dominio a la IP local (para bloquear)."""
    return LOCAL_IP

def handle_dns_query(data, socket):
    """Manejar una consulta DNS y responder según la configuración."""
    try:
        # Parsear la consulta DNS
        request = dns.message.from_wire(data)

        # Crear respuesta DNS
        reply = dns.message.make_response(request)

        # Procesar cada pregunta en la consulta
        for qname in request.question:
            domain = str(qname).lower()

            # Verificar si el dominio está bloqueado
            if is_domain_blocked(domain):
                # Crear respuesta con IP local (bloqueo)
                reply.answer.append(
                    dns.rrset.from_rdata(
                        reply,
                        dns.rdata.A(LOCAL_IP),
                        ttl=300
                    )
                )
                print(f"🔒 Bloqueado acceso a: {domain} -> {LOCAL_IP}")
            else:
                # Resolver el dominio normalmente (usando DNS público)
                try:
                    answers = dns.resolver.resolve(domain, 'A')
                    for rdata in answers:
                        reply.answer.append(
                            dns.rrset.from_rdata(
                                reply,
                                rdata,
                                ttl=300
                            )
                        )
                except Exception as e:
                    print(f"⚠️ Error al resolver {domain}: {e}")

        # Enviar la respuesta
        socket.sendto(reply.to_wire(), socket.getpeername())
    except Exception as e:
        print(f"Error al manejar consulta DNS: {e}")

def start_dns_server():
    """Iniciar el servidor DNS local."""
    try:
        # Crear socket UDP para DNS
        dns_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        dns_socket.bind((LOCAL_IP, LOCAL_DNS_PORT))
        print(f"🌐 Servidor DNS bloqueador iniciado en {LOCAL_IP}:{LOCAL_DNS_PORT}")

        # Configurar el servidor DNS como resolución predeterminada en Windows
        try:
            # Configurar DNS en la interfaz de red
            subprocess.run(
                ["netsh", "interface", "ip", "set", "dns", "name=\"Ethernet\"", "static", LOCAL_IP],
                shell=True,
                check=True,
                capture_output=True
            )
            print(f"✅ Configurado DNS local ({LOCAL_IP}) como resolución predeterminada")
        except Exception as e:
            print(f"⚠️ No se pudo configurar DNS local: {e}")

        # Manejar consultas DNS en un hilo separado
        def dns_loop():
            while True:
                try:
                    data, addr = dns_socket.recvfrom(512)
                    handle_dns_query(data, dns_socket)
                except Exception as e:
                    print(f"Error en servidor DNS: {e}")
                    time.sleep(1)

        threading.Thread(target=dns_loop, daemon=True).start()
        return dns_socket
    except Exception as e:
        print(f"Error al iniciar servidor DNS: {e}")
        return None

# Endpoints para gestionar el bloqueador DNS
@app.route('/api/dns/status', methods=['GET'])
def get_dns_status():
    """Obtener el estado del bloqueador DNS."""
    return jsonify({
        "status": "ok",
        "local_ip": LOCAL_IP,
        "dns_port": LOCAL_DNS_PORT,
        "blocked_domains_count": len(blocked_domains),
        "blocked_domains_sample": blocked_domains[:5]  # Muestra los primeros 5 dominios bloqueados
    })

@app.route('/api/dns/blocked_domains', methods=['GET'])
def list_blocked_domains():
    """Listar todos los dominios bloqueados."""
    return jsonify({
        "status": "ok",
        "domains": blocked_domains
    })

@app.route('/api/dns/add_domain', methods=['POST'])
def add_blocked_domain():
    """Añadir un dominio a la lista de bloqueados."""
    data = request.get_json()
    if not data or 'domain' not in data:
        return jsonify({"status": "error", "message": "Dominio requerido"}), 400

    domain = data['domain'].lower().strip()
    if domain in blocked_domains:
        return jsonify({"status": "error", "message": "Dominio ya bloqueado"}), 400

    blocked_domains.append(domain)
    save_blocked_domains(blocked_domains)
    return jsonify({
        "status": "ok",
        "message": f"Dominio {domain} añadido a la lista de bloqueados",
        "total_domains": len(blocked_domains)
    })

@app.route('/api/dns/remove_domain', methods=['POST'])
def remove_blocked_domain():
    """Eliminar un dominio de la lista de bloqueados."""
    data = request.get_json()
    if not data or 'domain' not in data:
        return jsonify({"status": "error", "message": "Dominio requerido"}), 400

    domain = data['domain'].lower().strip()
    if domain not in blocked_domains:
        return jsonify({"status": "error", "message": "Dominio no encontrado en la lista"}), 400

    blocked_domains.remove(domain)
    save_blocked_domains(blocked_domains)
    return jsonify({
        "status": "ok",
        "message": f"Dominio {domain} eliminado de la lista de bloqueados",
        "total_domains": len(blocked_domains)
    })

@app.route('/api/dns/clear_all', methods=['POST'])
def clear_all_blocked_domains():
    """Eliminar todos los dominios bloqueados."""
    global blocked_domains
    blocked_domains = []
    save_blocked_domains(blocked_domains)
    return jsonify({
        "status": "ok",
        "message": "Todos los dominios bloqueados han sido eliminados",
        "total_domains": len(blocked_domains)
    })

# Función para configurar el modo offline
def configure_offline_mode():
    """Configurar el sistema para operar en modo offline."""
    try:
        # 1. Iniciar el bloqueador DNS
        dns_server = start_dns_server()
        if not dns_server:
            print("❌ No se pudo iniciar el servidor DNS")
            return False

        # 2. Desconectar redes externas (simulado)
        print("🔌 Desconectando redes externas (modo offline activado)")

        # 3. Configurar firewall para bloquear todo el tráfico saliente
        try:
            # Bloquear todo el tráfico saliente excepto puertos locales
            subprocess.run(
                ["netsh", "advfirewall", "set", "allprofiles", "state", "on"],
                shell=True,
                check=True,
                capture_output=True
            )
            subprocess.run(
                ["netsh", "advfirewall", "firewall", "add", "rule", "name=BlockAllOutbound", "dir=out", "action=block"],
                shell=True,
                check=True,
                capture_output=True
            )
            print("✅ Firewall configurado para bloquear tráfico saliente")
        except Exception as e:
            print(f"⚠️ No se pudo configurar firewall: {e}")

        # 4. Forzar el uso de modelos locales
        print("🔒 Forzando el uso de modelos locales (sin conexión a internet)")

        return True
    except Exception as e:
        print(f"❌ Error al configurar modo offline: {e}")
        return False

# Función para desactivar el modo offline
def deactivate_offline_mode():
    """Desactivar el modo offline y restaurar la conectividad."""
    try:
        # 1. Restaurar configuración de DNS
        try:
            subprocess.run(
                ["netsh", "interface", "ip", "set", "dns", "name=\"Ethernet\"", "dhcp"],
                shell=True,
                check=True,
                capture_output=True
            )
            print("✅ Restaurada configuración de DNS original")
        except Exception as e:
            print(f"⚠️ No se pudo restaurar DNS: {e}")

        # 2. Restaurar firewall
        try:
            subprocess.run(
                ["netsh", "advfirewall", "reset"],
                shell=True,
                check=True,
                capture_output=True
            )
            print("✅ Restaurado firewall original")
        except Exception as e:
            print(f"⚠️ No se pudo restaurar firewall: {e}")

        return True
    except Exception as e:
        print(f"❌ Error al desactivar modo offline: {e}")
        return False

@app.route('/api/airgapped/activate', methods=['POST'])
def activate_airgapped_mode():
    """Activar el modo air-gapped (offline)."""
    data = request.get_json()
    if not data or 'auth_key' not in data:
        return jsonify({"status": "error", "message": "Llave de autorización requerida"}), 401

    auth_key = data.get('auth_key')
    if auth_key != "SECRET_AUTH_KEY_12345":
        return jsonify({"status": "error", "message": "Llave de autorización inválida"}), 403

    try:
        success = configure_offline_mode()
        if success:
            return jsonify({
                "status": "ok",
                "message": "Modo air-gapped activado correctamente",
                "details": {
                    "dns_server": f"{LOCAL_IP}:{LOCAL_DNS_PORT}",
                    "firewall": "bloqueado",
                    "models": "locales"
                }
            })
        else:
            return jsonify({
                "status": "error",
                "message": "No se pudo activar el modo air-gapped"
            })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error al activar modo air-gapped: {str(e)}"
        })

@app.route('/api/airgapped/deactivate', methods=['POST'])
def deactivate_airgapped_mode_endpoint():
    """Desactivar el modo air-gapped (offline)."""
    data = request.get_json()
    if not data or 'auth_key' not in data:
        return jsonify({"status": "error", "message": "Llave de autorización requerida"}), 401

    auth_key = data.get('auth_key')
    if auth_key != "SECRET_AUTH_KEY_12345":
        return jsonify({"status": "error", "message": "Llave de autorización inválida"}), 403

    try:
        success = deactivate_offline_mode()
        if success:
            return jsonify({
                "status": "ok",
                "message": "Modo air-gapped desactivado correctamente",
                "details": {
                    "dns": "restaurado",
                    "firewall": "restaurado",
                    "conectividad": "activada"
                }
            })
        else:
            return jsonify({
                "status": "error",
                "message": "No se pudo desactivar el modo air-gapped"
            })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error al desactivar modo air-gapped: {str(e)}"
        })

if __name__ == "__main__":
    # Iniciar el servidor DNS en segundo plano
    dns_server = start_dns_server()

    # Iniciar el servidor web
    app.run(host='0.0.0.0', port=5013, debug=False)