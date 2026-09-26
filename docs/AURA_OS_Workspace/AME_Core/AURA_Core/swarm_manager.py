#!/usr/bin/env python3
"""
swarm_manager.py - Gestor de enjambre (Swarm) para la orquestación distribuida de tareas en AURA.
Este módulo coordina múltiples nodos móviles para ejecutar tareas de manera eficiente,
asignando trabajos según criterios como señal Wi-Fi, carga de CPU y disponibilidad de recursos.

Características:
- Consulta el estado de todos los nodos conectados.
- Asigna tareas al nodo más eficiente según criterios configurables.
- Coordina el retorno de datos consolidados.
- Proporciona una interfaz para monitorear la salud del enjambre.
- Integra con el Task Dispatcher y el Dashboard de AURA.
"""

import os
import sys
import json
import logging
import time
import threading
import subprocess
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set
import sqlite3
import hashlib
import requests
import networkx as nx
from collections import defaultdict
import math
from enum import Enum

class NodeStatus(Enum):
    """Estados posibles de un nodo en el enjambre."""
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"
    UNAVAILABLE = "unavailable"

class TaskPriority(Enum):
    """Prioridades de tareas en el enjambre."""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4

class SwarmManager:
    """Gestor de enjambre (Swarm) para la orquestación distribuida de tareas."""

    def __init__(self, config: Dict):
        self.config = config
        self.logger = self._setup_logging()
        self.db_path = config.get("db_path", "/data/data/com.termux/files/home/aura_intel.db")
        self.nodes_config_path = config.get("nodes_config_path", "nodes_config.json")
        self.task_dispatcher_config = config.get("task_dispatcher_config", {})
        self.ssh_host = config.get("ssh_host", "localhost")
        self.ssh_port = config.get("ssh_port", 8022)
        self.ssh_user = config.get("ssh_user", "user")
        self.node_heartbeat_interval = config.get("node_heartbeat_interval", 60)
        self.node_timeout = config.get("node_timeout", 120)
        self.max_concurrent_tasks = config.get("max_concurrent_tasks", 5)
        self.swarm_health_file = config.get("swarm_health_file", "/data/data/com.termux/files/home/swarm_health.json")
        self.running = False
        self.shutdown_event = threading.Event()
        self.nodes_state = {}
        self.nodes_graph = nx.Graph()
        self.task_assignment_strategy = config.get("task_assignment_strategy", "optimal")
        self.strategy_weights = config.get("strategy_weights", {
            "signal_strength": 0.4,
            "cpu_load": 0.3,
            "battery_level": 0.2,
            "distance": 0.1
        })
        self.last_heartbeat_time = {}
        self.lock = threading.Lock()
        self.health_monitor_thread = None
        self.task_coordinator_thread = None

    def _setup_logging(self):
        """Configura el logging para el Swarm Manager."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('/data/data/com.termux/files/home/swarm_manager.log'),
                logging.StreamHandler()
            ]
        )
        logger = logging.getLogger("SwarmManager")
        logger.setLevel(logging.INFO)
        return logger

    def _load_nodes_config(self) -> Dict:
        """Carga la configuración de nodos desde el archivo JSON."""
        try:
            with open(self.nodes_config_path, 'r') as f:
                nodes_data = json.load(f)
            return nodes_data
        except Exception as e:
            self.logger.error(f"Error al cargar configuración de nodos: {str(e)}")
            return {}

    def _save_swarm_health(self, swarm_health: Dict):
        """Guarda el estado de salud del enjambre en un archivo JSON."""
        try:
            with open(self.swarm_health_file, 'w') as f:
                json.dump(swarm_health, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error al guardar estado de salud del enjambre: {str(e)}")

    def _execute_ssh_command(self, node_id: str, command: List[str]) -> Tuple[bool, str, str]:
        """Ejecuta un comando SSH en un nodo específico y devuelve el resultado."""
        try:
            full_command = [
                "ssh",
                f"-p", str(self.ssh_port),
                f"{self.ssh_user}@{self.ssh_host}",
                f"cd /data/data/com.termux/files/home && {command[0]} {' '.join(command[1:])}"
            ]

            result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                timeout=self.config.get("ssh_timeout", 30)
            )

            if result.returncode == 0:
                return True, result.stdout, result.stderr
            else:
                return False, "", result.stderr
        except subprocess.TimeoutExpired:
            return False, "", f"Timeout al ejecutar comando en {node_id}"
        except Exception as e:
            return False, "", f"Error al ejecutar comando en {node_id}: {str(e)}"

    def _get_node_status(self, node_id: str) -> Dict:
        """Obtiene el estado actual de un nodo específico."""
        try:
            # Intentar obtener el estado del nodo vía SSH
            success, stdout, stderr = self._execute_ssh_command(
                node_id,
                ["python3", "-c", "import json; print(json.dumps({'status': 'online', 'timestamp': '" +
                 datetime.utcnow().isoformat() + "Z'}))"]
            )

            if success:
                try:
                    status_data = json.loads(stdout)
                    return {
                        "id": node_id,
                        "status": status_data.get("status", "online"),
                        "timestamp": status_data.get("timestamp", datetime.utcnow().isoformat() + "Z"),
                        "last_seen": datetime.utcnow().isoformat() + "Z"
                    }
                except json.JSONDecodeError:
                    self.logger.error(f"Error al parsear respuesta del nodo {node_id}: {stderr}")
                    return {
                        "id": node_id,
                        "status": "offline",
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "last_seen": datetime.utcnow().isoformat() + "Z"
                    }
            else:
                self.logger.warning(f"Nodo {node_id} no respondió: {stderr}")
                return {
                    "id": node_id,
                    "status": "offline",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "last_seen": datetime.utcnow().isoformat() + "Z"
                }
        except Exception as e:
            self.logger.error(f"Error al obtener estado del nodo {node_id}: {str(e)}")
            return {
                "id": node_id,
                "status": "offline",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "last_seen": datetime.utcnow().isoformat() + "Z"
            }

    def _get_node_metrics(self, node_id: str) -> Dict:
        """Obtiene métricas detalladas de un nodo específico."""
        try:
            # Obtener métricas de batería
            success, stdout, stderr = self._execute_ssh_command(
                node_id,
                ["termux-battery-status"]
            )
            battery_level = 0
            if success:
                try:
                    battery_info = json.loads(stdout)
                    battery_level = battery_info.get("percentage", 0)
                except json.JSONDecodeError:
                    pass

            # Obtener métricas de CPU
            success, stdout, stderr = self._execute_ssh_command(
                node_id,
                ["top", "-n", "1", "-b"]
            )
            cpu_load = 100  # Valor por defecto (100% de carga)
            if success:
                lines = stdout.split('\n')
                for line in lines:
                    if 'Cpu(s)' in line:
                        parts = line.split()
                        if len(parts) > 1:
                            cpu_load = float(parts[1].strip('%'))

            # Obtener métricas de señal Wi-Fi
            success, stdout, stderr = self._execute_ssh_command(
                node_id,
                ["cat", "/proc/net/wireless"]
            )
            signal_strength = -100  # Valor por defecto (señal débil)
            if success:
                lines = stdout.split('\n')
                for line in lines:
                    if line.strip() and not line.startswith('I'):
                        parts = line.split()
                        if len(parts) >= 4:
                            signal_strength = int(parts[3])

            # Obtener métricas de espacio en disco
            success, stdout, stderr = self._execute_ssh_command(
                node_id,
                ["df", "-h", "/data"]
            )
            disk_space = 0
            if success:
                lines = stdout.split('\n')
                for line in lines:
                    if '/data' in line:
                        parts = line.split()
                        if len(parts) >= 4:
                            try:
                                disk_space = int(parts[3].replace('G', '').replace('%', ''))
                            except ValueError:
                                pass

            return {
                "node_id": node_id,
                "battery_level": battery_level,
                "cpu_load": cpu_load,
                "signal_strength": signal_strength,
                "disk_space_percent": disk_space,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        except Exception as e:
            self.logger.error(f"Error al obtener métricas del nodo {node_id}: {str(e)}")
            return {
                "node_id": node_id,
                "battery_level": 0,
                "cpu_load": 100,
                "signal_strength": -100,
                "disk_space_percent": 0,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }

    def _check_node_health(self, node_id: str) -> Dict:
        """Verifica la salud de un nodo y devuelve un dict con su estado."""
        try:
            # Obtener estado básico
            status = self._get_node_status(node_id)

            # Obtener métricas detalladas
            metrics = self._get_node_metrics(node_id)

            # Determinar el estado general del nodo
            node_health = {
                "id": node_id,
                "status": status["status"],
                "last_seen": status["last_seen"],
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "metrics": metrics,
                "health_score": 0,
                "capabilities": self._get_node_capabilities(node_id),
                "location": self._get_node_location(node_id),
                "connections": self._get_node_connections(node_id)
            }

            # Calcular puntuación de salud (0-100)
            self._calculate_node_health_score(node_health)

            return node_health
        except Exception as e:
            self.logger.error(f"Error al verificar salud del nodo {node_id}: {str(e)}")
            return {
                "id": node_id,
                "status": "offline",
                "last_seen": datetime.utcnow().isoformat() + "Z",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "metrics": {
                    "node_id": node_id,
                    "battery_level": 0,
                    "cpu_load": 100,
                    "signal_strength": -100,
                    "disk_space_percent": 0,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                },
                "health_score": 0,
                "capabilities": [],
                "location": {},
                "connections": []
            }

    def _get_node_capabilities(self, node_id: str) -> List[str]:
        """Obtiene las capacidades de un nodo específico."""
        try:
            nodes_data = self._load_nodes_config()
            node_capabilities = nodes_data.get("node_capabilities", {}).get(node_id, [])
            return node_capabilities
        except Exception as e:
            self.logger.error(f"Error al obtener capacidades del nodo {node_id}: {str(e)}")
            return []

    def _get_node_location(self, node_id: str) -> Dict:
        """Obtiene la ubicación de un nodo específico."""
        try:
            nodes_data = self._load_nodes_config()
            for node in nodes_data.get("nodes", []):
                if node.get("id") == node_id:
                    return node.get("location", {})
            return {}
        except Exception as e:
            self.logger.error(f"Error al obtener ubicación del nodo {node_id}: {str(e)}")
            return {}

    def _get_node_connections(self, node_id: str) -> List[Dict]:
        """Obtiene las conexiones de un nodo específico."""
        try:
            nodes_data = self._load_nodes_config()
            for node in nodes_data.get("nodes", []):
                if node.get("id") == node_id:
                    return [{
                        "type": "ssh",
                        "host": self.ssh_host,
                        "port": self.ssh_port,
                        "status": "connected" if node.get("status") == "online" else "disconnected"
                    }]
            return []
        except Exception as e:
            self.logger.error(f"Error al obtener conexiones del nodo {node_id}: {str(e)}")
            return []

    def _calculate_node_health_score(self, node_health: Dict) -> None:
        """Calcula la puntuación de salud de un nodo (0-100)."""
        try:
            metrics = node_health["metrics"]
            score = 100  # Puntuación base

            # Puntuación por nivel de batería (0-100)
            battery_score = min(100, max(0, metrics["battery_level"]))
            score = score * (battery_score / 100)

            # Puntuación por carga de CPU (0-100, inversa)
            cpu_score = max(0, 100 - metrics["cpu_load"])
            score = score * (cpu_score / 100)

            # Puntuación por señal Wi-Fi (-100 a 0, convertida a 0-100)
            signal_score = min(100, max(0, (metrics["signal_strength"] + 100) / 2))
            score = score * (signal_score / 100)

            # Puntuación por espacio en disco (0-100, inversa)
            disk_score = max(0, 100 - metrics["disk_space_percent"])
            score = score * (disk_score / 100)

            # Ajustar puntuación según estado
            if node_health["status"] == "offline":
                score = 0
            elif node_health["status"] == "degraded":
                score = score * 0.7
            elif node_health["status"] == "busy":
                score = score * 0.8

            # Redondear a entero
            node_health["health_score"] = round(score)
        except Exception as e:
            self.logger.error(f"Error al calcular puntuación de salud del nodo {node_health['id']}: {str(e)}")
            node_health["health_score"] = 0

    def _update_nodes_state(self):
        """Actualiza el estado de todos los nodos en el enjambre."""
        try:
            nodes_data = self._load_nodes_config()
            available_nodes = [node["id"] for node in nodes_data.get("nodes", []) if node.get("status") == "online"]

            with self.lock:
                for node_id in available_nodes:
                    if node_id not in self.nodes_state:
                        self.nodes_state[node_id] = {}

                    # Obtener estado del nodo
                    node_health = self._check_node_health(node_id)
                    self.nodes_state[node_id] = node_health

                    # Actualizar tiempo del último heartbeat
                    self.last_heartbeat_time[node_id] = datetime.utcnow()

                    # Actualizar grafo de nodos
                    self._update_nodes_graph(node_id, node_health)

                # Eliminar nodos que no respondieron y están fuera de tiempo
                current_time = datetime.utcnow()
                for node_id in list(self.nodes_state.keys()):
                    if node_id not in available_nodes:
                        # Nodo no disponible en la configuración
                        if (current_time - datetime.fromisoformat(self.nodes_state[node_id]["last_seen"].replace('Z', '+00:00'))).total_seconds() > self.node_timeout:
                            del self.nodes_state[node_id]
                            self.nodes_graph.remove_node(node_id)
                            self.logger.warning(f"Nodo {node_id} eliminado del enjambre (fuera de tiempo)")
                    else:
                        # Verificar si el nodo está fuera de tiempo
                        if (current_time - datetime.fromisoformat(self.nodes_state[node_id]["last_seen"].replace('Z', '+00:00'))).total_seconds() > self.node_timeout:
                            self.nodes_state[node_id]["status"] = "offline"
                            self.nodes_state[node_id]["health_score"] = 0
                            self.logger.warning(f"Nodo {node_id} marcado como offline (fuera de tiempo)")

        except Exception as e:
            self.logger.error(f"Error al actualizar estado de nodos: {str(e)}")

    def _update_nodes_graph(self, node_id: str, node_health: Dict):
        """Actualiza el grafo de nodos con la información del nodo."""
        try:
            # Añadir o actualizar nodo en el grafo
            if node_id not in self.nodes_graph:
                self.nodes_graph.add_node(node_id, **node_health)

                # Conectar con otros nodos cercanos (simulado)
                for other_node in list(self.nodes_graph.nodes()):
                    if other_node != node_id:
                        # Simular conexión basada en distancia (si hay coordenadas)
                        node_loc = node_health.get("location", {}).get("coordinates", {})
                        other_loc = self.nodes_graph.nodes[other_node].get("location", {}).get("coordinates", {})

                        if node_loc and other_loc:
                            distance = self._calculate_distance(
                                node_loc["latitude"], node_loc["longitude"],
                                other_loc["latitude"], other_loc["longitude"]
                            )
                            self.nodes_graph.add_edge(node_id, other_node, weight=distance, status="connected")
                        else:
                            self.nodes_graph.add_edge(node_id, other_node, weight=1.0, status="connected")
            else:
                # Actualizar atributos del nodo
                self.nodes_graph.nodes[node_id].update(node_health)

                # Actualizar conexiones con otros nodos
                for other_node in list(self.nodes_graph.neighbors(node_id)):
                    if other_node != node_id:
                        # Verificar si la conexión sigue activa
                        node_loc = node_health.get("location", {}).get("coordinates", {})
                        other_node_data = self.nodes_graph.nodes[other_node]
                        other_loc = other_node_data.get("location", {}).get("coordinates", {})

                        if node_loc and other_loc:
                            distance = self._calculate_distance(
                                node_loc["latitude"], node_loc["longitude"],
                                other_loc["latitude"], other_loc["longitude"]
                            )
                            self.nodes_graph.edges[node_id, other_node]["weight"] = distance
                            self.nodes_graph.edges[node_id, other_node]["status"] = "connected"
                        else:
                            self.nodes_graph.edges[node_id, other_node]["status"] = "connected"

        except Exception as e:
            self.logger.error(f"Error al actualizar grafo de nodos para {node_id}: {str(e)}")

    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calcula la distancia entre dos puntos en coordenadas geográficas (en km)."""
        try:
            # Fórmula de Haversine
            R = 6371  # Radio de la Tierra en km
            dLat = math.radians(lat2 - lat1)
            dLon = math.radians(lon2 - lon1)
            a = (math.sin(dLat / 2) * math.sin(dLat / 2) +
                 math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
                 math.sin(dLon / 2) * math.sin(dLon / 2))
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            distance = R * c
            return distance
        except Exception as e:
            self.logger.error(f"Error al calcular distancia: {str(e)}")
            return 1.0  # Valor por defecto

    def _get_optimal_node(self, task_type: str, task_requirements: List[str]) -> Optional[str]:
        """Selecciona el nodo óptimo para ejecutar una tarea según criterios configurables."""
        try:
            with self.lock:
                if not self.nodes_state:
                    self.logger.warning("No hay nodos disponibles en el enjambre")
                    return None

                # Filtrar nodos que cumplen con los requisitos de la tarea
                candidate_nodes = []
                for node_id, node_health in self.nodes_state.items():
                    if node_health["status"] != "online":
                        continue

                    # Verificar capacidades del nodo
                    node_capabilities = node_health.get("capabilities", [])
                    if not all(req in node_capabilities for req in task_requirements):
                        continue

                    candidate_nodes.append(node_id)

                if not candidate_nodes:
                    self.logger.warning(f"No hay nodos disponibles con las capacidades requeridas para la tarea {task_type}")
                    return None

                # Seleccionar el nodo óptimo según la estrategia configurada
                if self.task_assignment_strategy == "optimal":
                    return self._select_optimal_node(candidate_nodes, task_type)
                elif self.task_assignment_strategy == "round_robin":
                    return self._select_round_robin_node(candidate_nodes)
                elif self.task_assignment_strategy == "load_balancing":
                    return self._select_load_balancing_node(candidate_nodes)
                else:
                    return self._select_optimal_node(candidate_nodes, task_type)

        except Exception as e:
            self.logger.error(f"Error al seleccionar nodo óptimo: {str(e)}")
            return None

    def _select_optimal_node(self, candidate_nodes: List[str], task_type: str) -> Optional[str]:
        """Selecciona el nodo óptimo según criterios ponderados."""
        try:
            best_node = None
            best_score = -1

            for node_id in candidate_nodes:
                node_health = self.nodes_state[node_id]
                score = 0

                # Puntuación por señal Wi-Fi (mayor es mejor)
                signal_score = min(100, max(0, (node_health["metrics"]["signal_strength"] + 100) / 2))
                score += signal_score * self.strategy_weights["signal_strength"]

                # Puntuación por carga de CPU (menor carga es mejor)
                cpu_score = max(0, 100 - node_health["metrics"]["cpu_load"])
                score += cpu_score * self.strategy_weights["cpu_load"]

                # Puntuación por nivel de batería (mayor es mejor)
                battery_score = min(100, max(0, node_health["metrics"]["battery_level"]))
                score += battery_score * self.strategy_weights["battery_level"]

                # Puntuación por distancia (si hay coordenadas)
                if "location" in node_health and "coordinates" in node_health["location"]:
                    # En este caso, preferimos nodos más cercanos al centro de operaciones
                    # (asumimos coordenadas del servidor en Lima)
                    server_lat = -12.0464
                    server_lon = -77.0428
                    node_lat = node_health["location"]["coordinates"]["latitude"]
                    node_lon = node_health["location"]["coordinates"]["longitude"]
                    distance = self._calculate_distance(server_lat, server_lon, node_lat, node_lon)
                    distance_score = max(0, 100 - (distance * 10))  # Normalizar distancia
                    score += distance_score * self.strategy_weights["distance"]

                # Actualizar mejor nodo
                if best_node is None or score > best_score:
                    best_score = score
                    best_node = node_id

            return best_node
        except Exception as e:
            self.logger.error(f"Error al seleccionar nodo óptimo: {str(e)}")
            return candidate_nodes[0] if candidate_nodes else None

    def _select_round_robin_node(self, candidate_nodes: List[str]) -> Optional[str]:
        """Selecciona un nodo usando estrategia round-robin."""
        try:
            if not candidate_nodes:
                return None

            # Implementar round-robin simple
            # En un entorno real, usaríamos un contador persistente
            return candidate_nodes[0]
        except Exception as e:
            self.logger.error(f"Error al seleccionar nodo round-robin: {str(e)}")
            return candidate_nodes[0] if candidate_nodes else None

    def _select_load_balancing_node(self, candidate_nodes: List[str]) -> Optional[str]:
        """Selecciona un nodo usando estrategia de balanceo de carga."""
        try:
            if not candidate_nodes:
                return None

            # Seleccionar el nodo con menor carga de CPU
            best_node = None
            best_cpu_load = float('inf')

            for node_id in candidate_nodes:
                node_health = self.nodes_state[node_id]
                cpu_load = node_health["metrics"]["cpu_load"]

                if cpu_load < best_cpu_load:
                    best_cpu_load = cpu_load
                    best_node = node_id

            return best_node
        except Exception as e:
            self.logger.error(f"Error al seleccionar nodo con balanceo de carga: {str(e)}")
            return candidate_nodes[0] if candidate_nodes else None

    def _assign_task_to_node(self, task_id: str, node_id: str, task_type: str, task_parameters: Dict) -> bool:
        """Asigna una tarea a un nodo específico."""
        try:
            self.logger.info(f"Asignando tarea {task_id} ({task_type}) al nodo {node_id}")

            # Crear payload para el nodo
            payload = {
                "task_id": task_id,
                "task_type": task_type,
                "parameters": task_parameters,
                "assigned_at": datetime.utcnow().isoformat() + "Z",
                "priority": "high",
                "source": "swarm_manager"
            }

            # Enviar la tarea al nodo vía SSH
            script_content = f"""#!/bin/bash
# Script para asignar tarea al nodo {node_id}
# Payload: {json.dumps(payload)}

# Guardar el payload en un archivo temporal
echo '{json.dumps(payload)}' > /tmp/swarm_task_{task_id}.json

# Ejecutar el task_dispatcher local para procesar la tarea
python3 /data/data/com.termux/files/home/task_dispatcher.py --process-task /tmp/swarm_task_{task_id}.json

# Limpiar el archivo temporal
rm -f /tmp/swarm_task_{task_id}.json

echo "Tarea {task_id} asignada con éxito al nodo {node_id}"
"""

            # Guardar el script en un archivo temporal
            script_path = f"/tmp/assign_task_{task_id}.sh"
            with open(script_path, 'w') as f:
                f.write(script_content)

            # Hacer el script ejecutable y enviarlo al nodo
            os.chmod(script_path, 0o755)
            success, stdout, stderr = self._execute_ssh_command(
                node_id,
                ["cat", script_path]
            )

            # Limpiar el script temporal
            os.remove(script_path)

            if success:
                # Actualizar estado del nodo
                with self.lock:
                    if node_id in self.nodes_state:
                        self.nodes_state[node_id]["status"] = "busy"
                        self.nodes_state[node_id]["current_task"] = {
                            "task_id": task_id,
                            "task_type": task_type,
                            "assigned_at": datetime.utcnow().isoformat() + "Z"
                        }
                        self.logger.info(f"Nodo {node_id} marcado como ocupado con tarea {task_id}")
                return True
            else:
                self.logger.error(f"Error al asignar tarea {task_id} al nodo {node_id}: {stderr}")
                return False
        except Exception as e:
            self.logger.error(f"Error al asignar tarea {task_id} al nodo {node_id}: {str(e)}")
            return False

    def _monitor_swarm_health(self):
        """Monitorea la salud del enjambre en segundo plano."""
        while not self.shutdown_event.is_set():
            try:
                self.logger.info("🔍 Monitoreando salud del enjambre...")
                self._update_nodes_state()

                # Generar informe de salud del enjambre
                swarm_health = self._generate_swarm_health_report()

                # Guardar informe de salud
                self._save_swarm_health(swarm_health)

                # Esperar hasta el próximo monitoreo
                time.sleep(self.node_heartbeat_interval)

            except Exception as e:
                self.logger.error(f"Error en el monitoreo de salud del enjambre: {str(e)}")
                time.sleep(self.config.get("error_retry_delay", 60))

    def _generate_swarm_health_report(self) -> Dict:
        """Genera un informe de salud del enjambre."""
        try:
            with self.lock:
                report = {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "node_count": len(self.nodes_state),
                    "online_nodes": 0,
                    "offline_nodes": 0,
                    "busy_nodes": 0,
                    "degraded_nodes": 0,
                    "average_health_score": 0,
                    "nodes": {},
                    "graph": self._generate_graph_data(),
                    "connections": self._generate_connections_data(),
                    "capabilities": self._generate_capabilities_report(),
                    "task_load": self._generate_task_load_report()
                }

                # Contar nodos por estado
                online = degraded = busy = 0
                total_score = 0

                for node_id, node_health in self.nodes_state.items():
                    report["nodes"][node_id] = {
                        "status": node_health["status"],
                        "health_score": node_health["health_score"],
                        "metrics": {
                            "battery_level": node_health["metrics"]["battery_level"],
                            "cpu_load": node_health["metrics"]["cpu_load"],
                            "signal_strength": node_health["metrics"]["signal_strength"],
                            "disk_space_percent": node_health["metrics"]["disk_space_percent"]
                        },
                        "capabilities": node_health["capabilities"],
                        "location": node_health["location"],
                        "current_task": node_health.get("current_task", None)
                    }

                    if node_health["status"] == "online":
                        report["online_nodes"] += 1
                        online += 1
                    elif node_health["status"] == "offline":
                        report["offline_nodes"] += 1
                    elif node_health["status"] == "busy":
                        report["busy_nodes"] += 1
                        busy += 1
                    elif node_health["status"] == "degraded":
                        report["degraded_nodes"] += 1
                        degraded += 1

                    total_score += node_health["health_score"]

                # Calcular promedio de puntuación de salud
                if len(self.nodes_state) > 0:
                    report["average_health_score"] = round(total_score / len(self.nodes_state))

                return report
        except Exception as e:
            self.logger.error(f"Error al generar informe de salud del enjambre: {str(e)}")
            return {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "error": str(e),
                "node_count": 0,
                "online_nodes": 0,
                "offline_nodes": 0,
                "busy_nodes": 0,
                "degraded_nodes": 0,
                "average_health_score": 0
            }

    def _generate_graph_data(self) -> Dict:
        """Genera datos para visualizar el grafo de nodos."""
        try:
            graph_data = {
                "nodes": [],
                "edges": [],
                "properties": {
                    "layout": "force",
                    "physics": {
                        "enabled": True,
                        "solver": "forceAtlas2Based",
                        "timestep": 0.5,
                        "strongGravityMode": True,
                        "gravitationalConstant": -50,
                        "centralGravity": 0.01,
                        "springLength": 100,
                        "springConstant": 0.08,
                        "damping": 0.9
                    }
                }
            }

            # Añadir nodos
            for node_id, node_attrs in self.nodes_graph.nodes(data=True):
                node_data = {
                    "id": node_id,
                    "label": node_attrs.get("name", node_id),
                    "status": node_attrs.get("status", "offline"),
                    "health_score": node_attrs.get("health_score", 0),
                    "battery_level": node_attrs.get("metrics", {}).get("battery_level", 0),
                    "cpu_load": node_attrs.get("metrics", {}).get("cpu_load", 100),
                    "signal_strength": node_attrs.get("metrics", {}).get("signal_strength", -100),
                    "x": node_attrs.get("location", {}).get("coordinates", {}).get("longitude", 0) if node_attrs.get("location") else 0,
                    "y": node_attrs.get("location", {}).get("coordinates", {}).get("latitude", 0) if node_attrs.get("location") else 0,
                    "size": min(20, max(5, node_attrs.get("health_score", 0) / 5)),
                    "color": self._get_node_color(node_attrs.get("status", "offline")),
                    "capabilities": node_attrs.get("capabilities", [])
                }
                graph_data["nodes"].append(node_data)

            # Añadir conexiones
            for edge in self.nodes_graph.edges(data=True):
                edge_data = {
                    "source": edge[0],
                    "target": edge[1],
                    "weight": edge[2].get("weight", 1.0),
                    "status": edge[2].get("status", "disconnected"),
                    "width": max(1, min(5, 10 - (edge[2].get("weight", 1.0) * 2))),
                    "color": self._get_connection_color(edge[2].get("status", "disconnected"))
                }
                graph_data["edges"].append(edge_data)

            return graph_data
        except Exception as e:
            self.logger.error(f"Error al generar datos del grafo: {str(e)}")
            return {
                "nodes": [],
                "edges": [],
                "properties": {}
            }

    def _get_node_color(self, status: str) -> str:
        """Obtiene el color para un nodo según su estado."""
        status = status.lower()
        if status == "online":
            return "#4CAF50"  # Verde (saludable)
        elif status == "busy":
            return "#FFC107"  # Amarillo (ocupado)
        elif status == "degraded":
            return "#FF5722"  # Naranja (degradado)
        elif status == "offline":
            return "#F44336"  # Rojo (fuera de línea)
        elif status == "maintenance":
            return "#9E9E9E"  # Gris (mantenimiento)
        else:
            return "#607D8B"  # Azul grisáceo (desconocido)

    def _get_connection_color(self, status: str) -> str:
        """Obtiene el color para una conexión según su estado."""
        status = status.lower()
        if status == "connected":
            return "#4CAF50"  # Verde (conectado)
        else:
            return "#F44336"  # Rojo (no conectado)

    def _generate_connections_data(self) -> List[Dict]:
        """Genera datos de conexiones entre nodos."""
        try:
            connections = []
            for edge in self.nodes_graph.edges(data=True):
                connections.append({
                    "source": edge[0],
                    "target": edge[1],
                    "status": edge[2].get("status", "disconnected"),
                    "weight": edge[2].get("weight", 1.0),
                    "distance": edge[2].get("weight", 1.0) if edge[2].get("weight") else 1.0
                })
            return connections
        except Exception as e:
            self.logger.error(f"Error al generar datos de conexiones: {str(e)}")
            return []

    def _generate_capabilities_report(self) -> Dict:
        """Genera un informe de las capacidades disponibles en el enjambre."""
        try:
            capabilities = defaultdict(int)
            node_capabilities = defaultdict(set)

            for node_id, node_health in self.nodes_state.items():
                for capability in node_health.get("capabilities", []):
                    capabilities[capability] += 1
                    node_capabilities[capability].add(node_id)

            report = {
                "total_capabilities": len(capabilities),
                "capabilities": {},
                "capability_distribution": {}
            }

            for capability, count in capabilities.items():
                report["capabilities"][capability] = {
                    "count": count,
                    "nodes": list(node_capabilities[capability])
                }

            return report
        except Exception as e:
            self.logger.error(f"Error al generar informe de capacidades: {str(e)}")
            return {
                "total_capabilities": 0,
                "capabilities": {},
                "capability_distribution": {}
            }

    def _generate_task_load_report(self) -> Dict:
        """Genera un informe de la carga de tareas en el enjambre."""
        try:
            task_load = {
                "total_tasks": 0,
                "assigned_tasks": 0,
                "completed_tasks": 0,
                "pending_tasks": 0,
                "node_task_distribution": {},
                "task_types": {}
            }

            # Contar tareas asignadas a nodos
            for node_id, node_health in self.nodes_state.items():
                if "current_task" in node_health:
                    task_load["assigned_tasks"] += 1
                    task_load["total_tasks"] += 1
                    task_type = node_health["current_task"]["task_type"]
                    task_load["task_types"][task_type] = task_load["task_types"].get(task_type, 0) + 1
                    task_load["node_task_distribution"][node_id] = {
                        "task_id": node_health["current_task"]["task_id"],
                        "task_type": task_type,
                        "assigned_at": node_health["current_task"]["assigned_at"]
                    }

            # En un entorno real, también contaríamos tareas completadas y pendientes
            # Esto requeriría integración con el task_dispatcher

            return task_load
        except Exception as e:
            self.logger.error(f"Error al generar informe de carga de tareas: {str(e)}")
            return {
                "total_tasks": 0,
                "assigned_tasks": 0,
                "completed_tasks": 0,
                "pending_tasks": 0,
                "node_task_distribution": {},
                "task_types": {}
            }

    def _coordinate_task_execution(self):
        """Coordina la ejecución de tareas en el enjambre."""
        while not self.shutdown_event.is_set():
            try:
                # En un entorno real, obtendríamos tareas pendientes del task_dispatcher
                # Por ahora, simulamos la coordinación de tareas

                # Ejemplo: Simular recepción de una orden de "Escaneo Masivo"
                self.logger.info("📡 Esperando órdenes de ejecución de tareas...")

                # Simular procesamiento de una tarea (en un entorno real, esto vendría del task_dispatcher)
                time.sleep(self.config.get("task_coordination_interval", 30))

            except Exception as e:
                self.logger.error(f"Error en la coordinación de tareas: {str(e)}")
                time.sleep(self.config.get("error_retry_delay", 60))

    def assign_task(self, task_type: str, task_parameters: Dict, priority: TaskPriority = TaskPriority.MEDIUM) -> Optional[str]:
        """
        Asigna una tarea al nodo más eficiente del enjambre.

        Args:
            task_type: Tipo de tarea (ej: "OSINT_SCAN", "WIFI_SCAN")
            task_parameters: Parámetros específicos para la tarea
            priority: Prioridad de la tarea

        Returns:
            ID del nodo asignado o None si no se pudo asignar
        """
        try:
            self.logger.info(f"📤 Asignando tarea {task_type} con prioridad {priority.name}")

            # Obtener requisitos de la tarea
            task_requirements = self._get_task_requirements(task_type)
            if not task_requirements:
                self.logger.error(f"No se encontraron requisitos para la tarea {task_type}")
                return None

            # Seleccionar nodo óptimo
            optimal_node = self._get_optimal_node(task_type, task_requirements)
            if not optimal_node:
                self.logger.error(f"No se pudo seleccionar nodo para la tarea {task_type}")
                return None

            # Generar ID único para la tarea
            import uuid
            task_id = f"swarm_task_{uuid.uuid4().hex[:8]}"

            # Asignar tarea al nodo seleccionado
            success = self._assign_task_to_node(task_id, optimal_node, task_type, task_parameters)
            if success:
                self.logger.info(f"✅ Tarea {task_id} ({task_type}) asignada al nodo {optimal_node}")
                return optimal_node
            else:
                self.logger.error(f"❌ Error al asignar tarea {task_id} al nodo {optimal_node}")
                return None
        except Exception as e:
            self.logger.error(f"Error al asignar tarea {task_type}: {str(e)}")
            return None

    def _get_task_requirements(self, task_type: str) -> List[str]:
        """Obtiene los requisitos de capacidades para un tipo de tarea específico."""
        try:
            # En un entorno real, obtendríamos esto de la configuración del task_dispatcher
            task_requirements_map = {
                "OSINT_SCAN": ["osint_tools"],
                "WIFI_SCAN": ["wifi_scan"],
                "NETWORK_ANALYSIS": ["network_analysis"],
                "MODULE_EXECUTION": ["module_execution"],
                "BATTERY_MONITORING": ["battery_monitoring"],
                "SECURITY_AUDIT": ["security_audit"],
                "NETWORK_CAPTURE": ["network_capture", "packet_analysis"]
            }

            return task_requirements_map.get(task_type, [])
        except Exception as e:
            self.logger.error(f"Error al obtener requisitos de tarea {task_type}: {str(e)}")
            return []

    def get_swarm_health(self) -> Dict:
        """Obtiene el estado de salud actual del enjambre."""
        try:
            with self.lock:
                return self._generate_swarm_health_report()
        except Exception as e:
            self.logger.error(f"Error al obtener estado de salud del enjambre: {str(e)}")
            return {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "error": str(e),
                "node_count": 0,
                "online_nodes": 0,
                "offline_nodes": 0,
                "busy_nodes": 0,
                "degraded_nodes": 0,
                "average_health_score": 0
            }

    def get_node_status(self, node_id: str) -> Optional[Dict]:
        """Obtiene el estado de un nodo específico."""
        try:
            with self.lock:
                if node_id in self.nodes_state:
                    return self.nodes_state[node_id].copy()
                else:
                    return None
        except Exception as e:
            self.logger.error(f"Error al obtener estado del nodo {node_id}: {str(e)}")
            return None

    def start(self):
        """Inicia el Swarm Manager."""
        self.running = True
        self.shutdown_event.clear()
        self.logger.info("🚀 Swarm Manager iniciado")

        # Inicializar base de datos si es necesario
        self._initialize_database()

        # Iniciar hilos de monitoreo
        self.health_monitor_thread = threading.Thread(
            target=self._monitor_swarm_health,
            daemon=True,
            name="SwarmHealthMonitorThread"
        )
        self.health_monitor_thread.start()

        self.task_coordinator_thread = threading.Thread(
            target=self._coordinate_task_execution,
            daemon=True,
            name="TaskCoordinatorThread"
        )
        self.task_coordinator_thread.start()

        # Esperar a que se presione Ctrl+C
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("🛑 Swarm Manager detenido por el usuario")
        finally:
            self.stop()

    def stop(self):
        """Detiene el Swarm Manager."""
        if self.running:
            self.running = False
            self.shutdown_event.set()

            # Esperar a que los hilos terminen
            if self.health_monitor_thread:
                self.health_monitor_thread.join(timeout=5)
            if self.task_coordinator_thread:
                self.task_coordinator_thread.join(timeout=5)

            self.logger.info("🛑 Swarm Manager detenido")

    def _initialize_database(self):
        """Inicializa la base de datos si no existe."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Crear tabla swarm_health si no existe
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS swarm_health (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    node_count INTEGER,
                    online_nodes INTEGER,
                    offline_nodes INTEGER,
                    busy_nodes INTEGER,
                    degraded_nodes INTEGER,
                    average_health_score REAL,
                    data TEXT,
                    processed BOOLEAN DEFAULT 0
                )
            """)

            # Crear tabla swarm_tasks si no existe
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS swarm_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT UNIQUE NOT NULL,
                    task_type TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    completed_at DATETIME,
                    status TEXT DEFAULT 'assigned',
                    parameters TEXT,
                    result TEXT,
                    error TEXT
                )
            """)

            # Crear índices para búsquedas rápidas
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_swarm_health_timestamp ON swarm_health(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_swarm_health_node_count ON swarm_health(node_count)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_swarm_tasks_task_id ON swarm_tasks(task_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_swarm_tasks_node_id ON swarm_tasks(node_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_swarm_tasks_status ON swarm_tasks(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_swarm_tasks_timestamp ON swarm_tasks(assigned_at)")

            conn.commit()
            conn.close()
            self.logger.info("Base de datos inicializada correctamente")

        except sqlite3.Error as e:
            self.logger.error(f"Error al inicializar la base de datos: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Error al inicializar la base de datos: {str(e)}")
            return False

        return True

    def register_task_assignment(self, task_id: str, task_type: str, node_id: str, parameters: Dict) -> bool:
        """Registra la asignación de una tarea en la base de datos."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Verificar si la tarea ya existe
            cursor.execute("""
                SELECT id FROM swarm_tasks WHERE task_id = ?
            """, (task_id,))

            if cursor.fetchone():
                # Actualizar tarea existente
                cursor.execute("""
                    UPDATE swarm_tasks
                    SET task_type = ?, node_id = ?, assigned_at = CURRENT_TIMESTAMP,
                        parameters = ?, status = 'assigned'
                    WHERE task_id = ?
                """, (task_type, node_id, json.dumps(parameters), task_id))
            else:
                # Insertar nueva tarea
                cursor.execute("""
                    INSERT INTO swarm_tasks (
                        task_id, task_type, node_id, parameters, status
                    ) VALUES (?, ?, ?, ?, ?)
                """, (task_id, task_type, node_id, json.dumps(parameters), "assigned"))

            conn.commit()
            conn.close()
            return True

        except sqlite3.Error as e:
            self.logger.error(f"Error al registrar asignación de tarea: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Error al registrar asignación de tarea: {str(e)}")
            return False

