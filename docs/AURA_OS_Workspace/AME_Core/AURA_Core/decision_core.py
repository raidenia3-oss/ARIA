import logging
import time
import json
import os
import uuid
from datetime import datetime
from enum import Enum
from threading import Thread, Lock
from typing import Dict, List, Optional
from queue import PriorityQueue
import psutil

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('DecisionCore')

class TaskPriority(Enum):
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4

class DecisionCore:
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self.tasks = PriorityQueue()
        self.cache = {}
        self.cache_lock = Lock()
        self.metrics = {
            "tasks_processed": 0,
            "tasks_failed": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "start_time": datetime.now().isoformat()
        }
        self.state = "INITIALIZING"
        self.ghost_mode = False
        self._start_monitoring_thread()

    def _load_config(self, config_path: str) -> Dict:
        """Carga la configuración desde un archivo JSON."""
        default_config = {
            "max_tasks": 100,
            "cache_size": 1000,
            "monitoring_interval": 60,
            "ghost_mode_timeout": 300,
            "max_retries": 3,
            "retry_delay": 5,
            "high_priority_timeout": 10,
            "medium_priority_timeout": 30,
            "low_priority_timeout": 60
        }
        
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    logger.info(f"Configuración cargada desde {config_path}")
                    return {**default_config, **config}
            else:
                logger.warning(f"Archivo de configuración {config_path} no encontrado. Usando configuración por defecto.")
                return default_config
        except Exception as e:
            logger.error(f"Error al cargar configuración: {e}")
            return default_config

    def _start_monitoring_thread(self):
        """Inicia un hilo de monitoreo en segundo plano."""
        def monitor_loop():
            while True:
                self._monitor_system_resources()
                time.sleep(self.config["monitoring_interval"])
        
        monitor_thread = Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        logger.info("Hilo de monitoreo iniciado")

    def _monitor_system_resources(self):
        """Monitorea el uso de recursos del sistema."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            self.metrics["cpu_usage"] = cpu_percent
            self.metrics["memory_usage"] = memory.percent
            
            if cpu_percent > 90:
                logger.warning(f"Uso de CPU alto: {cpu_percent}%")
            if memory.percent > 90:
                logger.warning(f"Uso de memoria alto: {memory.percent}%")
                
        except Exception as e:
            logger.error(f"Error al monitorear recursos: {e}")

    def add_task(self, task_func, priority: TaskPriority = TaskPriority.MEDIUM, *args, **kwargs):
        """Añade una tarea a la cola con prioridad."""
        try:
            task_id = str(uuid.uuid4())
            task = {
                "id": task_id,
                "function": task_func,
                "args": args,
                "kwargs": kwargs,
                "priority": priority,
                "timestamp": datetime.now().isoformat(),
                "retries": 0
            }
            
            self.tasks.put((priority.value, task))
            logger.info(f"Tarea {task_id} añadida con prioridad {priority.name}")
            return task_id
            
        except Exception as e:
            logger.error(f"Error al añadir tarea: {e}")
            return None

    def process_tasks(self):
        """Procesa tareas de la cola."""
        while True:
            try:
                if not self.tasks.empty():
                    priority, task = self.tasks.get()
                    
                    # Verificar límite de reintentos
                    if task["retries"] >= self.config["max_retries"]:
                        logger.error(f"Tarea {task['id']} excedió límite de reintentos")
                        self.metrics["tasks_failed"] += 1
                        continue
                    
                    try:
                        # Ejecutar tarea
                        logger.info(f"Procesando tarea {task['id']}")
                        result = task["function"](*task["args"], **task["kwargs"])
                        
                        # Guardar en caché si es necesario
                        self._cache_result(task["id"], result)
                        
                        self.metrics["tasks_processed"] += 1
                        logger.info(f"Tarea {task['id']} completada exitosamente")
                        
                    except Exception as e:
                        logger.error(f"Error en tarea {task['id']}: {e}")
                        task["retries"] += 1
                        self.tasks.put((priority, task))
                        
                else:
                    time.sleep(0.1)  # Evitar uso excesivo de CPU
                    
            except Exception as e:
                logger.error(f"Error en procesamiento de tareas: {e}")
                time.sleep(1)

    def _cache_result(self, task_id: str, result):
        """Guarda el resultado en caché."""
        with self.cache_lock:
            if len(self.cache) >= self.config["cache_size"]:
                # Eliminar entrada más antigua
                oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k]["timestamp"])
                del self.cache[oldest_key]
            
            self.cache[task_id] = {
                "result": result,
                "timestamp": datetime.now().isoformat()
            }
            self.metrics["cache_hits"] += 1

    def get_cached_result(self, task_id: str):
        """Obtiene un resultado de la caché."""
        with self.cache_lock:
            if task_id in self.cache:
                self.metrics["cache_hits"] += 1
                return self.cache[task_id]["result"]
            else:
                self.metrics["cache_misses"] += 1
                return None

    def get_metrics(self):
        """Retorna las métricas actuales."""
        return self.metrics.copy()

    def toggle_ghost_mode(self):
        """Activa/desactiva el modo fantasma."""
        self.ghost_mode = not self.ghost_mode
        logger.info(f"Modo fantasma {'activado' if self.ghost_mode else 'desactivado'}")
        return self.ghost_mode

    def get_status(self):
        """Retorna el estado actual del sistema."""
        return {
            "state": self.state,
            "ghost_mode": self.ghost_mode,
            "tasks_queue_size": self.tasks.qsize(),
            "cache_size": len(self.cache),
            "metrics": self.get_metrics()
        }

    def start(self):
        """Inicia el Decision Core."""
        self.state = "RUNNING"
        logger.info("Decision Core iniciado")
        
        # Iniciar procesamiento de tareas
        processor_thread = Thread(target=self.process_tasks, daemon=True)
        processor_thread.start()
        
        return True

    def stop(self):
        """Detiene el Decision Core."""
        self.state = "STOPPED"
        logger.info("Decision Core detenido")
        return True

# Funciones de ejemplo para tareas
def example_task1():
    time.sleep(1)
    return {"status": "completed", "task": "example1"}

def example_task2():
    time.sleep(2)
    return {"status": "completed", "task": "example2"}

if __name__ == "__main__":
    # Ejemplo de uso
    core = DecisionCore()
    core.start()
    
    # Añadir tareas de ejemplo
    core.add_task(example_task1, TaskPriority.HIGH)
    core.add_task(example_task2, TaskPriority.MEDIUM)
    
    # Esperar un tiempo para procesamiento
    time.sleep(5)
    
    # Obtener métricas
    print("Métricas:", core.get_metrics())
    print("Estado:", core.get_status())
    
    # Detener el sistema
    core.stop()