#!/usr/bin/env python3
"""
Resource Guardian para AURA.
Monitorea y optimiza el uso de recursos de hardware, incluyendo:
1. Gestión de VRAM en Ollama (descargar modelos inactivos)
2. Congelación de procesos en modo de bajo consumo
3. Telemetría de consumo de recursos y alertas
"""

import os
import time
import threading
import subprocess
import psutil
import requests
import json
import logging
import platform
import socket
import netifaces
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# Configuración global
RESOURCE_GUARDIAN_CONFIG = {
    "ollama_host": "http://localhost:11434",
    "model_inactivity_threshold": 300,  # 5 minutos de inactividad para descargar modelos
    "check_interval": 60,  # Verificar cada 60 segundos
    "max_memory_usage": 0.85,  # 85% de uso de memoria como umbral de alerta
    "low_power_mode_threshold": 0.2,  # 20% de batería para activar modo de bajo consumo
    "mobile_network_detect_interval": 300,  # Verificar conexión móvil cada 5 minutos
    "log_file": "resource_guardian.log",
    "critical_processes": ["python", "ollama", "redis-server", "AME_Core/servidor_ame.py", "shadow_core.py"],
    "non_critical_processes": ["voice_processor.py", "test_*", "debug_*", "shadow_core.py"],
    "system_info": {
        "os": platform.system().lower(),
        "platform": platform.platform().lower(),
        "python_version": platform.python_version()
    }
}

# Estado del sistema
SYSTEM_STATE = {
    "last_model_check": None,
    "loaded_models": {},
    "last_memory_check": None,
    "memory_usage": 0.0,
    "battery_level": None,
    "on_mobile_network": False,
    "low_power_mode": False,
    "process_priorities": {},
    "last_network_check": None,
    "active_sessions": 0,
    "last_optimization_time": None,
    "optimization_count": 0,
    "alerts_triggered": 0
}

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(RESOURCE_GUARDIAN_CONFIG["log_file"]),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ResourceGuardian")

def load_ollama_models() -> Dict[str, Dict]:
    """Cargar la lista de modelos actualmente cargados en Ollama."""
    try:
        response = requests.get(f"{RESOURCE_GUARDIAN_CONFIG['ollama_host']}/api/tags", timeout=5)
        if response.status_code == 200:
            models_data = response.json().get("models", {})
            loaded_models = {}

            for model_name, model_info in models_data.items():
                # Verificar si el modelo está actualmente cargado (en uso)
                try:
                    # Intentar obtener información del modelo (esto puede fallar si no está cargado)
                    model_response = requests.get(f"{RESOURCE_GUARDIAN_CONFIG['ollama_host']}/api/show?model={model_name}", timeout=3)
                    if model_response.status_code == 200:
                        loaded_models[model_name] = {
                            "name": model_name,
                            "size": model_info.get("size", 0),
                            "last_used": datetime.now(),
                            "active": True
                        }
                except Exception as e:
                    logger.debug(f"Error al verificar modelo {model_name}: {e}")
                    # Si no se puede obtener información, asumimos que no está activo
                    continue

            return loaded_models
        else:
            logger.error(f"Error al obtener modelos de Ollama: {response.text}")
            return {}
    except Exception as e:
        logger.error(f"Error al cargar modelos de Ollama: {e}")
        return {}