def load_config(config_file: str = "/data/data/com.termux/files/home/swarm_manager_config.json") -> Dict:
    """Carga la configuración desde un archivo JSON."""
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        raise ValueError(f"Error al cargar configuración: {str(e)}")

def save_config(config: Dict, config_file: str = "/data/data/com.termux/files/home/swarm_manager_config.json"):
    """Guarda la configuración en un archivo JSON."""
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        raise ValueError(f"Error al guardar configuración: {str(e)}")

def setup_default_config() -> Dict:
    """Configura valores por defecto para el Swarm Manager."""
    return {
        "version": "1.0.0",
        "description": "Configuración para el Swarm Manager de AURA",
        "node_id": "server_node_001",
        "db_path": "/data/data/com.termux/files/home/aura_intel.db",
        "nodes_config_path": "nodes_config.json",
        "ssh_host": "localhost",
        "ssh_port": 8022,
        "ssh_user": "user",
        "node_heartbeat_interval": 60,
        "node_timeout": 120,
        "max_concurrent_tasks": 5,
        "swarm_health_file": "/data/data/com.termux/files/home/swarm_health.json",
        "task_assignment_strategy": "optimal",
        "strategy_weights": {
            "signal_strength": 0.4,
            "cpu_load": 0.3,
            "battery_level": 0.2,
            "distance": 0.1
        },
        "task_coordination_interval": 30,
        "error_retry_delay": 60,
        "log_file": "/data/data/com.termux/files/home/swarm_manager.log",
        "enable_visualization": true,
        "visualization_update_interval": 60,
        "enable_task_coordination": true,
        "task_priority_weights": {
            "critical": 1.0,
            "high": 0.8,
            "medium": 0.5,
            "low": 0.2
        },
        "node_selection_criteria": [
            "signal_strength",
            "cpu_load",
            "battery_level",
            "disk_space",
            "capabilities"
        ],
        "last_updated": "2026-06-02T00:00:00Z",
        "swarm_capabilities": {
            "osint_tools": 3,
            "wifi_scan": 4,
            "network_analysis": 2,
            "module_execution": 3,
            "battery_monitoring": 4,
            "security_audit": 1,
            "network_capture": 2
        },
        "geolocation": {
            "enabled": true,
            "server_latitude": -12.0464,
            "server_longitude": -77.0428,
            "max_distance_km": 50
        },
        "security_settings": {
            "enable_node_authentication": true,
            "require_ssl": true,
            "api_rate_limit": 100,
            "rate_limit_window": 60,
            "enable_audit_logging": true,
            "audit_log_retention": 30
        }
    }

