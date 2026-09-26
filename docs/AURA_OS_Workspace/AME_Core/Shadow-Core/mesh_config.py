#!/usr/bin/env python3
"""
mesh_config.py — Proxy Mesh Orchestrator for AME/AURA
======================================================
Gestiona una red de proxies distribuida donde cada nodo móvil
puede actuar como 'Exit Node' para navegación anónima y ejecución de OSINT.

Arquitectura:
  [Nodo A] ←→ [Nodo B (Exit)] ←→ Internet
       ↑            ↑
       └── Proxy Mesh (Privoxy/Dante) ──┘
       ↑
  [Gatekeeper] — Validación de tráfico

Características:
  - Configuración dinámica de upstream vía Privoxy/Dante
  - Rotación automática de IP de salida
  - Validación de tráfico con Gatekeeper
  - Health checks periódicos de nodos exit
  - Fallover automático si un exit node cae
"""

import os
import sys
import json
import time
import logging
import threading
import socket
import subprocess
import random
import re
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import yaml

# ── Configuración de logging ──
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [PROXY-MESH] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('mesh_config.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ── Constantes ──
ROOT_DIR = Path(__file__).resolve().parent.parent
AURA_CORE_DIR = ROOT_DIR / "AURA_Core"
TERMUX_HOME = "/data/data/com.termux/files/home"
PRIVOXY_CONFIG = f"{TERMUX_HOME}/.privoxy/config"
PRIVOXY_PORT = 8118
DANTE_CONFIG = f"{TERMUX_HOME}/.dante/sockd.conf"
DANTE_PORT = 1080
HEALTH_CHECK_INTERVAL = 30  # segundos
ROTATION_INTERVAL = 300     # 5 minutos
UPSTREAM_PROXY_LIST = []    # Se llena dinámicamente

# ── Tipos de nodo ──
class NodeRole(Enum):
    EXIT = "exit"        # Proporciona salida a internet
    RELAY = "relay"      # Reenvía tráfico entre nodos
    CLIENT = "client"    # Consume la salida
    HYBRID = "hybrid"    # Exit + Relay

class ProxyProtocol(Enum):
    HTTP = "http"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"

@dataclass
class MeshNode:
    id: str
    ip: str
    port: int
    role: NodeRole = NodeRole.CLIENT
    protocol: ProxyProtocol = ProxyProtocol.HTTP
    status: str = "unknown"  # online, offline, degraded
    last_seen: float = 0.0
    latency: float = 0.0     # ms
    bandwidth: float = 0.0   # Mbps
    score: float = 1.0       # 0.0 - 1.0 (fitness)
    current_upstream: Optional[str] = None
    upstream_list: List[str] = field(default_factory=list)
    auth_required: bool = False
    username: str = ""
    password: str = ""

    def is_alive(self) -> bool:
        return (time.time() - self.last_seen) < HEALTH_CHECK_INTERVAL * 2

# ── Proxy Mesh Engine ──
class ProxyMeshEngine:
    def __init__(self, gatekeeper=None, config_path: str = None):
        self.nodes: Dict[str, MeshNode] = {}
        self.exit_nodes: List[str] = []  # IDs de nodos exit activos
        self.lock = threading.Lock()
        self.running = False
        self.current_exit_index = 0
        self.gatekeeper = gatekeeper  # Referencia al Gatekeeper de AURA
        self.config_path = config_path or str(ROOT_DIR / "Shadow-Core" / "mesh_config.yaml")
        self.load_config()

        # Configuración de upstream (lista de proxies externos)
        self.upstream_pool: List[Dict] = []
        self.load_upstream_pool()

        # Threads
        self.health_thread = None
        self.rotation_thread = None

    def load_config(self):
        """Carga la configuración de mesh desde archivo YAML"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    cfg = yaml.safe_load(f) or {}
                logger.info(f"Configuración mesh cargada desde {self.config_path}")
            else:
                cfg = self._default_config()
                with open(self.config_path, 'w') as f:
                    yaml.dump(cfg, f, default_flow_style=False)
                logger.info(f"Configuración mesh por defecto creada en {self.config_path}")
            return cfg
        except Exception as e:
            logger.error(f"Error cargando configuración mesh: {e}")
            return self._default_config()

    def _default_config(self) -> Dict:
        return {
            "mesh": {
                "enabled": True,
                "name": "AURA Proxy Mesh",
                "version": "1.0",
                "protocol": "http",
                "default_timeout": 30,
                "max_hops": 3,
                "gatekeeper_validation": True
            },
            "privoxy": {
                "enabled": True,
                "port": PRIVOXY_PORT,
                "config_path": PRIVOXY_CONFIG,
                "listen_address": "0.0.0.0"
            },
            "dante": {
                "enabled": True,
                "port": DANTE_PORT,
                "config_path": DANTE_CONFIG,
                "listen_address": "0.0.0.0"
            },
            "rotation": {
                "enabled": True,
                "interval_seconds": ROTATION_INTERVAL,
                "strategy": "round_robin",  # round_robin, random, latency, score
                "health_check_before_rotation": True
            },
            "upstream": {
                "provider": "dynamic",  # tor, socks5_list, http_list, dynamic
                "pool_size": 10,
                "refresh_interval": 600,
                "sources": [
                    "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt",
                    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt"
                ]
            },
            "gatekeeper": {
                "enabled": True,
                "endpoint": "http://127.0.0.1:5000/api/gatekeeper/validate",
                "timeout": 10,
                "require_auth": True,
                "allowed_actions": ["http", "osint", "recon", "exploit"]
            },
            "termux": {
                "privoxy_binary": f"{TERMUX_HOME}/../usr/bin/privoxy",
                "dante_binary": f"{TERMUX_HOME}/../usr/bin/sockd",
                "auto_install": False,
                "config_dir": f"{TERMUX_HOME}/.aura/mesh"
            }
        }

    def load_upstream_pool(self):
        """Carga la pool de proxies upstream desde fuentes externas"""
        try:
            config = self.load_config()
            sources = config.get("upstream", {}).get("sources", [])
            for source_url in sources:
                try:
                    response = requests.get(source_url, timeout=10)
                    if response.status_code == 200:
                        proxies = response.text.strip().split('\n')
                        for proxy in proxies[:50]:  # Máximo 50 por fuente
                            proxy = proxy.strip()
                            if ':' in proxy:
                                host, port = proxy.split(':')
                                entry = {
                                    "host": host,
                                    "port": int(port),
                                    "protocol": "socks5" if "socks" in source_url else "http",
                                    "source": source_url,
                                    "added": time.time()
                                }
                                self.upstream_pool.append(entry)
                        logger.info(f"Pool cargada: {len(proxies)} proxies desde {source_url}")
                except Exception as e:
                    logger.warning(f"No se pudo cargar proxy list desde {source_url}: {e}")

            # Si no hay proxies externos, crear pool simulada
            if not self.upstream_pool:
                self._create_fallback_pool()
            logger.info(f"Upstream pool: {len(self.upstream_pool)} proxies disponibles")
        except Exception as e:
            logger.error(f"Error cargando upstream pool: {e}")
            self._create_fallback_pool()

    def _create_fallback_pool(self):
        """Crea pool de proxies simulada para demostración/fallback"""
        fallback_proxies = [
            {"host": "127.0.0.1", "port": 9050, "protocol": "socks5", "source": "tor"},
            {"host": "127.0.0.1", "port": 8118, "protocol": "http", "source": "privoxy"},
        ]
        self.upstream_pool = fallback_proxies
        logger.info(f"Pool de fallback creada: {len(fallback_proxies)} proxies")

    def register_node(self, node_id: str, ip: str, port: int,
                      role: str = "client", protocol: str = "http",
                      auth_required: bool = False) -> MeshNode:
        """Registra un nodo en el mesh"""
        with self.lock:
            node = MeshNode(
                id=node_id,
                ip=ip,
                port=port,
                role=NodeRole(role),
                protocol=ProxyProtocol(protocol),
                status="online",
                last_seen=time.time(),
                auth_required=auth_required
            )
            self.nodes[node_id] = node

            if node.role in [NodeRole.EXIT, NodeRole.HYBRID]:
                self.exit_nodes.append(node_id)

            logger.info(f"Nodo registrado en mesh: {node_id} ({role}) en {ip}:{port}")
            return node

    def unregister_node(self, node_id: str):
        """Elimina un nodo del mesh"""
        with self.lock:
            if node_id in self.nodes:
                del self.nodes[node_id]
            if node_id in self.exit_nodes:
                self.exit_nodes.remove(node_id)
            logger.info(f"Nodo eliminado del mesh: {node_id}")

    def select_exit_node(self, strategy: str = "round_robin") -> Optional[MeshNode]:
        """Selecciona un nodo exit óptimo según la estrategia"""
        with self.lock:
            available = [
                self.nodes[eid] for eid in self.exit_nodes
                if eid in self.nodes and self.nodes[eid].is_alive()
            ]
            if not available:
                logger.warning("No hay nodos exit disponibles")
                return None

            if strategy == "random":
                return random.choice(available)
            elif strategy == "latency":
                return min(available, key=lambda n: n.latency)
            elif strategy == "score":
                return max(available, key=lambda n: n.score)
            else:  # round_robin
                self.current_exit_index = (self.current_exit_index + 1) % len(available)
                return available[self.current_exit_index]

    def get_upstream_proxy(self) -> Optional[Dict]:
        """Obtiene un proxy upstream aleatorio de la pool"""
        if not self.upstream_pool:
            self.load_upstream_pool()
            return None
        return random.choice(self.upstream_pool)

    def rotate_proxy(self) -> bool:
        """Rota la IP de salida seleccionando nuevo exit node y upstream"""
        try:
            with self.lock:
                # Seleccionar nuevo exit node
                exit_node = self.select_exit_node()
                if not exit_node:
                    return False

                # Seleccionar nuevo upstream
                upstream = self.get_upstream_proxy()

                # Actualizar configuración de Privoxy/Dante
                if self._update_proxy_config(exit_node, upstream):
                    # Marcar nodo actualizado
                    exit_node.current_upstream = f"{upstream['host']}:{upstream['port']}" if upstream else None
                    logger.info(f"Proxy rotado: Exit={exit_node.id}, Upstream={exit_node.current_upstream}")
                    return True
            return False
        except Exception as e:
            logger.error(f"Error en rotación de proxy: {e}")
            return False

    def _update_proxy_config(self, exit_node: MeshNode, upstream: Optional[Dict]) -> bool:
        """Actualiza la configuración de Privoxy/Dante para usar el upstream"""
        try:
            # Actualizar configuración de Privoxy
            privoxy_cfg = f"""
# ============================================
# AURA Proxy Mesh — Privoxy Configuration
# Generado por mesh_config.py
# Exit Node: {exit_node.id}
# Upstream: {upstream['host']}:{upstream['port'] if upstream else 'DIRECT'}
# Timestamp: {datetime.now().isoformat()}
# ============================================

# Dirección y puerto de escucha
listen-address  0.0.0.0:{PRIVOXY_PORT}
toggle          1
enable-remote-toggle  0
enable-remote-http-toggle  0
enable-edit-actions  0
enforce-blocks  0
buffer-limit    4096
forwarded-connect-retries  2
accept-intercepted-requests 0
allow-cgi-request-crunching 0

# Timeout de conexión (30s para túneles)
socket-timeout  30
connect-timeout 30

# Logging
logfile  {TERMUX_HOME}/.privoxy/logfile

# Upstream proxy
"""
            if upstream:
                if upstream['protocol'] == 'socks5':
                    privoxy_cfg += f"forward-socks5t   /   {upstream['host']}:{upstream['port']} .\n"
                elif upstream['protocol'] == 'http':
                    privoxy_cfg += f"forward   /   {upstream['host']}:{upstream['port']}\n"
            else:
                privoxy_cfg += "forward   /   .\n"  # Conexión directa

            # Configuración de forward para peticiones específicas
            privoxy_cfg += """
# No forward para direcciones locales
forward   127.0.0.0/8      .
forward   10.0.0.0/8       .
forward   172.16.0.0/12    .
forward   192.168.0.0/16   .

# Forward para todo lo demás
forward   /   .
"""

            # Guardar configuración
            os.makedirs(os.path.dirname(PRIVOXY_CONFIG), exist_ok=True)
            with open(PRIVOXY_CONFIG, 'w') as f:
                f.write(privoxy_cfg)

            # Verificar sintaxis
            result = subprocess.run(
                ['privoxy', '--config-test', PRIVOXY_CONFIG],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                logger.info("Configuración de Privoxy actualizada")
                return True
            else:
                logger.error(f"Error en configuración de Privoxy: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error actualizando configuración de proxy: {e}")
            return False

    def health_check(self) -> Dict[str, str]:
        """Verifica la salud de todos los nodos en el mesh"""
        results = {}
        with self.lock:
            for node_id, node in list(self.nodes.items()):
                try:
                    # Probar conexión al nodo
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(5)
                    start = time.time()
                    result = sock.connect_ex((node.ip, node.port))
                    latency = (time.time() - start) * 1000  # ms
                    sock.close()

                    if result == 0:
                        node.status = "online"
                        node.latency = latency
                        node.last_seen = time.time()
                        node.score = max(0.1, min(1.0, 1000.0 / (latency + 1)))
                        results[node_id] = "online"
                    else:
                        node.status = "offline"
                        node.score = 0.0
                        results[node_id] = f"offline (code {result})"

                except Exception as e:
                    node.status = "offline"
                    node.score = 0.0
                    results[node_id] = f"error: {str(e)[:50]}"

            # Limpiar exit nodes caídos
            self.exit_nodes = [
                eid for eid in self.exit_nodes
                if eid in self.nodes and self.nodes[eid].status == "online"
            ]

        return results

    def validate_with_gatekeeper(self, action: str, target: str, data: Dict) -> bool:
        """Valida una acción con el Gatekeeper antes de ejecutarla vía proxy mesh"""
        if not self.gatekeeper:
            logger.warning("Gatekeeper no disponible, omitiendo validación")
            return True

        try:
            validation = self.gatekeeper.validate_action(
                action_type=f"proxy_mesh_{action}",
                target=target,
                severity="medium",
                source="proxy_mesh",
                metadata={
                    "data": data,
                    "timestamp": datetime.now().isoformat()
                }
            )
            if validation.get('approved', False):
                logger.info(f"Gatekeeper aprobó: {action} → {target}")
                return True
            else:
                logger.warning(f"Gatekeeper rechazó: {action} → {target}: {validation.get('message', '')}")
                return False
        except Exception as e:
            logger.error(f"Error validando con Gatekeeper: {e}")
            return False

    def execute_via_mesh(self, action: str, target: str, data: Dict = None) -> Dict:
        """Ejecuta una acción a través del proxy mesh"""
        # Validar con Gatekeeper primero
        if not self.validate_with_gatekeeper(action, target, data or {}):
            return {"status": "rejected", "message": "Acción rechazada por Gatekeeper"}

        # Seleccionar exit node
        exit_node = self.select_exit_node()
        if not exit_node:
            return {"status": "failed", "message": "No hay exit nodes disponibles"}

        # Construir proxy URL
        proxy_url = f"{exit_node.protocol.value}://{exit_node.ip}:{exit_node.port}"

        try:
            # Ejecutar la acción a través del proxy
            proxies = {
                "http": proxy_url,
                "https": proxy_url
            }

            if action == "http":
                response = requests.get(
                    target,
                    proxies=proxies,
                    timeout=30,
                    headers={
                        "User-Agent": "AURA-ProxyMesh/1.0",
                        "X-Exit-Node": exit_node.id
                    }
                )
                return {
                    "status": "completed",
                    "exit_node": exit_node.id,
                    "status_code": response.status_code,
                    "content_length": len(response.content),
                    "proxy": proxy_url
                }

            elif action == "osint":
                # Canalizar herramienta OSINT a través del proxy
                # (La herramienta debe soportar proxy HTTP)
                return self._run_osint_through_mesh(target, data or {}, exit_node, proxy_url)

            elif action == "dns":
                # Resolución DNS a través del proxy
                import dns.resolver
                resolver = dns.resolver.Resolver()
                resolver.nameservers = [exit_node.ip]
                answers = resolver.resolve(target, 'A')
                return {
                    "status": "completed",
                    "exit_node": exit_node.id,
                    "resolved_ips": [str(r) for r in answers]
                }

            else:
                return {"status": "failed", "message": f"Acción no soportada: {action}"}

        except requests.exceptions.Timeout:
            return {"status": "timeout", "exit_node": exit_node.id, "message": "Timeout del proxy mesh"}
        except requests.exceptions.ConnectionError as e:
            return {"status": "failed", "exit_node": exit_node.id, "message": str(e)[:100]}
        except Exception as e:
            return {"status": "error", "exit_node": exit_node.id, "message": str(e)[:100]}

    def _run_osint_through_mesh(self, target: str, params: Dict,
                                 exit_node: MeshNode, proxy_url: str) -> Dict:
        """Ejecuta OSINT canalizado a través del proxy mesh"""
        try:
            # Configurar environment con proxy
            env = os.environ.copy()
            env['HTTP_PROXY'] = proxy_url
            env['HTTPS_PROXY'] = proxy_url

            tool = params.get('tool', 'whois')

            if tool == 'whois':
                import whois
                result = whois.whois(target)
                return {
                    "status": "completed",
                    "exit_node": exit_node.id,
                    "tool": "whois",
                    "target": target,
                    "result": str(result)[:1000]
                }

            elif tool == 'nslookup':
                result = subprocess.run(
                    ['nslookup', target],
                    capture_output=True, text=True, timeout=15, env=env
                )
                return {
                    "status": "completed",
                    "exit_node": exit_node.id,
                    "tool": "nslookup",
                    "target": target,
                    "stdout": result.stdout[:500],
                    "stderr": result.stderr[:500]
                }

            else:
                # Fallback: HTTP request con proxy
                proxies = {"http": proxy_url, "https": proxy_url}
                response = requests.get(
                    f"https://api.hackertarget.com/{tool}/?q={target}",
                    proxies=proxies, timeout=30
                )
                return {
                    "status": "completed",
                    "exit_node": exit_node.id,
                    "tool": tool,
                    "target": target,
                    "response": response.text[:1000]
                }

        except Exception as e:
            return {"status": "error", "exit_node": exit_node.id, "message": str(e)[:100]}

    def install_termux_proxy(self) -> bool:
        """Instala y configura los proxies en Termux"""
        try:
            logger.info("Instalando proxies en Termux...")

            # Instalar Privoxy
            result = subprocess.run(
                ['pkg', 'install', '-y', 'privoxy'],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode != 0:
                logger.warning(f"Privoxy no instalado: {result.stderr[:100]}")

            # Instalar Dante
            result = subprocess.run(
                ['pkg', 'install', '-y', 'dante'],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode != 0:
                logger.warning(f"Dante no instalado: {result.stderr[:100]}")

            # Crear directorios de configuración
            os.makedirs(f"{TERMUX_HOME}/.privoxy", exist_ok=True)
            os.makedirs(f"{TERMUX_HOME}/.dante", exist_ok=True)
            os.makedirs(f"{TERMUX_HOME}/.aura/mesh", exist_ok=True)

            # Configurar Privoxy
            self._update_proxy_config(
                MeshNode(id="local", ip="127.0.0.1", port=PRIVOXY_PORT, role=NodeRole.EXIT),
                self.get_upstream_proxy()
            )

            # Configurar Dante (SOCKS5)
            dante_config = f"""
# Configuración Dante SOCKS5 para AURA Proxy Mesh
# Exit Node local: 127.0.0.1:{DANTE_PORT}

internal: 0.0.0.0 port = {DANTE_PORT}
external: wlan0

method: username none
user.privileged: root
user.unprivileged: nobody

client pass {{
    from: 0.0.0.0/0 to: 0.0.0.0/0
    log: error connect disconnect
}}

socks pass {{
    from: 0.0.0.0/0 to: 0.0.0.0/0
    command: bind connect udpassociate
    log: error connect disconnect
    socksmethod: username
}}
"""
            with open(DANTE_CONFIG, 'w') as f:
                f.write(dante_config)

            logger.info("Configuración de proxies Termux completada")
            return True

        except Exception as e:
            logger.error(f"Error instalando proxies Termux: {e}")
            return False

    def _health_check_loop(self):
        """Bucle de health check periódico"""
        while self.running:
            try:
                results = self.health_check()
                offline = [n for n, s in results.items() if s != "online"]
                if offline:
                    logger.info(f"Nodos offline: {offline}")

                    # Si hay pocos exit nodes, intentar reconfigurar
                    if len(self.exit_nodes) < 2:
                        logger.warning("Pocos exit nodes disponibles, intentando reconfigurar...")
                        self.rotate_proxy()

            except Exception as e:
                logger.error(f"Error en health check: {e}")
            time.sleep(HEALTH_CHECK_INTERVAL)

    def _rotation_loop(self):
        """Bucle de rotación periódica de IP de salida"""
        while self.running:
            try:
                config = self.load_config()
                if config.get("rotation", {}).get("enabled", True):
                    logger.info("Ejecutando rotación periódica de proxy...")
                    self.rotate_proxy()
            except Exception as e:
                logger.error(f"Error en rotación: {e}")
            time.sleep(ROTATION_INTERVAL)

    def start(self):
        """Inicia el motor Proxy Mesh"""
        if self.running:
            logger.warning("Proxy Mesh ya está en ejecución")
            return

        self.running = True

        # Iniciar health checks
        self.health_thread = threading.Thread(target=self._health_check_loop, daemon=True)
        self.health_thread.start()

        # Iniciar rotación periódica
        self.rotation_thread = threading.Thread(target=self._rotation_loop, daemon=True)
        self.rotation_thread.start()

        # Configurar Privoxy localmente
        self._update_proxy_config(
            MeshNode(id="local", ip="127.0.0.1", port=PRIVOXY_PORT, role=NodeRole.EXIT),
            self.get_upstream_proxy()
        )

        logger.info(f"Proxy Mesh iniciado: {len(self.exit_nodes)} exit nodes, {len(self.nodes)} total nodes")
        return True

    def stop(self):
        """Detiene el motor Proxy Mesh"""
        self.running = False
        if self.health_thread:
            self.health_thread.join(timeout=5)
        if self.rotation_thread:
            self.rotation_thread.join(timeout=5)
        logger.info("Proxy Mesh detenido")

    def get_status(self) -> Dict:
        """Obtiene el estado actual del mesh"""
        return {
            "enabled": self.running,
            "total_nodes": len(self.nodes),
            "exit_nodes": len(self.exit_nodes),
            "online_exits": sum(1 for eid in self.exit_nodes if eid in self.nodes and self.nodes[eid].status == "online"),
            "upstream_pool_size": len(self.upstream_pool),
            "current_exit": self.current_exit_index,
            "nodes": {nid: {
                "ip": n.ip,
                "port": n.port,
                "role": n.role.value,
                "status": n.status,
                "latency_ms": round(n.latency, 1),
                "score": round(n.score, 2),
                "upstream": n.current_upstream
            } for nid, n in self.nodes.items()}
        }


# ── Punto de entrada ──
if __name__ == "__main__":
    engine = ProxyMeshEngine()

    # Registrar algunos nodos de ejemplo
    engine.register_node("nodo-1", "192.168.1.101", 8118, "exit", "http")
    engine.register_node("nodo-2", "192.168.1.102", 8118, "exit", "http")
    engine.register_node("nodo-3", "192.168.1.103", 8118, "client", "http")
    engine.register_node("nodo-4", "192.168.1.104", 8118, "relay", "socks5")

    engine.start()

    try:
        # Probar ejecución vía mesh
        result = engine.execute_via_mesh("http", "https://httpbin.org/ip")
        print(f"Resultado: {json.dumps(result, indent=2)}")
    except KeyboardInterrupt:
        engine.stop()