def check_model_usage() -> None:
    """Verificar el uso de modelos y descargar los inactivos."""
    try:
        current_time = datetime.now()
        loaded_models = load_ollama_models()

        # Actualizar estado de modelos
        for model_name, model_info in loaded_models.items():
            if model_name not in SYSTEM_STATE["loaded_models"]:
                SYSTEM_STATE["loaded_models"][model_name] = model_info
                logger.info(f"Modelo cargado: {model_name}")
            else:
                SYSTEM_STATE["loaded_models"][model_name]["last_used"] = current_time
                SYSTEM_STATE["loaded_models"][model_name]["active"] = True

        # Verificar modelos que ya no están cargados
        models_to_remove = []
        for model_name, model_info in SYSTEM_STATE["loaded_models"].items():
            if model_name not in loaded_models:
                logger.info(f"Modelo descargado: {model_name}")
                models_to_remove.append(model_name)

        for model_name in models_to_remove:
            del SYSTEM_STATE["loaded_models"][model_name]

        # Verificar modelos inactivos y descargarlos si es necesario
        for model_name, model_info in SYSTEM_STATE["loaded_models"].items():
            inactivity_time = (current_time - model_info["last_used"]).total_seconds()

            if inactivity_time > RESOURCE_GUARDIAN_CONFIG["model_inactivity_threshold"]:
                logger.info(f"Modelo {model_name} inactivo por {inactivity_time:.0f} segundos. Descargando...")
                try:
                    # Intentar descargar el modelo
                    unload_response = requests.post(
                        f"{RESOURCE_GUARDIAN_CONFIG['ollama_host']}/api/unload?model={model_name}",
                        timeout=10
                    )

                    if unload_response.status_code == 200:
                        logger.info(f"Modelo {model_name} descargado correctamente")
                        del SYSTEM_STATE["loaded_models"][model_name]
                        SYSTEM_STATE["optimization_count"] += 1
                    else:
                        logger.warning(f"Error al descargar modelo {model_name}: {unload_response.text}")
                except Exception as e:
                    logger.error(f"Error al descargar modelo {model_name}: {e}")

        SYSTEM_STATE["last_model_check"] = current_time

    except Exception as e:
        logger.error(f"Error al verificar uso de modelos: {e}")

def check_system_memory() -> None:
    """Verificar el uso de memoria del sistema y tomar acciones si es necesario."""
    try:
        current_time = datetime.now()
        memory = psutil.virtual_memory()
        SYSTEM_STATE["memory_usage"] = memory.percent
        SYSTEM_STATE["last_memory_check"] = current_time

        logger.info(f"Uso de memoria: {memory.percent:.1f}% ({memory.used / (1024 ** 3):.1f} GB / {memory.total / (1024 ** 3):.1f} GB)")

        # Verificar si el uso de memoria supera el umbral crítico
        if memory.percent > RESOURCE_GUARDIAN_CONFIG["max_memory_usage"] * 100:
            logger.warning(f"¡Uso de memoria crítico ({memory.percent:.1f}%)! Optimizando recursos...")

            # Identificar y matar procesos no críticos
            terminate_non_critical_processes()

            # Verificar batería y modo de bajo consumo
            check_battery_and_network_status()

            # Registrar alerta
            SYSTEM_STATE["alerts_triggered"] += 1
            SYSTEM_STATE["last_optimization_time"] = current_time

    except Exception as e:
        logger.error(f"Error al verificar memoria del sistema: {e}")

def check_battery_and_network_status() -> None:
    """Verificar el nivel de batería y la conexión a red móvil."""
    try:
        # Verificar nivel de batería (solo en sistemas con batería)
        try:
            battery = psutil.sensors_battery()
            if battery:
                SYSTEM_STATE["battery_level"] = battery.percent
                logger.info(f"Nivel de batería: {battery.percent}%")

                # Activar modo de bajo consumo si la batería está baja
                if battery.percent < RESOURCE_GUARDIAN_CONFIG["low_power_mode_threshold"] * 100:
                    if not SYSTEM_STATE["low_power_mode"]:
                        logger.info("Activando modo de bajo consumo (batería baja)")
                        SYSTEM_STATE["low_power_mode"] = True
                        set_process_priorities(low_power=True)
                else:
                    if SYSTEM_STATE["low_power_mode"]:
                        logger.info("Desactivando modo de bajo consumo (batería suficiente)")
                        SYSTEM_STATE["low_power_mode"] = False
                        set_process_priorities(low_power=False)
            else:
                SYSTEM_STATE["battery_level"] = None
        except Exception as e:
            logger.debug(f"Error al verificar batería: {e}")
            SYSTEM_STATE["battery_level"] = None

        # Verificar conexión a red móvil
        try:
            current_time = datetime.now()
            if (not SYSTEM_STATE["last_network_check"] or
                (current_time - SYSTEM_STATE["last_network_check"]).total_seconds() > RESOURCE_GUARDIAN_CONFIG["mobile_network_detect_interval"]):

                is_mobile = detect_mobile_network()
                SYSTEM_STATE["on_mobile_network"] = is_mobile
                logger.info(f"Conexión a red móvil detectada: {'Sí' if is_mobile else 'No'}")

                if is_mobile:
                    # Si estamos en red móvil, activar modo de bajo consumo
                    if not SYSTEM_STATE["low_power_mode"]:
                        logger.info("Activando modo de bajo consumo (red móvil detectada)")
                        SYSTEM_STATE["low_power_mode"] = True
                        set_process_priorities(low_power=True)
                else:
                    # Si no estamos en red móvil, verificar batería
                    check_battery_and_network_status()

                SYSTEM_STATE["last_network_check"] = current_time

        except Exception as e:
            logger.error(f"Error al verificar estado de red y batería: {e}")

    except Exception as e:
        logger.error(f"Error en check_battery_and_network_status: {e}")

