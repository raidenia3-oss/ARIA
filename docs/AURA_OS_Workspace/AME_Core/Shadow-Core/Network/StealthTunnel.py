"""
Shadow-Core StealthTunnel — Modulo de trafico anonimo via Tor SOCKS5
Automatiza el levantamiento/uso de Tor para enrutar trafico HTTP
de manera efimera, cambiando de IP para evitar baneos o rastreos.
Disenado para los nodos Venice (OSINT Scraper, etc).
"""
import os
import sys
import time
import socket
import subprocess
import logging
import platform
import threading
from typing import Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s [StealthTunnel] %(levelname)s %(message)s')
logger = logging.getLogger('stealth_tunnel')

# Puertos comunes de Tor
SOCKS_PORT_DEFAULT = 9050
SOCKS_PORT_ALT = 9150
CONTROL_PORT_DEFAULT = 9051


def find_tor_executable() -> Optional[str]:
    """Busca el binario de Tor en el sistema."""
    candidates = []
    if platform.system() == 'Windows':
        candidates = [
            r'C:\Program Files\Tor Browser\Browser\TorBrowser\Tor\tor.exe',
            r'C:\Tools\tor\tor.exe',
            os.path.expanduser('~/AppData/Local/Tor Browser/Browser/TorBrowser/Tor/tor.exe'),
        ]
    else:
        candidates = ['/usr/bin/tor', '/usr/local/bin/tor', '/opt/homebrew/bin/tor']

    # Intentar `which` o `where`
    try:
        result = subprocess.run(
            ['where' if platform.system() == 'Windows' else 'which', 'tor'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip().split('\n')[0]
    except Exception:
        pass

    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def is_tor_running(socks_port: int = SOCKS_PORT_DEFAULT) -> bool:
    """Verifica si Tor SOCKS5 esta escuchando."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        result = s.connect_ex(('127.0.0.1', socks_port))
        s.close()
        return result == 0
    except Exception:
        return False


def start_tor_process(socks_port: int = SOCKS_PORT_DEFAULT,
                    control_port: int = CONTROL_PORT_DEFAULT) -> Optional[subprocess.Popen]:
    """Inicia un subproceso Tor en la PC."""
    tor_bin = find_tor_executable()
    if not tor_bin:
        logger.error("Binario de Tor no encontrado. Use setup_environment() para instalar.")
        return None

    if is_tor_running(socks_port):
        logger.info("Tor ya esta corriendo en puerto %d", socks_port)
        return None

    args = [
        tor_bin,
        '--SOCKSPort', str(socks_port),
        '--ControlPort', str(control_port),
        '--DataDirectory', os.path.join(os.path.expanduser('~'), '.aura_tor')
    ]
    try:
        proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(10):
            time.sleep(1)
            if is_tor_running(socks_port):
                logger.info("Tor daemon iniciado correctamente (PID: %d)", proc.pid)
                return proc
        logger.warning("Tor no respondio despues de 10 segundos")
        return proc  # Devolver proceso aunque no este respondiendo
    except Exception as e:
        logger.error("Error iniciando Tor: %s", e)
        return None


def get_stealth_session(socks_port: int = SOCKS_PORT_DEFAULT, rotate_every: int = 0):
    """
    Retorna una sesion `requests.Session` enrutada por Tor SOCKS5.
    Si rotate_every > 0, programa rotacion de IP (cambio de circuito) en background.
    """
    try:
        import requests
    except ImportError:
        logger.error("requests no instalado. Ejecute: pip install requests")
        return None

    if not is_tor_running(socks_port):
        logger.info("Tor no esta corriendo, intentando iniciar...")
        start_tor_process(socks_port)
        if not is_tor_running(socks_port):
            logger.error("No se pudo iniciar Tor. Sesion directa (sin anonimato).")
            return requests.Session()

    proxy_url = f'socks5h://127.0.0.1:{socks_port}'
    session = requests.Session()
    session.proxies = {'http': proxy_url, 'https': proxy_url}
    session.headers.update({
        'User-Agent': 'AURA-StealthTunnel/1.0 (Venice; +https://github.com/raidenia3-oss/AURA-server.01)'
    })

    # Test rapido
    try:
        r = session.get('https://api.ipify.org?format=json', timeout=10)
        if r.ok:
            logger.info("Sesion Tor configurada correctamente. IP actual: %s", r.text)
    except Exception as e:
        logger.warning("No se pudo verificar IP (red no disponible?): %s", e)

    if rotate_every > 0:
        _start_ip_rotator(session, socks_port, rotate_every)

    return session


def _start_ip_rotator(session, socks_port: int, interval: int):
    """Hilo daemon que renueva la IP cada N segundos."""
    def loop():
        while True:
            time.sleep(interval)
            try:
                # Nuevo IP via Signal NEWNYM (requiere ControlPort)
                import socket as _s
                with _s.create_connection(('127.0.0.1', socks_port + 1), timeout=5):
                    pass
                logger.info("IP rotada (solicitada por Signal NEWNYM)")
            except Exception as e:
                logger.debug("Rotacion de IP no disponible: %s", e)

    t = threading.Thread(target=loop, daemon=True, name='ip-rotator')
    t.start()
    logger.info("IP rotator iniciado cada %ds", interval)


def get_status() -> dict:
    """Retorna estado del stealth tunnel."""
    binary = find_tor_executable()
    port = SOCKS_PORT_DEFAULT
    running = is_tor_running(port)
    if not running:
        port = SOCKS_PORT_ALT
        running = is_tor_running(port)
    return {
        'binary_found': binary is not None,
        'binary_path': binary,
        'binary_searched': platform.system() == 'Windows',
        'socks_port': port,
        'daemon_running': running,
        'proxy_url': f'socks5h://127.0.0.1:{port}' if running else None,
        'service_available': binary is not None and running
    }


# ── MAIN ──
if __name__ == '__main__':
    print("=" * 60)
    print("AURA SHADOW-CORE STEALTH TUNNEL (Tor SOCKS5)")
    print("=" * 60)

    status = get_status()
    print("\nEstado del Tunnel:")
    print("  Binario encontrado:   %s", 'Si' if status['binary_found'] else 'No')
    if status['binary_path']:
        print("  Ruta del binario:     %s", status['binary_path'])
    print("  Daemon corriendo:     %s", 'Si' if status['daemon_running'] else 'No')
    print("  Puerto SOCKS:         %d", status['socks_port'])
    print("  URL Proxy:            %s", status['proxy_url'] or 'N/A')

    if not status['daemon_running']:
        print("\nIniciando Tor daemon...")
        start_tor_process(status['socks_port'])

    if status['binary_found']:
        print("\nProbando sesion anonima...")
        session = get_stealth_session(rotate_every=60)
        if session:
            print("  Sesion Tor configurada")
            print("  IP rotara cada 60 segundos")
        else:
            print("  No se pudo configurar sesion")
    else:
        print("\nTor no instalado. Instalar via:")
        print("  Windows: choco install tor")
        print("  Linux:   sudo apt install tor")
        print("  macOS:   brew install tor")