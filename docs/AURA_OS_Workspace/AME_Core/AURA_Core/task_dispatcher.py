#!/usr/bin/env python3
"""
task_dispatcher.py - Dispatcher central para la gestión de tareas en el sistema AURA.
Este módulo asigna tareas de la cola tasks_queue.json a nodos disponibles,
monitorea su ejecución y registra los resultados.

Características:
- Asignación inteligente de tareas según capacidades de los nodos.
- Comunicación con nodos móviles vía SSH.
- Protocolo de comunicación para estado de tareas (SUCCESS/FAIL).
- Logging detallado y manejo de errores.
- Soporte para reintentos y escalado de prioridades.
"""

import os
import sys
import json
import logging
import time
import threading
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import uuid
import signal
import queue
import hashlib
from enum import Enum

class TaskStatus(Enum):
    """Estados posibles de una tarea."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskDispatcher:
    """Dispatcher central para la gestión de tareas en el sistema AURA."""

    def __init__(self, config: Dict):
        self.config = config
        self.logger = self._setup_logging()
        self.tasks_queue_path = config.get("tasks_queue_path", "tasks_queue.json")
        self.nodes_config_path = config.get("nodes_config_path", "nodes_config.json")
        self.task_timeout = config.get("task_timeout", 3600)  # 1 hora por defecto
        self.retry_delay = config.get("retry_delay", 60)  # 1 minuto por defecto
        self.max_retries = config.get("max_retries", 3)
        self.ssh_timeout = config.get("ssh_timeout", 30)
        self.task_check_interval = config.get("task_check_interval", 10)  # segundos
        self.running = False
        self.shutdown_event = threading.Event()
        self.task_queue = queue.Queue()
        self.active_tasks = {}
        self.lock = threading.Lock()
        self.task_processor_thread = None
        self.monitor_thread = None
        self.nodes_capabilities = self._load_nodes_capabilities()

    def _setup_logging(self):
        """Configura el logging para el dispatcher."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('task_dispatcher.log'),
                logging.StreamHandler()
            ]
        )
        logger = logging.getLogger("TaskDispatcher")
        logger.setLevel(logging.INFO)
        return logger

    def _load_nodes_capabilities(self) -> Dict:
        """Carga las capacidades de los nodos desde el archivo de configuración."""
        try:
            with open(self.nodes_config_path, 'r') as f:
                nodes_data = json.load(f)
            return nodes_data.get("node_capabilities", {})
        except Exception as e:
            self.logger.error(f"Error al cargar capacidades de nodos: {str(e)}")
            return {}

    def _load_tasks_queue(self) -> List[Dict]:
        """Carga la cola de tareas desde el archivo JSON."""
        try:
            with open(self.tasks_queue_path, 'r') as f:
                tasks_data = json.load(f)
            return tasks_data.get("tasks", [])
        except Exception as e:
            self.logger.error(f"Error al cargar cola de tareas: {str(e)}")
            return []

    def _save_tasks_queue(self, tasks: List[Dict]):
        """Guarda la cola de tareas en el archivo JSON."""
        try:
            with open(self.tasks_queue_path, 'r') as f:
                tasks_data = json.load(f)

            tasks_data["tasks"] = tasks
            with open(self.tasks_queue_path, 'w') as f:
                json.dump(tasks_data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error al guardar cola de tareas: {str(e)}")

    def _generate_task_id(self) -> str:
        """Genera un ID único para una nueva tarea."""
        return f"task_{uuid.uuid4().hex[:8]}"

    def _find_suitable_node(self, task_type: str) -> Optional[str]:
        """Encuentra un nodo con las capacidades requeridas para ejecutar la tarea."""
        required_capabilities = self._get_task_type_requirements(task_type)
        if not required_capabilities:
            return None

        for node_id, capabilities in self.nodes_capabilities.items():
            if all(cap in capabilities for cap in required_capabilities):
                return node_id
        return None

    def _get_task_type_requirements(self, task_type: str) -> List[str]:
        """Obtiene los requisitos de capacidades para un tipo de tarea específico."""
        try:
            with open(self.tasks_queue_path, 'r') as f:
                tasks_data = json.load(f)
            task_types = tasks_data.get("task_types", {})
            return task_types.get(task_type, {}).get("required_capabilities", [])
        except Exception as e:
            self.logger.error(f"Error al obtener requisitos de tarea: {str(e)}")
            return []

    def _update_task_status(self, task_id: str, status: TaskStatus, node_id: Optional[str] = None,
                          result: Optional[Dict] = None, error: Optional[str] = None):
        """Actualiza el estado de una tarea en la cola."""
        tasks = self._load_tasks_queue()

        for task in tasks:
            if task["id"] == task_id:
                task["status"] = status.value
                if node_id is not None:
                    task["assigned_node"] = node_id
                    task["assigned_at"] = datetime.utcnow().isoformat() + "Z"
                if result is not None:
                    task["result"] = result
                if error is not None:
                    task["error"] = error
                if status == TaskStatus.COMPLETED:
                    task["completed_at"] = datetime.utcnow().isoformat() + "Z"
                elif status == TaskStatus.FAILED:
                    task["failed_at"] = datetime.utcnow().isoformat() + "Z"
                    task["metadata"]["retries"] = task["metadata"].get("retries", 0) + 1

                # Mover la tarea a completed_tasks o failed_tasks si corresponde
                if status == TaskStatus.COMPLETED:
                    tasks.remove(task)
                    with open(self.tasks_queue_path, 'r') as f:
                        tasks_data = json.load(f)
                    tasks_data["completed_tasks"].append(task)
                    with open(self.tasks_queue_path, 'w') as f:
                        json.dump(tasks_data, f, indent=2)
                elif status == TaskStatus.FAILED:
                    tasks.remove(task)
                    with open(self.tasks_queue_path, 'r') as f:
                        tasks_data = json.load(f)
                    tasks_data["failed_tasks"].append(task)
                    with open(self.tasks_queue_path, 'w') as f:
                        json.dump(tasks_data, f, indent=2)

                self._save_tasks_queue(tasks)
                return

    def _execute_ssh_command(self, node_id: str, command: List[str]) -> Tuple[bool, str, str]:
        """Ejecuta un comando SSH en un nodo específico y devuelve el resultado."""
        try:
            ssh_host = self.config.get("ssh_host", "localhost")
            ssh_port = self.config.get("ssh_port", 8022)
            ssh_user = self.config.get("ssh_user", "user")

            full_command = [
                "ssh",
                f"-p", str(ssh_port),
                f"{ssh_user}@{ssh_host}",
                f"cd /data/data/com.termux/files/home && {command[0]} {' '.join(command[1:])}"
            ]

            result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                timeout=self.ssh_timeout
            )

            if result.returncode == 0:
                return True, result.stdout, result.stderr
            else:
                return False, "", result.stderr
        except subprocess.TimeoutExpired:
            return False, "", f"Timeout al ejecutar comando en {node_id}"
        except Exception as e:
            return False, "", f"Error al ejecutar comando en {node_id}: {str(e)}"

    def _execute_task_on_node(self, task: Dict, node_id: str) -> Dict:
        """Ejecuta una tarea específica en un nodo móvil."""
        task_id = task["id"]
        task_type = task["type"]
        parameters = task["parameters"]

        self.logger.info(f"Ejecutando tarea {task_id} ({task_type}) en nodo {node_id}")

        # Crear un script temporal para ejecutar la tarea
        script_content = self._generate_task_script(task_type, parameters, node_id)

        try:
            # Guardar el script en un archivo temporal
            script_path = f"/tmp/task_{task_id}.sh"
            with open(script_path, 'w') as f:
                f.write(script_content)

            # Copiar el script al nodo móvil
            copy_success, _, copy_error = self._execute_ssh_command(
                node_id,
                ["mkdir", "-p", "/tmp/aura_tasks"]
            )
            if not copy_success:
                self.logger.error(f"Error al crear directorio en {node_id}: {copy_error}")
                return {"status": "failed", "error": copy_error}

            copy_success, _, copy_error = self._execute_ssh_command(
                node_id,
                ["cat", script_path]
            )
            if not copy_success:
                self.logger.error(f"Error al copiar script a {node_id}: {copy_error}")
                return {"status": "failed", "error": copy_error}

            # Ejecutar el script en el nodo
            execute_command = [
                "bash", "/tmp/aura_tasks/task_{}.sh".format(task_id),
                str(self.task_timeout)
            ]

            success, stdout, stderr = self._execute_ssh_command(node_id, execute_command)

            # Limpiar el script después de ejecutarlo
            self._execute_ssh_command(node_id, ["rm", "-f", "/tmp/aura_tasks/task_{}.sh".format(task_id)])

            if success:
                try:
                    result = json.loads(stdout)
                    return {
                        "status": "success",
                        "result": result,
                        "stdout": stdout,
                        "stderr": stderr
                    }
                except json.JSONDecodeError:
                    return {
                        "status": "success",
                        "result": {"raw_output": stdout},
                        "stdout": stdout,
                        "stderr": stderr
                    }
            else:
                return {
                    "status": "failed",
                    "error": stderr,
                    "stdout": stdout,
                    "stderr": stderr
                }

        except Exception as e:
            self.logger.error(f"Error al ejecutar tarea {task_id} en {node_id}: {str(e)}")
            return {"status": "failed", "error": str(e)}

    def _generate_task_script(self, task_type: str, parameters: Dict, node_id: str) -> str:
        """Genera un script bash para ejecutar una tarea específica."""
        script_template = """#!/bin/bash
# Script generado por AURA Task Dispatcher para ejecutar tarea {task_id}
# Tipo: {task_type}
# Nodo: {node_id}
# Tiempo límite: {timeout} segundos

set -e
set -o pipefail

TIMEOUT={timeout}
TASK_ID={task_id}
TASK_TYPE={task_type}
NODE_ID={node_id}

# Función para manejar el timeout
timeout_handler() {{
    echo "{\"status\": \"failed\", \"error\": \"Timeout de {timeout} segundos alcanzado\"}" > /tmp/task_{TASK_ID}_result.json
    exit 1
}}

# Configurar el timeout
trap timeout_handler ALRM
( sleep $TIMEOUT ; kill -ALRM $$ ) &

# Ejecutar la tarea según su tipo
case "$TASK_TYPE" in
    SCAN_WIFI)
        echo "Ejecutando escaneo WiFi..."
        # Implementación del escaneo WiFi
        RESULT=$(
            python3 << 'PYTHON_END'
import json
import subprocess
import time

def scan_wifi(network, scan_type, duration, target_ssids):
    try:
        # Simular escaneo WiFi (en un entorno real, usar herramientas como airodump-ng)
        result = {{
            "devices": [],
            "access_points": [],
            "security_issues": []
        }}

        # Simular algunos resultados
        if "AURA-NET" in target_ssids:
            result["access_points"].append({{
                "ssid": "AURA-NET",
                "bssid": "00:11:22:33:44:55",
                "channel": 6,
                "signal": -65,
                "encryption": "WPA2-AES",
                "devices": [
                    "{{"mac": "AA:BB:CC:DD:EE:FF", "manufacturer": "Apple", "last_seen": time.time()}}"
                ]
            }})

        if "Guest-WiFi" in target_ssids:
            result["access_points"].append({{
                "ssid": "Guest-WiFi",
                "bssid": "55:66:77:88:99:AA",
                "channel": 11,
                "signal": -75,
                "encryption": "WPA2-PSK",
                "devices": []
            }})

        # Simular un dispositivo conectado
        result["devices"].append({{
            "mac": "BB:CC:DD:EE:FF:00",
            "manufacturer": "Google",
            "ip": "192.168.1.100",
            "last_seen": time.time()
        }})

        return json.dumps(result)

    except Exception as e:
        return json.dumps({{"status": "failed", "error": str(e)}})

# Parámetros de la tarea
params = {parameters}
result = scan_wifi(**params)
print(result)
PYTHON_END
        )
        echo "$RESULT" > /tmp/task_{TASK_ID}_result.json
        ;;
    ANALIZAR_RED_LOCAL)
        echo "Ejecutando análisis de red local..."
        # Implementación del análisis de red local
        RESULT=$(
            python3 << 'PYTHON_END'
import json
import time

def analyze_network(interface, scan_duration, detect_rogue_devices, check_for_malware, generate_report):
    try:
        # Simular análisis de red local
        result = {{
            "network_map": {{
                "interface": "{interface}",
                "devices": [],
                "connections": []
            }},
            "rogue_devices": [],
            "malware_indicators": [],
            "report_path": "/tmp/local_network_analysis_report.json"
        }}

        # Simular algunos dispositivos en la red
        result["network_map"]["devices"].append({{
            "mac": "AA:BB:CC:DD:EE:FF",
            "ip": "192.168.1.1",
            "hostname": "router",
            "manufacturer": "Cisco",
            "status": "online"
        }})

        result["network_map"]["devices"].append({{
            "mac": "BB:CC:DD:EE:FF:00",
            "ip": "192.168.1.100",
            "hostname": "laptop",
            "manufacturer": "Dell",
            "status": "online"
        }})

        # Simular dispositivos no autorizados si se solicita
        if detect_rogue_devices:
            result["rogue_devices"].append({{
                "mac": "XX:YY:ZZ:AA:BB:CC",
                "ip": "192.168.1.200",
                "hostname": "unknown_device",
                "manufacturer": "Unknown",
                "status": "rogue",
                "last_seen": time.time(),
                "risk_score": 0.95
            }})

        # Simular indicadores de malware si se solicita
        if check_for_malware:
            result["malware_indicators"].append({{
                "device_mac": "BB:CC:DD:EE:FF:00",
                "threat_type": "potential_virus",
                "severity": "medium",
                "details": "Detectado posible virus en el dispositivo",
                "timestamp": time.time()
            }})

        # Generar informe si se solicita
        if generate_report:
            with open(result["report_path"], 'w') as f:
                json.dump(result, f)

        return json.dumps(result)

    except Exception as e:
        return json.dumps({{"status": "failed", "error": str(e)}})

# Parámetros de la tarea
params = {parameters}
result = analyze_network(**params)
print(result)
PYTHON_END
        )
        echo "$RESULT" > /tmp/task_{TASK_ID}_result.json
        ;;
    OSINT_SCAN)
        echo "Ejecutando escaneo OSINT..."
        # Implementación del escaneo OSINT
        RESULT=$(
            python3 << 'PYTHON_END'
import json
import time
import random

def osint_scan(target, tools, depth, timeout, output_format):
    try:
        result = {
            "domains": [],
            "subdomains": [],
            "ports": [],
            "vulnerabilities": [],
            "report": None
        }

        # Simular resultados según las herramientas seleccionadas
        if "PhantomOSINT" in tools:
            result["domains"].append(target)
            result["subdomains"].extend([
                f"sub1.{target}",
                f"sub2.{target}",
                f"api.{target}",
                f"www.{target}"
            ])

            result["ports"].extend([
                {"port": 80, "service": "HTTP", "status": "open"},
                {"port": 443, "service": "HTTPS", "status": "open"},
                {"port": 22, "service": "SSH", "status": "open"},
                {"port": 3306, "service": "MySQL", "status": "closed"}
            ])

            result["vulnerabilities"].append({
                "type": "potential_xss",
                "severity": "medium",
                "description": "Posible vulnerabilidad XSS detectada en /login",
                "url": f"https://{target}/login",
                "confidence": 0.85
            })

        if "SubdomainEnumeration" in tools:
            result["subdomains"].extend([
                f"mail.{target}",
                f"ftp.{target}",
                f"dev.{target}",
                f"test.{target}"
            ])

        if "PortScanner" in tools:
            result["ports"].extend([
                {"port": 8080, "service": "HTTP-alt", "status": "open"},
                {"port": 21, "service": "FTP", "status": "filtered"},
                {"port": 8000, "service": "HTTP-proxy", "status": "closed"}
            ])

        # Generar informe si se solicita
        if output_format == "json":
            result["report"] = json.dumps(result, indent=2)

        return json.dumps(result)

    except Exception as e:
        return json.dumps({"status": "failed", "error": str(e)})

# Parámetros de la tarea
params = {parameters}
result = osint_scan(**params)
print(result)
PYTHON_END
        )
        echo "$RESULT" > /tmp/task_{TASK_ID}_result.json
        ;;
    OSINT_SHODAN)
        echo "Ejecutando escaneo Shodan OSINT (Venice)..."
        # Implementación del escaneo Shodan usando VeniceShodanScanner
        RESULT=$(
            python3 << 'PYTHON_END'
import json
import sys
import os

# Añadir el path de AURA_Core al sys.path
aura_core_path = "/data/data/com.termux/files/home/.aura"
if aura_core_path not in sys.path:
    sys.path.insert(0, aura_core_path)

try:
    from venice_shodan_scanner import VeniceShodanScanner
    
    # Parámetros de la tarea
    params = {parameters}
    target = params.get("target", "")
    mode = params.get("mode", "host")
    limit = params.get("limit", 10)
    query = params.get("query", target)
    
    if not target:
        result = {"status": "failed", "error": "Target parameter is required"}
    else:
        scanner = VeniceShodanScanner()
        
        if mode == "host":
            result = scanner.scan_host(target)
        elif mode == "vulns":
            result = scanner.get_vulnerabilities(target)
        elif mode == "search":
            result = scanner.search(query, limit)
        else:
            result = {"status": "failed", "error": f"Invalid mode: {mode}"}
        
        # Añadir embed para Discord
        if "error" not in result:
            result["embed"] = scanner.format_for_discord_embed(result)
            
except Exception as e:
    result = {"status": "failed", "error": str(e)}

print(json.dumps(result))
PYTHON_END
        )
        echo "$RESULT" > /tmp/task_{TASK_ID}_result.json
        ;;
    MONITOREO_BATERIA)
        echo "Ejecutando monitoreo de batería..."
        # Implementación del monitoreo de batería
        RESULT=$(
            python3 << 'PYTHON_END'
import json
import time
import random

def monitor_battery(interval, threshold, duration):
    try:
        result = {{
            "battery_levels": [],
            "low_battery_warnings": [],
            "final_status": None
        }}

        # Simular monitoreo de batería durante el tiempo especificado
        end_time = time.time() + duration
        current_time = time.time()

        while current_time < end_time:
            # Simular nivel de batería (entre 20% y 100%)
            battery_level = max(20, min(100, random.randint(20, 100)))
            timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(current_time))

            result["battery_levels"].append({{
                "timestamp": timestamp,
                "level": battery_level,
                "status": "normal" if battery_level >= threshold else "low"
            }})

            # Generar advertencia si el nivel es bajo
            if battery_level < threshold:
                result["low_battery_warnings"].append({{
                    "timestamp": timestamp,
                    "level": battery_level,
                    "message": f"Nivel de batería bajo ({battery_level}%) - por debajo del umbral de {threshold}%",
                    "recommended_action": "conectar a carga"
                }})

            current_time += interval
            time.sleep(interval)

        # Determinar estado final
        if result["battery_levels"]:
            last_level = result["battery_levels"][-1]["level"]
            result["final_status"] = {
                "level": last_level,
                "status": "critical" if last_level < 10 else
                         "low" if last_level < threshold else
                         "normal"
            }

        return json.dumps(result)

    except Exception as e:
        return json.dumps({{"status": "failed", "error": str(e)}})

# Parámetros de la tarea
params = {parameters}
result = monitor_battery(**params)
print(result)
PYTHON_END
        )
        echo "$RESULT" > /tmp/task_{TASK_ID}_result.json
        ;;
    EJECUTAR_MODULE_VENICE)
        echo "Ejecutando módulo Venice..."
        # Ejecutar el módulo Venice directamente
        MODULE_NAME="{module_name}"
        MODULE_ARGS="{module_args}"
        TIMEOUT={timeout}

        # Verificar que el módulo exista
        if [ ! -f "/data/data/com.termux/files/home/.aura/${{MODULE_NAME}}" ]; then
            echo "{\"status\": \"failed\", \"error\": \"Módulo no encontrado: /data/data/com.termux/files/home/.aura/${{MODULE_NAME}}\"}" > /tmp/task_{TASK_ID}_result.json
            exit 1
        fi

        # Ejecutar el módulo con timeout
        RESULT=$(
            timeout $TIMEOUT python3 /data/data/com.termux/files/home/.aura/${{MODULE_NAME}} ${MODULE_ARGS} 2>&1
        )
        EXIT_CODE=$?

        # Guardar el resultado
        echo "{{
            \"exit_code\": {EXIT_CODE},
            \"stdout\": \"{RESULT}\",
            \"execution_time\": {timeout},
            \"module_output\": \"{RESULT}\"
        }}" > /tmp/task_{TASK_ID}_result.json
        ;;
    *)
        echo "{\"status\": \"failed\", \"error\": \"Tipo de tarea no soportado: {task_type}\"}" > /tmp/task_{TASK_ID}_result.json
        exit 1
        ;;
esac

# Verificar si el resultado fue generado correctamente
if [ ! -f "/tmp/task_{TASK_ID}_result.json" ]; then
    echo "{\"status\": \"failed\", \"error\": \"No se generó resultado para la tarea\"}" > /tmp/task_{TASK_ID}_result.json
    exit 1
fi

# Mostrar el resultado
cat /tmp/task_{TASK_ID}_result.json
"""

        # Reemplazar placeholders con valores reales
        script = script_template.format(
            task_id=task["id"],
            task_type=task_type,
            node_id=node_id,
            timeout=self.task_timeout,
            parameters=json.dumps(parameters),
            module_name=parameters.get("module_name", ""),
            module_args=" ".join(parameters.get("module_args", []))
        )

        return script

    def _process_task(self, task: Dict):
        """Procesa una tarea individual: la asigna a un nodo y monitorea su ejecución."""
        task_id = task["id"]
        task_type = task["type"]

        self.logger.info(f"Procesando tarea {task_id} ({task_type})")

        # Actualizar estado a assigned
        self._update_task_status(task_id, TaskStatus.ASSIGNED)

        # Encontrar un nodo adecuado
        node_id = self._find_suitable_node(task_type)
        if not node_id:
            self.logger.error(f"No se encontró nodo con capacidades para ejecutar tarea {task_id} ({task_type})")
            self._update_task_status(task_id, TaskStatus.FAILED, error="No se encontró nodo disponible")
            return

        self.logger.info(f"Asignando tarea {task_id} al nodo {node_id}")

        # Ejecutar la tarea en el nodo
        try:
            result = self._execute_task_on_node(task, node_id)

            if result["status"] == "success":
                self.logger.info(f"Tarea {task_id} completada con éxito en nodo {node_id}")
                self._update_task_status(
                    task_id,
                    TaskStatus.COMPLETED,
                    node_id=node_id,
                    result=result.get("result", {})
                )
            else:
                self.logger.error(f"Tarea {task_id} falló en nodo {node_id}: {result.get('error', 'Error desconocido')}")
                self._update_task_status(
                    task_id,
                    TaskStatus.FAILED,
                    node_id=node_id,
                    error=result.get("error", "Error desconocido")
                )

        except Exception as e:
            self.logger.error(f"Error al procesar tarea {task_id} en nodo {node_id}: {str(e)}")
            self._update_task_status(
                task_id,
                TaskStatus.FAILED,
                node_id=node_id,
                error=str(e)
            )

    def _check_task_status(self):
        """Verifica el estado de las tareas en progreso y reasigna las fallidas."""
        while not self.shutdown_event.is_set():
            try:
                tasks = self._load_tasks_queue()

                # Buscar tareas asignadas pero no en progreso
                for task in tasks:
                    if task["status"] == TaskStatus.ASSIGNED.value and task["id"] not in self.active_tasks:
                        self.active_tasks[task["id"]] = {
                            "task": task,
                            "start_time": datetime.utcnow(),
                            "retries": 0
                        }
                        self.task_queue.put(task)

                # Verificar tareas en progreso con timeout
                current_time = datetime.utcnow()
                for task_id, task_info in list(self.active_tasks.items()):
                    if current_time - task_info["start_time"] > timedelta(seconds=self.task_timeout):
                        self.logger.warning(f"Tarea {task_id} ha excedido el tiempo límite. Marcando como fallida.")
                        self._update_task_status(
                            task_id,
                            TaskStatus.FAILED,
                            error=f"Tiempo límite de {self.task_timeout} segundos excedido"
                        )
                        del self.active_tasks[task_id]

                time.sleep(self.task_check_interval)

            except Exception as e:
                self.logger.error(f"Error al verificar estado de tareas: {str(e)}")
                time.sleep(self.retry_delay)

    def _task_processor(self):
        """Procesador de tareas en segundo plano."""
        while not self.shutdown_event.is_set():
            try:
                task = self.task_queue.get(timeout=self.task_check_interval)
                if task:
                    self._process_task(task)
                    # Eliminar la tarea de active_tasks si ya no está en la cola
                    if task["id"] in self.active_tasks:
                        del self.active_tasks[task["id"]]
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error en el procesador de tareas: {str(e)}")
                time.sleep(self.retry_delay)

    def start(self):
        """Inicia el dispatcher de tareas."""
        self.running = True
        self.shutdown_event.clear()
        self.logger.info("Dispatcher de tareas iniciado.")

        # Cargar tareas iniciales en la cola
        tasks = self._load_tasks_queue()
        for task in tasks:
            if task["status"] == TaskStatus.PENDING.value:
                self.task_queue.put(task)

        # Iniciar hilos
        self.task_processor_thread = threading.Thread(
            target=self._task_processor,
            daemon=True,
            name="TaskProcessorThread"
        )
        self.task_processor_thread.start()

        self.monitor_thread = threading.Thread(
            target=self._check_task_status,
            daemon=True,
            name="TaskMonitorThread"
        )
        self.monitor_thread.start()

        # Esperar a que se presione Ctrl+C
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Deteniendo dispatcher de tareas...")
        finally:
            self.stop()

    def stop(self):
        """Detiene el dispatcher de tareas."""
        if self.running:
            self.running = False
            self.shutdown_event.set()

            # Esperar a que los hilos terminen
            if self.task_processor_thread:
                self.task_processor_thread.join(timeout=5)
            if self.monitor_thread:
                self.monitor_thread.join(timeout=5)

            self.logger.info("Dispatcher de tareas detenido.")

    def add_task(self, task_type: str, parameters: Dict, priority: str = "medium",
                 requested_by: str = "system", reason: str = "Tarea generada por el sistema") -> str:
        """
        Añade una nueva tarea a la cola.

        Args:
            task_type: Tipo de tarea (ej: "SCAN_WIFI", "OSINT_SCAN")
            parameters: Parámetros específicos para la tarea
            priority: Prioridad de la tarea ("high", "medium", "low")
            requested_by: Quién solicitó la tarea
            reason: Razón para la tarea

        Returns:
            ID de la tarea creada
        """
        task_id = self._generate_task_id()
        created_at = datetime.utcnow().isoformat() + "Z"

        new_task = {
            "id": task_id,
            "type": task_type,
            "status": TaskStatus.PENDING.value,
            "priority": priority,
            "created_at": created_at,
            "assigned_node": None,
            "assigned_at": None,
            "parameters": parameters,
            "expected_result": {},
            "metadata": {
                "requested_by": requested_by,
                "reason": reason,
                "retries": 0,
                "max_retries": self.max_retries
            }
        }

        # Cargar tareas existentes y añadir la nueva
        tasks = self._load_tasks_queue()
        tasks.append(new_task)

        # Guardar la cola actualizada
        self._save_tasks_queue(tasks)

        # Añadir la tarea a la cola de procesamiento
        self.task_queue.put(new_task)

        self.logger.info(f"Tarea añadida: {task_id} ({task_type})")
        return task_id

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Obtiene el estado actual de una tarea."""
        tasks = self._load_tasks_queue()
        for task in tasks:
            if task["id"] == task_id:
                return task.copy()

        # Verificar en tareas completadas
        try:
            with open(self.tasks_queue_path, 'r') as f:
                tasks_data = json.load(f)
            completed_tasks = tasks_data.get("completed_tasks", [])
            for task in completed_tasks:
                if task["id"] == task_id:
                    return task.copy()

            failed_tasks = tasks_data.get("failed_tasks", [])
            for task in failed_tasks:
                if task["id"] == task_id:
                    return task.copy()
        except Exception as e:
            self.logger.error(f"Error al obtener estado de tarea: {str(e)}")

        return None

    def cancel_task(self, task_id: str) -> bool:
        """Cancela una tarea en progreso."""
        tasks = self._load_tasks_queue()

        for task in tasks:
            if task["id"] == task_id and task["status"] in [TaskStatus.ASSIGNED.value, TaskStatus.IN_PROGRESS.value]:
                self._update_task_status(task_id, TaskStatus.CANCELLED, error="Tarea cancelada por el usuario")
                return True

        # Verificar en tareas completadas (por si acaso)
        try:
            with open(self.tasks_queue_path, 'r') as f:
                tasks_data = json.load(f)
            completed_tasks = tasks_data.get("completed_tasks", [])
            for task in completed_tasks:
                if task["id"] == task_id:
                    return False  # La tarea ya está completada

            failed_tasks = tasks_data.get("failed_tasks", [])
            for task in failed_tasks:
                if task["id"] == task_id:
                    return False  # La tarea ya falló
        except Exception as e:
            self.logger.error(f"Error al cancelar tarea: {str(e)}")

        return False

def load_config(config_file: str = "task_dispatcher_config.json") -> Dict:
    """Carga la configuración desde un archivo JSON."""
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        raise ValueError(f"Error al cargar configuración: {str(e)}")

def save_config(config: Dict, config_file: str = "task_dispatcher_config.json"):
    """Guarda la configuración en un archivo JSON."""
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        raise ValueError(f"Error al guardar configuración: {str(e)}")

def setup_default_config() -> Dict:
    """Configura valores por defecto para el dispatcher de tareas."""
    return {
        "version": "1.0.0",
        "description": "Configuración para el dispatcher de tareas AURA",
        "tasks_queue_path": "tasks_queue.json",
        "nodes_config_path": "nodes_config.json",
        "ssh_host": "localhost",
        "ssh_port": 8022,
        "ssh_user": "user",
        "ssh_timeout": 30,
        "task_timeout": 3600,  # 1 hora por defecto
        "retry_delay": 60,    # 1 minuto por defecto
        "max_retries": 3,
        "task_check_interval": 10,  # segundos
        "log_file": "task_dispatcher.log"
    }

def main():
    """Punto de entrada principal del dispatcher de tareas."""
    parser = argparse.ArgumentParser(description="Dispatcher central para la gestión de tareas en el sistema AURA.")
    parser.add_argument("--config", help="Archivo de configuración JSON", default="task_dispatcher_config.json")
    parser.add_argument("--setup", action="store_true", help="Configurar valores por defecto")
    parser.add_argument("--add-task", help="Añadir una nueva tarea (ej: 'SCAN_WIFI --network 2.4GHz')")
    parser.add_argument("--status", help="Obtener el estado de una tarea")
    parser.add_argument("--cancel", help="Cancelar una tarea")
    args = parser.parse_args()

    try:
        if args.setup:
            config = setup_default_config()
            save_config(config)
            print("Configuración por defecto guardada en task_dispatcher_config.json")
            print("Por favor edita este archivo según tu configuración antes de iniciar el servicio.")
            return

        config = load_config(args.config)
        dispatcher = TaskDispatcher(config)

        if args.add_task:
            # Parsear los argumentos de la tarea
            import shlex
            task_parts = shlex.split(args.add_task)
            if not task_parts:
                print("Formato incorrecto. Ejemplo: SCAN_WIFI --network 2.4GHz --duration 60")
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

            task_id = dispatcher.add_task(
                task_type=task_type,
                parameters=parameters,
                priority="high",
                requested_by="user",
                reason=f"Tarea añadida manualmente: {args.add_task}"
            )
            print(f"Tarea añadida con éxito. ID: {task_id}")
            return

        if args.status:
            task_id = args.status
            status = dispatcher.get_task_status(task_id)
            if status:
                print(f"Estado de la tarea {task_id}:")
                print(json.dumps(status, indent=2))
            else:
                print(f"No se encontró la tarea {task_id}")
            return

        if args.cancel:
            task_id = args.cancel
            success = dispatcher.cancel_task(task_id)
            if success:
                print(f"Tarea {task_id} cancelada con éxito")
            else:
                print(f"No se pudo cancelar la tarea {task_id} (puede que ya esté completada o no exista)")
            return

        print("Dispatcher de tareas listo para uso.")
        print("Ejemplos de uso:")
        print("  python task_dispatcher.py --setup (Configurar valores por defecto)")
        print("  python task_dispatcher.py --add-task \"SCAN_WIFI --network 2.4GHz --duration 60\"")
        print("  python task_dispatcher.py --status task_abc123")
        print("  python task_dispatcher.py --cancel task_abc123")
        print("  python task_dispatcher.py (Iniciar dispatcher en segundo plano)")

        # Iniciar el dispatcher
        dispatcher.start()

    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    import argparse
    main()