def detect_mobile_network() -> bool:
    """Detectar si estamos conectados a una red móvil."""
    try:
        # Estrategia 1: Verificar interfaces de red conocidas (wwan, mobile, etc.)
        interfaces = psutil.net_if_addrs()
        for interface_name, addresses in interfaces.items():
            for addr in addresses:
                if addr.family == socket.AF_INET:  # IPv4
                    if interface_name.lower().startswith(('wwan', 'mobile', 'cellular', 'pdp')):
                        return True

        # Estrategia 2: Verificar la puerta de enlace por defecto (puede indicar red móvil)
        try:
            gateways = psutil.net_if_stats().get('default', {}).get('gateways', [])
            if gateways:
                for gateway in gateways:
                    if gateway[0] != '0.0.0.0' and not gateway[0].startswith(('192.168.', '10.', '172.16.', '127.')):
                        return True
        except Exception as e:
            logger.debug(f"Error al verificar gateways: {e}")

        # Estrategia 3: Verificar DNS público (si no estamos en una red local)
        try:
            # Intentar resolver un dominio público
            socket.setdefaulttimeout(5)
            socket.socket(socket.AF_INET, socket.SOCK_DGRAM).connect(("8.8.8.8", 53))
            socket.socket(socket.AF_INET, socket.SOCK_DGRAM).connect(("1.1.1.1", 53))

            # Si podemos conectarnos a DNS públicos, probablemente no estamos en red móvil
            # Pero si no podemos, podría indicar red móvil o conexión inestable
            # Esta estrategia es menos confiable, así que la usamos como último recurso

            # Intentar obtener la IP pública (si es posible)
            try:
                response = requests.get("https://api.ipify.org", timeout=3)
                if response.status_code == 200:
                    public_ip = response.text
                    logger.debug(f"IP pública detectada: {public_ip}")

                    # Si la IP pública no es de una red local, probablemente estamos en red móvil
                    if not any(public_ip.startswith(ip_range) for ip_range in ['192.168.', '10.', '172.16.', '127.', '169.254.']):
                        return True
            except Exception as e:
                logger.debug(f"Error al obtener IP pública: {e}")

        except Exception as e:
            logger.debug(f"Error al verificar conexión a DNS: {e}")

        # Estrategia 4: Verificar con netifaces (para sistemas Linux/macOS)
        try:
            if platform.system().lower() in ['linux', 'darwin']:
                for interface in netifaces.interfaces():
                    try:
                        addrs = netifaces.ifaddresses(interface)
                        if netifaces.AF_INET in addrs:
                            for addr_info in addrs[netifaces.AF_INET]:
                                if 'addr' in addr_info:
                                    ip_address = addr_info['addr']
                                    if not any(ip_address.startswith(ip_range) for ip_range in ['192.168.', '10.', '172.16.', '127.', '169.254.']):
                                        return True
                    except Exception as e:
                        logger.debug(f"Error al verificar interfaz {interface}: {e}")
        except Exception as e:
            logger.debug(f"Error al verificar interfaces con netifaces: {e}")

        # Si ninguna estrategia detectó red móvil, asumir que no estamos en red móvil
        return False

    except Exception as e:
        logger.debug(f"Error al detectar red móvil: {e}")
        return False

