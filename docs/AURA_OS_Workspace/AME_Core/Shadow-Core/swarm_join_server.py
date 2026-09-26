#!/usr/bin/env python3
"""
swarm_join_server.py — AURA Swarm Auto-Join Server
====================================================
Módulo servidor para el protocolo de Handshake automático.
Cuando un nuevo dispositivo ejecuta join_swarm.py, este servidor:
  1. Recibe el handshake con clave pública pre-compartida
  2. Valida la autenticación
  3. Asigna un Node_ID único
  4. Crea sandbox en venice_modules/<node_id>/
  5. Configura túnel SSH inverso
  6. Registra el nodo en SwarmManager + NotificationBridge
  7. Notifica a Discord "Nuevo nodo online"

Endpoint REST: POST /api/swarm/join
"""

import os
import sys
import json
import time
import uuid
import socket
import logging
import threading
import subprocess
import hashlib
import hmac
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple
from flask import Flask, request, jsonify
import requests

# ── Configuración de logging ──
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [SWARM-JOIN] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('swarm_join.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ── Constantes ──
ROOT_DIR = Path(__file__).resolve().parent.parent
AURA_CORE_DIR = ROOT_DIR / "AURA_Core"
VENICE_MODULES_DIR = ROOT_DIR / "venice_modules"
NODES_DIR = VENICE_MODULES_DIR / "nodes"
NODES_CONFIG = AURA_CORE_DIR / "nodes_config.json"
SSH_BASE_PORT = 8022
AURA_SERVER_PORT = 5000

# Clave pre-compartida para autenticación
# En producción, obtener de variable de entorno o archivo secreto
PRESHARED_KEY = os.environ.get("AURA_JOIN_SECRET", "aura-join-default-key-change-me")

# ─── Gestor de Auto-Join ───

class SwarmJoinServer:
    """
    Maneja el protocolo de handshake para nuevos nodos.
    """

    def __init__(self, notification_bridge=None, swarm_manager=None):
        self.bridge = notification_bridge
        self.swarm_manager = swarm_manager
        self.joined_nodes: Dict[str, Dict] = {}
        self.lock = threading.Lock()
        self.next_ssh_port = SSH_BASE_PORT

    def handle_join(self, handshake_data: Dict, remote_ip: str) -> Dict:
        """
        Procesa una solicitud de join desde un nuevo nodo.
        Flujo completo:
          1. Validar handshake criptográfico
          2. Generar Node_ID único
          3. Crear sandbox en venice_modules/nodes/<node_id>/
          4. Configurar túnel SSH inverso
          5. Registrar en SwarmManager
          6. Notificar a Discord/WhatsApp
        """
        logger.info(f"📩 Handshake recibido desde {remote_ip}")

        try:
            # ── Fase 1: Validar autenticación ──
            node_name = handshake_data.get("node_name", "unknown")
            device_id = handshake_data.get("device_id", "")
            signature = handshake_data.get("signature", "")
            public_key = handshake_data.get("public_key", "")
            termux_version = handshake_data.get("termux_version", "unknown")
            capabilities = handshake_data.get("capabilities", [])

            # Validar firma HMAC
            expected_sig = self._compute_signature(device_id, node_name, public_key)
            if signature != expected_sig:
                logger.warning(f"❌ Firma inválida desde {remote_ip} (device: {device_id})")
                return {
                    "status": "rejected",
                    "reason": "Invalid handshake signature. Verify PRESHARED_KEY matches."
                }

            logger.info(f"✅ Autenticación OK para {node_name} ({device_id})")

            # ── Fase 2: Generar Node_ID único ──
            node_id = self._generate_node_id(device_id)
            logger.info(f"🆔 Node_ID asignado: {node_id}")

            # ── Fase 3: Crear sandbox ──
            sandbox_path = self._create_sandbox(node_id, node_name, capabilities)
            logger.info(f"📁 Sandbox creado: {sandbox_path}")

            # ── Fase 4: Configurar túnel SSH inverso ──
            ssh_port = self._allocate_ssh_port()
            tunnel_config = self._setup_reverse_tunnel(node_id, remote_ip, ssh_port)
            logger.info(f"🔌 Túnel SSH configurado (puerto {ssh_port})")

            # ── Fase 5: Construir respuesta con todo lo necesario ──
            response = {
                "status": "accepted",
                "node_id": node_id,
                "server_ip": self._get_server_ip(),
                "server_port": AURA_SERVER_PORT,
                "ssh_port": ssh_port,
                "sandbox_path": str(sandbox_path),
                "master_public_key": self._get_master_public_key(),
                "assigned_at": datetime.now().isoformat(),
                "config": {
                    "websocket_url": f"ws://{self._get_server_ip()}:3000",
                    "api_url": f"http://{self._get_server_ip()}:{AURA_SERVER_PORT}",
                    "heartbeat_interval": 30,
                    "sync_interval": 300
                }
            }

            # ── Fase 6: Registrar en SwarmManager ──
            self._register_in_swarm(node_id, node_name, remote_ip, capabilities)

            # ── Fase 7: Notificar ──
            self._notify_join(node_id, node_name, remote_ip, capabilities)

            # Guardar en joined_nodes
            with self.lock:
                self.joined_nodes[node_id] = {
                    "node_id": node_id,
                    "node_name": node_name,
                    "device_id": device_id,
                    "ip": remote_ip,
                    "ssh_port": ssh_port,
                    "capabilities": capabilities,
                    "joined_at": datetime.now().isoformat(),
                    "last_heartbeat": datetime.now().isoformat()
                }
                self._save_nodes_config()

            logger.info(f"🎉 Nodo {node_name} ({node_id}) unido exitosamente desde {remote_ip}")
            return response

        except Exception as e:
            logger.error(f"❌ Error en handshake: {e}")
            return {"status": "error", "reason": str(e)[:200]}

    def _compute_signature(self, device_id: str, node_name: str, public_key: str) -> str:
        """Calcula la firma HMAC esperada."""
        message = f"{device_id}:{node_name}:{public_key}"
        return hmac.new(
            PRESHARED_KEY.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

    def _generate_node_id(self, device_id: str) -> str:
        """Genera un Node_ID único basado en device_id + hash."""
        raw = f"{device_id}:{uuid.uuid4()}:{time.time()}"
        hash_id = hashlib.sha256(raw.encode()).hexdigest()[:12]
        return f"node-{hash_id}"

    def _create_sandbox(self, node_id: str, node_name: str, capabilities: List[str]) -> Path:
        """Crea el sandbox del nodo en venice_modules/nodes/<node_id>/"""
        sandbox = NODES_DIR / node_id
        sandbox.mkdir(parents=True, exist_ok=True)

        # Estructura del sandbox
        dirs = ["tasks", "results", "logs", "cache", "config"]
        for d in dirs:
            (sandbox / d).mkdir(parents=True, exist_ok=True)

        # Archivo de metadatos del nodo
        meta = {
            "node_id": node_id,
            "node_name": node_name,
            "created_at": datetime.now().isoformat(),
            "capabilities": capabilities,
            "status": "active"
        }
        with open(sandbox / "node.json", 'w') as f:
            json.dump(meta, f, indent=2)

        # Configuración por defecto
        default_config = {
            "node_id": node_id,
            "data_lakehouse": {"enabled": True, "sync_interval": 300},
            "telemetry": {"enabled": True, "interval": 60},
            "osint": {"enabled": "venice" in capabilities, "timeout": 600}
        }
        with open(sandbox / "config" / "default.json", 'w') as f:
            json.dump(default_config, f, indent=2)

        logger.info(f"Sandbox creado para {node_id}: {sandbox}")
        return sandbox

    def _allocate_ssh_port(self) -> int:
        """Asigna un puerto SSH único para el túnel inverso."""
        with self.lock:
            port = self.next_ssh_port
            self.next_ssh_port += 1
            return port

    def _setup_reverse_tunnel(self, node_id: str, node_ip: str, ssh_port: int) -> Dict:
        """
        Configura la entrada del túnel SSH inverso en el servidor.
        En producción ejecuta: ssh -R <port>:localhost:22 user@server
        """
        config = {
            "node_id": node_id,
            "local_port": ssh_port,
            "remote_host": node_ip,
            "remote_port": 22,
            "type": "reverse",
            "config_path": str(NODES_DIR / node_id / "config" / "ssh_tunnel.json")
        }

        # Guardar configuración del túnel
        tunnel_file = NODES_DIR / node_id / "config" / "ssh_tunnel.json"
        with open(tunnel_file, 'w') as f:
            json.dump(config, f, indent=2)

        logger.info(f"Túnel SSH inverso configurado: :{ssh_port} → {node_ip}:22")
        return config

    def _register_in_swarm(self, node_id: str, node_name: str, ip: str, capabilities: List[str]):
        """Registra el nodo en el SwarmManager."""
        if self.swarm_manager:
            try:
                self.swarm_manager.register_node(
                    node_id=node_id,
                    ip=ip,
                    port=8118,
                    role="exit" if "proxy" in capabilities else "client",
                    protocol="http"
                )
                logger.info(f"Nodo {node_id} registrado en SwarmManager")
            except Exception as e:
                logger.warning(f"Error registrando en SwarmManager: {e}")

    def _notify_join(self, node_id: str, node_name: str, ip: str, capabilities: List[str]):
        """Notifica la unión del nuevo nodo a Discord/WhatsApp."""
        if self.bridge:
            try:
                self.bridge.notify_node_joined(
                    node_id=node_id,
                    ip=ip,
                    role="mobile"
                )
                # Mensaje adicional con detalles
                caps_str = ", ".join(capabilities[:5]) if capabilities else "básico"
                logger.info(f"Notificación de join enviada para {node_name}")
            except Exception as e:
                logger.warning(f"Error notificando join: {e}")

    def _get_server_ip(self) -> str:
        """Obtiene la IP del servidor para enviar al nodo."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def _get_master_public_key(self) -> str:
        """Obtiene la clave pública del servidor maestro."""
        key_file = ROOT_DIR / "master_public_key.pem"
        if key_file.exists():
            return key_file.read_text().strip()
        # Generar clave por defecto si no existe
        default_key = "AURA-MASTER-KEY-v1:default-public-key"
        key_file.write_text(default_key)
        return default_key

    def _save_nodes_config(self):
        """Guarda la configuración de nodos unidos."""
        try:
            data = {
                "last_updated": datetime.now().isoformat(),
                "nodes": list(self.joined_nodes.values())
            }
            NODES_CONFIG.parent.mkdir(parents=True, exist_ok=True)
            with open(NODES_CONFIG, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error guardando nodes_config: {e}")

    def get_joined_nodes(self) -> List[Dict]:
        return list(self.joined_nodes.values())

    def get_node_count(self) -> int:
        return len(self.joined_nodes)


# ─── Endpoint Flask ───

def create_join_endpoint(app: Flask, join_server: SwarmJoinServer):
    """Crea el endpoint REST para el handshake en la app Flask existente."""

    @app.route('/api/swarm/join', methods=['POST'])
    def swarm_join():
        """Endpoint de handshake para nuevos nodos."""
        data = request.get_json(force=True)
        remote_ip = request.remote_addr or "unknown"

        # Validar datos mínimos
        if not data or not data.get("device_id"):
            return jsonify({"status": "rejected", "reason": "device_id required"}), 400

        result = join_server.handle_join(data, remote_ip)
        status_code = 200 if result.get("status") == "accepted" else 403
        return jsonify(result), status_code

    @app.route('/api/swarm/nodes', methods=['GET'])
    def swarm_nodes():
        """Lista los nodos unidos."""
        return jsonify({
            "total": join_server.get_node_count(),
            "nodes": join_server.get_joined_nodes()
        })

    @app.route('/api/swarm/health', methods=['GET'])
    def swarm_health():
        """Health check del servidor de join."""
        return jsonify({
            "status": "online",
            "joined_nodes": join_server.get_node_count(),
            "server_time": datetime.now().isoformat()
        })

    logger.info("✅ Endpoints de Swarm Join registrados en Flask")
    return join_server


# ─── Punto de entrada independiente ───
if __name__ == "__main__":
    print("=" * 55)
    print("  AURA Swarm Join Server")
    print("  (Integrar en servidor_ame.py vía create_join_endpoint)")
    print("=" * 55)
    print()
    print(f"  PRESHARED_KEY: {PRESHARED_KEY[:20]}...")
    print(f"  NODES_DIR: {NODES_DIR}")
    print()
    print("  Para integrar en servidor_ame.py:")
    print("""
    from swarm_join_server import SwarmJoinServer, create_join_endpoint
    join_server = SwarmJoinServer(notification_bridge=bridge, swarm_manager=swarm_manager)
    create_join_endpoint(app, join_server)
    """)