def main():
    """Punto de entrada principal del Swarm Manager."""
    parser = argparse.ArgumentParser(description="Swarm Manager para la orquestación distribuida de tareas en AURA.")
    parser.add_argument("--config", help="Archivo de configuración JSON", default="/data/data/com.termux/files/home/swarm_manager_config.json")
    parser.add_argument("--setup", action="store_true", help="Configurar valores por defecto")
    parser.add_argument("--health", action="store_true", help="Obtener estado de salud del enjambre")
    parser.add_argument("--node", help="Obtener estado de un nodo específico")
    parser.add_argument("--assign", help="Asignar una tarea a un nodo (ej: 'OSINT_SCAN --target example.com')")
    args = parser.parse_args()

    try:
        if args.setup:
            config = setup_default_config()
            save_config(config)
            print("✅ Configuración por defecto guardada en swarm_manager_config.json")
            print("Por favor edita este archivo según tu configuración antes de iniciar el servicio.")
            return

        config = load_config(args.config)
        swarm_manager = SwarmManager(config)

        if args.health:
            health_report = swarm_manager.get_swarm_health()
            print(f"📊 Estado de salud del enjambre ({health_report['timestamp']}):")
            print(f"   Nodos totales: {health_report['node_count']}")
            print(f"   Nodos online: {health_report['online_nodes']}")
            print(f"   Nodos ocupados: {health_report['busy_nodes']}")
            print(f"   Puntuación promedio de salud: {health_report['average_health_score']}")
            print(f"   Nodos degradados: {health_report['degraded_nodes']}")
            print(f"   Nodos offline: {health_report['offline_nodes']}")
            return

        if args.node:
            node_status = swarm_manager.get_node_status(args.node)
            if node_status:
                print(f"📡 Estado del nodo {args.node}:")
                print(f"   Estado: {node_status['status']}")
                print(f"   Puntuación de salud: {node_status['health_score']}")
                print(f"   Batería: {node_status['metrics']['battery_level']}%")
                print(f"   Carga CPU: {node_status['metrics']['cpu_load']}%")
                print(f"   Señal Wi-Fi: {node_status['metrics']['signal_strength']} dBm")
                print(f"   Espacio en disco: {node_status['metrics']['disk_space_percent']}%")
                print(f"   Capacidades: {', '.join(node_status['capabilities'])}")
                if "current_task" in node_status:
                    print(f"   Tarea actual: {node_status['current_task']['task_type']} (ID: {node_status['current_task']['task_id']})")
            else:
                print(f"❌ Nodo {args.node} no encontrado en el enjambre")
            return

        if args.assign:
            # Parsear los argumentos de la tarea
            import shlex
            task_parts = shlex.split(args.assign)
            if not task_parts:
                print("Formato incorrecto. Ejemplo: OSINT_SCAN --target example.com --tools PhantomOSINT")
                return

            task_type = task_parts[0]
            parameters = {}
            i = 1
            while i < len(task_parts):
                if task_parts[i].startswith("--"):
                    key = task_parts[i][2:]
                    if i + 1 < len(task_parts) and not task_parts[i+1].startswith("--"):
                        value = task_parts[i+1]
                        parameters[key] = value
                        i += 2
                    else:
                        # Valor booleano (true)
                        parameters[key] = True
                        i += 1
                else:
                    i += 1

            print(f"📤 Asignando tarea {task_type} con parámetros: {parameters}")
            assigned_node = swarm_manager.assign_task(task_type, parameters)
            if assigned_node:
                print(f"✅ Tarea asignada al nodo {assigned_node}")
            else:
                print("❌ Error al asignar la tarea")
            return

        print("🚀 Swarm Manager listo para uso.")
        print("Ejemplos de uso:")
        print("  python swarm_manager.py --setup (Configurar valores por defecto)")
        print("  python swarm_manager.py --health (Obtener estado de salud del enjambre)")
        print("  python swarm_manager.py --node node_001 (Obtener estado de un nodo)")
        print("  python swarm_manager.py --assign \"OSINT_SCAN --target example.com\" (Asignar tarea)")
        print("  python swarm_manager.py (Iniciar Swarm Manager en segundo plano)")

        # Iniciar el Swarm Manager
        swarm_manager.start()

    except Exception as e:
        print(f"❌ Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()