def terminate_non_critical_processes() -> None:
    """Identificar y terminar procesos no críticos para liberar memoria."""
    try:
        terminated_processes = 0

        for proc in psutil.process_iter(['pid', 'name', 'username', 'cmdline', 'create_time']):
            try:
                process_name = proc.info['name'].lower()
                cmdline = proc.info.get('cmdline', [])
                create_time = proc.info['create_time']

                # Verificar si es un proceso crítico
                is_critical = False
                for critical_process in RESOURCE_GUARDIAN_CONFIG["critical_processes"]:
                    if (critical_process in process_name or
                        (cmdline and any(critical_process in str(c) for c in cmdline))):
                        is_critical = True
                        break

                # Verificar si es un proceso no crítico
                if not is_critical:
                    for non_critical_pattern in RESOURCE_GUARDIAN_CONFIG["non_critical_processes"]:
                        if (non_critical_pattern in process_name or
                            (cmdline and any(non_critical_pattern in str(c) for c in cmdline))):
                            # Verificar si el proceso está usando mucha memoria
                            try:
                                process_memory = proc.memory_info().rss / (1024 * 1024)  # MB
                                if process_memory > 50:  # Si usa más de 50MB
                                    logger.warning(f"Terminando proceso no crítico de alto consumo: {process_name} (PID: {proc.info['pid']}, Memoria: {process_memory:.1f}MB)")
                                    proc.terminate()
                                    terminated_processes += 1
                                    time.sleep(0.1)  # Esperar un poco antes de continuar
                            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                                continue

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        if terminated_processes > 0:
            logger.info(f"Terminados {terminated_processes} procesos no críticos para liberar memoria")
            SYSTEM_STATE["optimization_count"] += 1
        else:
            logger.info("No se encontraron procesos no críticos para terminar")

    except Exception as e:
        logger.error(f"Error al terminar procesos no críticos: {e}")

def set_process_priorities(low_power: bool = False) -> None:
    """Configurar prioridades de procesos según el modo de bajo consumo."""
    try:
        # Obtener procesos críticos
        critical_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'username', 'cmdline']):
            try:
                process_name = proc.info['name'].lower()
                cmdline = proc.info.get('cmdline', [])

                for critical_process in RESOURCE_GUARDIAN_CONFIG["critical_processes"]:
                    if (critical_process in process_name or
                        (cmdline and any(critical_process in str(c) for c in cmdline))):
                        critical_processes.append(proc.info['pid'])
                        break

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # Configurar prioridades
        for pid in critical_processes:
            try:
                process = psutil.Process(pid)
                if low_power:
                    # Reducir prioridad en modo de bajo consumo
                    if hasattr(process, 'nice'):
                        # Intentar establecer prioridad baja
                        try:
                            process.nice(psutil.HIGH_PRIORITY_CLASS)  # Prioridad baja
                            logger.info(f"Reducida prioridad del proceso crítico (PID: {pid}) en modo de bajo consumo")
                        except Exception as e:
                            logger.debug(f"Error al reducir prioridad del proceso (PID: {pid}): {e}")
                else:
                    # Restaurar prioridad normal
                    if hasattr(process, 'nice'):
                        # Intentar restaurar prioridad normal
                        try:
                            process.nice(psutil.NORMAL_PRIORITY_CLASS)  # Prioridad normal
                            logger.info(f"Restaurada prioridad normal del proceso crítico (PID: {pid})")
                        except Exception as e:
                            logger.debug(f"Error al restaurar prioridad del proceso (PID: {pid}): {e}")

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
                logger.debug(f"Error al configurar prioridad del proceso (PID: {pid}): {e}")

        # Guardar estado de prioridades
        SYSTEM_STATE["process_priorities"] = {
            "low_power": low_power,
            "last_updated": datetime.now(),
            "processes": critical_processes
        }

    except Exception as e:
        logger.error(f"Error al configurar prioridades de procesos: {e}")

def monitor_active_sessions() -> None:
    """Monitorear sesiones activas para evitar descargar modelos en uso."""
    try:
        # Contar sesiones activas (conexiones a Ollama, procesos de AURA, etc.)
        active_sessions = 0

        # Verificar conexiones a Ollama
        try:
            response = requests.get(f"{RESOURCE_GUARDIAN_CONFIG['ollama_host']}/api/info", timeout=3)
            if response.status_code == 200:
                info = response.json()
                active_sessions = info.get("models", {}).get("count", 0)
                logger.debug(f"Sesiones activas en Ollama: {active_sessions}")
        except Exception as e:
            logger.debug(f"Error al verificar sesiones activas en Ollama: {e}")

        # Verificar procesos de AURA
        aura_processes = 0
        for proc in psutil.process_iter(['name']):
            try:
                if any(critical in proc.info['name'].lower() for critical in ["aura", "ollama", "python", "shadow"]):
                    aura_processes += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        active_sessions += aura_processes
        logger.debug(f"Procesos de AURA activos: {aura_processes}")

        SYSTEM_STATE["active_sessions"] = active_sessions
        logger.info(f"Sesiones activas totales: {active_sessions}")

    except Exception as e:
        logger.error(f"Error al monitorear sesiones activas: {e}")

