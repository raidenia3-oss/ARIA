"""
Shadow-Core Network Stealth — Deteccion de Tor y Enrutamiento SOCKS5
Verifica la disponibilidad de Tor en el sistema operativo y
proporciona un proxy SOCKS5 para que los nodos de recoleccion
OSINT realicen consultas anonimas.
"""
import os
import sys
import logging
import platform
import subprocess
import socket
import time
from typing import Optional, Tuple, Dict

logging.basicConfig(level=logging.INFO, format='%(asctime)s [Stealth] %(levelname)s %(message)s')
logger = logging.getLogger('stealth')

# ── Configuracion por defecto ──
DEFAULT_SOCKS_PORT = 9050
DEFAULT_CONTROL_PORT = 9051
DEFAULT_TOR_PATHS = {
    'Windows': [
        r'C:\Program Files\Tor Browser\Browser\TorBrowser\Tor\tor.exe',
        r'C:\Program Files (x86)\Tor Browser\Browser\TorBrowser\Tor\tor.exe',
        r'C:\Tools\tor\tor.exe',
        os.path.expanduser('~/AppData/Local/Tor Browser/Browser/TorBrowser/Tor/tor.exe'),
    ],
    'Linux': [
        '/usr/bin/tor',
        '/usr/local/bin/tor',
        '/opt/tor/bin/tor',
        os.path.expanduser('~/.local/bin/tor'),
    ],
    'Darwin': [
        '/opt/homebrew/bin/tor',
        '/usr/local/bin/tor',
        '/Applications/Tor Browser.app/Contents/MacOS/Tor/tor',
    ]
}


class TorStatus:
    """Resultado de verificacion de Tor."""
    AVAILABLE = 'available'
    NOT_INSTALLED = 'not_installed'
    INSTALLED_NOT_RUNNING = 'installed_not_running'
    RUNNING = 'running'


