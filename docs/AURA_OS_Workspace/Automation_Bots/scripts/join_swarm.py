#!/usr/bin/env python3
"""
join_swarm.py — AURA Swarm Auto-Join Client (Termux)
======================================================
Ejecutar en un dispositivo NUEVO con Termux para unirse automáticamente al swarm AURA.
Uso: python join_swarm.py --server <SERVER_IP>

Flujo:
  1. Detecta el dispositivo (ID único basado en MAC/android_id)
  2. Genera par de claves para handshake
  3. Envía solicitud de join al servidor AURA
  4. Recibe Node_ID, configura sandbox y túnel SSH
  5. Inicia heartbeat para mantener conexión
  6. ¡El nodo aparece como "Online" en el dashboard AURA!

Requisitos: Termux, Python 3.8+, `pkg install python openssh`
"""

import os
import sys
import json
import time
import uuid
import socket
import hashlib
import hmac
import logging
import subprocess
import threading
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

# ── Configuración de logging ──
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [JOIN-SWARM] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# ── Constantes locales ──
TERMUX_HOME = Path("/data/data/com.termux/files/home")
AURA_DIR = TERMUX_HOME / ".aura"
CONFIG_FILE = AURA_DIR / "node_config.json"
HEARTBEAT_INTERVAL = 30
PRESHARED_KEY_ENV = "AURA_JOIN_SECRET"


def get_device_id() -> str:
    """Obtiene un identificador único del dispositivo."""
    # Intentar usar el Android ID (disponible en Termux)
    try:
        result = subprocess.run(
            ["settings", "get", "secure", "android_id"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()[:16]
    except Exception:
        pass

    # Fallback: dirección MAC
    try:
        for iface in ["wlan0", "eth0", "wlan1"]:
            path = f"/sys/class/net/{iface}/address"
            if os.path.exists(path):
                with open(path) as f:
                    mac = f.read().strip()
                    if mac and mac != "00:00:00:00:00:00":
                        return mac.replace(":", "")[:12]
    except Exception:
        pass

    # Último fallback: UUID basado en hostname + /etc
    try:
        raw = socket.gethostname() + str(os.stat('/etc').st_mtime)
        return hashlib.md5(raw.encode()).hexdigest()[:16]
    except Exception:
        return str(uuid.uuid4())[:16]


def get_node_name() -> str:
    """Obtiene un nombre descriptivo para el nodo."""
    hostname = socket.gethostname()
    try:
        import android
        model = android.serial
        if model:
            return f"{hostname}-{model[:8]}"
    except Exception:
        pass
    return hostname[:16]


def get_capabilities() -> list:
    """Detecta capacidades del dispositivo."""
    caps = ["basic"]
    
    # Verificar python packages
    try:
        import requests; caps.append("http")
    except: pass
    try:
        import whois; caps.append("osint")
    except: pass
    try:
        import socks; caps.append("proxy")
    except: pass
    
    # Verificar binarios
    for binary, cap in [("nmap", "scan"), ("tcpdump", "sniff"),
                        ("privoxy", "proxy"), ("git", "dev")]:
        if subprocess.run(["which", binary], capture_output=True).returncode == 0:
            caps.append(cap)
    
    return list(set(caps))


def compute_signature(device_id: str, node_name: str, public_key: str,
                      secret: str) -> str:
    """Calcula la firma HMAC para autenticación."""
    message = f"{device_id}:{node_name}:{public_key}"
    return hmac.new(
        secret.encode(), message.encode(), hashlib.sha256
    ).hexdigest()


def generate_key_pair() -> tuple:
    """Genera un par de claves para el handshake."""
    import secrets
    private_key = secrets.token_hex(32)
    public_key = hashlib.sha256(private_key.encode()).hexdigest()
    return private_key, public_key


def setup_ssh_keys():
    """Configura llaves SSH para el túnel inverso."""
    key_file = Path.home() / ".ssh" / "id_ed25519"
    if not key_file.exists():
        logger.info("Generando llave SSH...")
        subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-f", str(key_file),
             "-N", "", "-q"],
            capture_output=True, timeout=10
        )
    
    pub_key = key_file.with_suffix(".pub").read_text().strip()
    return pub_key


def install_dependencies():
    """Instala dependencias necesarias en Termux."""
    logger.info("Verificando dependencias...")
    
    packages = ["python", "openssh", "git"]
    for pkg in packages:
        result = subprocess.run(
            ["pkg", "install", "-y", pkg],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            logger.info(f"  ✓ {pkg}")
        else:
            logger.warning(f"  ⚠️ {pkg}: {result.stderr[:50]}")

    # Dependencias Python
    pip_packages = ["requests"]
    for pkg in pip_packages:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", pkg, "-q"],
            capture_output=True, timeout=30
        )