def log_system_telemetry() -> None:
    """Registrar telemetría del sistema en los logs."""
    try:
        current_time = datetime.now()
        log_entry = {
            "timestamp": current_time.isoformat(),
            "memory_usage": SYSTEM_STATE.get("memory_usage", 0),
            "loaded_models": len(SYSTEM_STATE.get("loaded_models", {})),
            "active_sessions": SYSTEM_STATE.get("active_sessions", 0),
            "battery_level": SYSTEM_STATE.get("battery_level"),
            "on_mobile_network": SYSTEM_STATE.get("on_mobile_network", False),
            "low_power_mode": SYSTEM_STATE.get("low_power_mode", False),
            "optimizations_applied": SYSTEM_STATE.get("optimization_count", 0),
            "alerts_triggered": SYSTEM_STATE.get("alerts_triggered", 0),
            "system_info": {
                "os": platform.system(),
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory": {
                    "total": psutil.virtual_memory().total / (1024 ** 3),
                    "available": psutil.virtual_memory().available / (1024 ** 3),
                    "used": psutil.virtual_memory().used / (1024 ** 3),
                    "percent": psutil.virtual_memory().percent
                },
                "disk": {
                    "total": psutil.disk_usage('/').total / (1024 ** 3),
                    "used": psutil.disk_usage('/').used / (1024 ** 3),
                    "free": psutil.disk_usage('/').free / (1024 ** 3),
                    "percent": psutil.disk_usage('/').percent
                },
                "network": {
                    "interfaces": list(psutil.net_if_stats().keys()),
                    "is_mobile": SYSTEM_STATE.get("on_mobile_network", False)
                }
            }
        }

        logger.info(f"📊 Telemetría del sistema: {json.dumps(log_entry, indent=2)}")

    except Exception as e:
        logger.error(f"Error al registrar telemetría del sistema: {e}")

def resource_optimization_loop() -> None:
    """Bucle principal de optimización de recursos."""
    logger.info("🚀 Iniciando Resource Guardian")

    while True:
        try:
            # Verificar uso de modelos
            check_model_usage()

            # Verificar memoria y tomar acciones si es necesario
            check_system_memory()

            # Monitorear sesiones activas
            monitor_active_sessions()

            # Registrar telemetría
            log_system_telemetry()

            # Esperar hasta la próxima verificación
            time.sleep(RESOURCE_GUARDIAN_CONFIG["check_interval"])

        except Exception as e:
            logger.error(f"Error en el bucle de optimización de recursos: {e}")
            time.sleep(RESOURCE_GUARDIAN_CONFIG["check_interval"])

def start_resource_guardian() -> None:
    """Iniciar el Resource Guardian en un hilo separado."""
    logger.info("🛡️ Iniciando Resource Guardian en segundo plano")

    # Iniciar el bucle de optimización en un hilo separado
    optimization_thread = threading.Thread(
        target=resource_optimization_loop,
        daemon=True,
        name="ResourceGuardianOptimizationLoop"
    )
    optimization_thread.start()

    logger.info("✅ Resource Guardian iniciado correctamente")

    return optimization_thread

def main() -> None:
    """Función principal para ejecutar el Resource Guardian."""
    logger.info("=" * 80)
    logger.info("🛡️ RESOURCE GUARDIAN - SISTEMA DE OPTIMIZACIÓN DE RECURSOS")
    logger.info("=" * 80)
    logger.info("Este script monitorea y optimiza el uso de recursos de hardware.")
    logger.info(f"Configuración del sistema: {RESOURCE_GUARDIAN_CONFIG['system_info']}")
    logger.info("=" * 80)

    # Iniciar el Resource Guardian
    start_resource_guardian()

    # Esperar a que el usuario detenga el programa
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 Resource Guardian detenido por el usuario")

if __name__ == "__main__":
    main()