class TorStealth:
    """
    Modulo principal de enrutamiento Stealth/Tor.
    Detecta binarios de Tor, verifica si hay daemon activo,
    y permite configurar sesiones con proxies SOCKS5.
    """

    def __init__(self, socks_port: int = DEFAULT_SOCKS_PORT,
                 control_port: int = DEFAULT_CONTROL_PORT):
        self.socks_port = socks_port
        self.control_port = control_port
        self.tor_binary_path: Optional[str] = None
        self.system_os = platform.system()

    def find_tor_binary(self) -> Optional[str]:
        """Busca el binario de Tor en el sistema."""
        # Intentar via `which` o `where`
        try:
            result = subprocess.run(
                ['where' if self.system_os == 'Windows' else 'which', 'tor'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                path = result.stdout.strip().split('\n')[0]
                logger.info("Tor encontrado via PATH: %s", path)
                return path
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Buscar en rutas conocidas segun SO
        candidates = DEFAULT_TOR_PATHS.get(self.system_os, [])
        for candidate in candidates:
            if os.path.isfile(candidate):
                logger.info("Tor encontrado en: %s", candidate)
                return candidate

        logger.warning("Tor no encontrado en el sistema")
        return None

    def is_tor_running(self, host: str = '127.0.0.1') -> bool:
        """Verifica si el daemon de Tor esta escuchando en SOCKS5."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, self.socks_port))
            sock.close()
            return result == 0
        except Exception as e:
            logger.debug("Error al verificar puerto Tor: %s", e)
            return False

    def is_tor_reachable(self, host: str = '127.0.0.1', timeout: int = 10) -> Tuple[bool, Optional[str]]:
        """
        Intenta verificar que el proxy SOCKS de Tor esta respondiendo.
        Retorna (ok, ip_externa_anonima_o_None).
        """
        if not self.is_tor_running(host):
            return False, None

        try:
            import socks  # PySocks
            original_socket = socket.socket
            socks.set_default_proxy(socks.SOCKS5, host, self.socks_port)
            socket.socket = socks.socksocket

            try:
                # Hacer peticion via SOCKS5 a un servicio que devuelve IP
                import urllib.request
                req = urllib.request.Request('https://api.ipify.org?format=json')
                req.add_header('User-Agent', 'AURA-Stealth/1.0')
                response = urllib.request.urlopen(req, timeout=timeout)
                data = response.read().decode('utf-8')
                logger.info("Conexion via Tor exitosa: %s", data)
                return True, data
            finally:
                socket.socket = original_socket
        except ImportError:
            logger.warning("PySocks no instalado. Ejecuta: pip install PySocks requests[socks]")
            return True, None
        except Exception as e:
            logger.error("Error al verificar Tor: %s", e)
            return False, None

    def check_status(self) -> Dict:
        """Verificacion completa de Tor."""
        binary = self.find_tor_binary()
        running = self.is_tor_running()
        status = {
            'os': self.system_os,
            'binary_found': binary is not None,
            'binary_path': binary,
            'socks_port': self.socks_port,
            'control_port': self.control_port,
            'daemon_running': running,
            'status': ''
        }

        if not binary:
            status['status'] = TorStatus.NOT_INSTALLED
        elif running:
            status['status'] = TorStatus.RUNNING
        else:
            status['status'] = TorStatus.INSTALLED_NOT_RUNNING

        return status

    def get_requests_session(self):
        """Retorna una sesion requests configurada con proxy SOCKS5 Tor."""
        try:
            import requests
            session = requests.Session()
            session.proxies = {
                'http': f'socks5h://127.0.0.1:{self.socks_port}',
                'https': f'socks5h://127.0.0.1:{self.socks_port}'
            }
            session.headers.update({
                'User-Agent': 'AURA-Stealth/1.0 (Compatible; Tor)'
            })
            return session
        except ImportError:
            logger.error("requests no disponible")
            return None

    def start_tor_daemon(self, config_path: Optional[str] = None) -> bool:
        """
        Intenta iniciar el daemon de Tor (solo si esta instalado).
        Retorna True si se inicio correctamente.
        """
        if not self.tor_binary_path:
            self.tor_binary_path = self.find_tor_binary()

        if not self.tor_binary_path:
            logger.error("No se puede iniciar Tor: binario no encontrado")
            return False

        try:
            args = [self.tor_binary_path]
            if config_path:
                args.extend(['-f', config_path])
            else:
                args.extend(['--SOCKSPort', str(self.socks_port),
                             '--ControlPort', str(self.control_port)])

            logger.info("Iniciando Tor daemon: %s", ' '.join(args))
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Esperar a que el puerto este disponible
            for _ in range(10):
                time.sleep(1)
                if self.is_tor_running():
                    logger.info("Tor daemon iniciado correctamente")
                    return True

            logger.warning("Tor no respondio despues de 10 segundos")
            return False
        except Exception as e:
            logger.error("Error al iniciar Tor: %s", e)
            return False

    def setup_environment(self) -> bool:
        """
        Configura el entorno para usar Tor. Si Tor no esta instalado,
        intenta instalarlo (Windows: chocolatey, Linux: apt/yum).
        """
        if self.find_tor_binary() is not None:
            logger.info("Tor ya esta disponible")
            return True

        logger.info("Tor no encontrado. Intentando instalar...")

        try:
            if self.system_os == 'Windows':
                cmd = 'choco install tor -y'
                logger.info("Ejecutando: %s", cmd)
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
                if result.returncode == 0:
                    return self.find_tor_binary() is not None
            elif self.system_os == 'Linux':
                for cmd in ['sudo apt-get install -y tor',
                           'sudo yum install -y tor',
                           'sudo dnf install -y tor']:
                    logger.info("Intentando: %s", cmd)
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
                    if result.returncode == 0 and self.find_tor_binary() is not None:
                        return True
            elif self.system_os == 'Darwin':
                cmd = 'brew install tor'
                logger.info("Ejecutando: %s", cmd)
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
                if result.returncode == 0 and self.find_tor_binary() is not None:
                    return True
        except Exception as e:
            logger.error("Error al instalar Tor: %s", e)
            return False

        return False


# ── Funcion de compatibilidad para integracion con OSINT Engine ──
def get_tor_session():
    """
    Retorna una sesion configurada para usar Tor, o una sesion normal
    si Tor no esta disponible.
    """
    stealth = TorStealth()
    status = stealth.check_status()

    if status['status'] == TorStatus.RUNNING:
        session = stealth.get_requests_session()
        if session:
            logger.info("Sesion Tor configurada (anonimato activado)")
            return session

    logger.warning("Tor no disponible. Usando sesion directa (sin anonimato)")
    import requests
    return requests.Session()


# ── Smoke Test ──
if __name__ == '__main__':
    print("=" * 60)
    print("AURA SHADOW-CORE STEALTH / TOR DETECTION")
    print("=" * 60)

    stealth = TorStealth()
    status = stealth.check_status()

    print("\nEstado de Tor:")
    print("  SO:                   %s", status['os'])
    print("  Binario encontrado:   %s", 'Si' if status['binary_found'] else 'No')
    if status['binary_path']:
        print("  Ruta del binario:     %s", status['binary_path'])
    print("  Daemon corriendo:     %s", 'Si' if status['daemon_running'] else 'No')
    print("  Puerto SOCKS:         %d", status['socks_port'])
    print("  Puerto Control:       %d", status['control_port'])
    print("  Estado general:       %s", status['status'])

    if status['status'] == TorStatus.RUNNING:
        print("\nVerificando anonimato via Tor...")
        ok, info = stealth.is_tor_reachable()
        if ok:
            print("  Conexion Tor:        OK")
            if info:
                print("  IP anonima:           %s", info)
        else:
            print("  Conexion Tor:        FALLO")
    elif status['status'] == TorStatus.INSTALLED_NOT_RUNNING:
        print("\nIniciando Tor daemon...")
        if stealth.start_tor_daemon():
            print("  Tor daemon: iniciado")
    elif status['status'] == TorStatus.NOT_INSTALLED:
        print("\nTor no instalado. Use setup_environment() para instalacion automatica.")