def run_heartbeat(config: Dict, running: threading.Event):
    """Mantiene el heartbeat hacia el servidor AURA."""
    node_id = config["node_id"]
    api_url = config["config"]["api_url"]
    
    while not running.is_set():
        try:
            payload = {
                "node_id": node_id,
                "status": "online",
                "timestamp": datetime.now().isoformat(),
                "load": os.cpu_count() or 1
            }
            
            response = requests.post(
                f"{api_url}/api/swarm/heartbeat",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.debug(f"Heartbeat enviado — {node_id}")
            else:
                logger.warning(f"Heartbeat falló: HTTP {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            logger.warning("Heartbeat: servidor no reachable")
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
        
        running.wait(HEARTBEAT_INTERVAL)


def join_swarm(server_ip: str, secret: str = None) -> bool:
    """
    Ejecuta el protocolo de join completo.
    1. Detecta dispositivo
    2. Genera claves
    3. Envía handshake
    4. Recibe configuración
    5. Inicia heartbeat
    """
    logger.info("=" * 50)
    logger.info("  AURA SWARM AUTO-JOIN")
    logger.info("=" * 50)
    logger.info(f"  Servidor: {server_ip}")
    logger.info()

    # ── Paso 1: Detectar dispositivo ──
    device_id = get_device_id()
    node_name = get_node_name()
    capabilities = get_capabilities()
    logger.info(f"  Dispositivo: {node_name}")
    logger.info(f"  Device ID:   {device_id}")
    logger.info(f"  Capacidades: {', '.join(capabilities)}")
    logger.info()

    # ── Paso 2: Generar claves ──
    private_key, public_key = generate_key_pair()
    pub_ssh = setup_ssh_keys()
    logger.info("  ✓ Claves generadas")

    # ── Paso 3: Enviar handshake ──
    preshared = secret or os.environ.get(PRESHARED_KEY_ENV, "")
    if not preshared:
        logger.warning("  ⚠️ Sin PRESHARED_KEY. Usando modo insecure.")
    
    signature = compute_signature(device_id, node_name, public_key, preshared or "insecure-default")
    
    payload = {
        "device_id": device_id,
        "node_name": node_name,
        "signature": signature,
        "public_key": public_key,
        "public_ssh_key": pub_ssh,
        "capabilities": capabilities,
        "termux_version": subprocess.run(
            ["pkg", "--version"], capture_output=True, text=True
        ).stdout.strip()[:20],
        "local_ip": socket.gethostbyname(socket.gethostname()),
        "timestamp": datetime.now().isoformat()
    }
    
    logger.info("  Enviando handshake...")
    
    try:
        response = requests.post(
            f"http://{server_ip}:5000/api/swarm/join",
            json=payload,
            timeout=30
        )
        
        if response.status_code != 200:
            logger.error(f"  ❌ Handshake rechazado: {response.json().get('reason', '?')}")
            return False
        
        result = response.json()
        
        if result.get("status") != "accepted":
            logger.error(f"  ❌ Handshake {result.get('status')}: {result.get('reason', '?')}")
            return False
        
        # ── Paso 4: Guardar configuración ──
        config = {
            "node_id": result["node_id"],
            "server_ip": result["server_ip"],
            "server_port": result["server_port"],
            "ssh_port": result["ssh_port"],
            "private_key": private_key,
            "config": result["config"],
            "joined_at": datetime.now().isoformat()
        }
        
        AURA_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"  ✅ NODO ACEPTADO: {config['node_id']}")
        logger.info(f"  🆔 Node ID:   {config['node_id']}")
        logger.info(f"  🌐 Servidor:  {result['server_ip']}:{result['server_port']}")
        logger.info(f"  🔌 SSH Port:  {config['ssh_port']}")
        logger.info(f"  📁 Sandbox:   {result.get('sandbox_path', 'N/A')}")
        logger.info()
        
        # ── Paso 5: Iniciar heartbeat ──
        running = threading.Event()
        heartbeat_thread = threading.Thread(
            target=run_heartbeat, args=(config, running), daemon=True
        )
        heartbeat_thread.start()
        
        logger.info("  💓 Heartbeat iniciado (cada 30s)")
        logger.info()
        logger.info("  🟢 NODO ONLINE — Visible en dashboard AURA")
        logger.info(f"     http://{server_ip}:5000")
        logger.info()
        logger.info("  Presiona Ctrl+C para salir")
        logger.info("  (El nodo seguirá registrado en el servidor)")
        
        # Mantener vivo
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("  Saliendo... (nodo sigue registrado)")
            running.set()
        
        return True
        
    except requests.exceptions.ConnectionError:
        logger.error(f"  ❌ No se pudo conectar a {server_ip}:5000")
        logger.error("     Verifica: (1) ¿El servidor AURA está corriendo?")
        logger.error("     (2) ¿Estás en la misma red?")
        logger.error("     (3) Prueba: curl http://{server_ip}:5000/api/status")
        return False
    except requests.exceptions.Timeout:
        logger.error("  ❌ Timeout en handshake (30s)")
        return False
    except Exception as e:
        logger.error(f"  ❌ Error: {e}")
        return False


# ─── Punto de entrada ───
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="AURA Swarm Auto-Join — Une este dispositivo al swarm AURA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python join_swarm.py --server 192.168.1.100
  python join_swarm.py --server 192.168.1.100 --secret mi-clave-secreta
  python join_swarm.py --server mi-servidor.com --no-deps
        """
    )
    parser.add_argument("--server", required=True, help="IP del servidor AURA central")
    parser.add_argument("--secret", help="Clave pre-compartida (opcional, también vía env AURA_JOIN_SECRET)")
    parser.add_argument("--no-deps", action="store_true", help="No instalar dependencias")
    parser.add_argument("--show-config", action="store_true", help="Mostrar configuración actual y salir")
    args = parser.parse_args()
    
    if args.show_config:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE) as f:
                print(json.dumps(json.load(f), indent=2))
        else:
            print("No configurado. Usa --server para unirte al swarm.")
        sys.exit(0)
    
    # Instalar dependencias
    if not args.no_deps:
        install_dependencies()
    
    # Unirse al swarm
    success = join_swarm(args.server, args.secret)
    sys.exit(0 if success else 1)