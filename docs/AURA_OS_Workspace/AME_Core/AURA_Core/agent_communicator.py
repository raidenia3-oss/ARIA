#!/usr/bin/env python3
"""
Agent Communicator para AURA.
Gestiona la comunicación entre agentes usando Redis.
"""

import os
import json
import time
import uuid
import redis
from datetime import datetime
import jsonpickle
import threading

class AgentCommunicator:
    def __init__(self, host='localhost', port=6379, password=None, db=0):
        self.redis_client = redis.Redis(
            host=host,
            port=port,
            password=password,
            db=db,
            decode_responses=True
        )
        self.task_queues = {}
        self.task_results = {}
        self.lock = threading.Lock()

    def initialize_queues(self, agents):
        """Inicializar colas de tareas para cada agente."""
        for agent in agents:
            self.task_queues[agent] = f"task_queue:{agent}"
            self.redis_client.delete(self.task_queues[agent])

    def publish_task(self, agent_name, task_data):
        """Publicar una tarea en la cola de un agente específico."""
        try:
            task_id = str(uuid.uuid4())
            task_data["task_id"] = task_id
            task_data["timestamp"] = datetime.now().isoformat()

            # Guardar la tarea en Redis
            self.redis_client.publish(self.task_queues[agent_name], jsonpickle.encode(task_data))

            # Registrar la tarea en el sistema
            with self.lock:
                self.task_results[task_id] = {
                    "status": "pending",
                    "agent": agent_name,
                    "timestamp": task_data["timestamp"],
                    "result": None
                }

            return task_id
        except Exception as e:
            print(f"Error al publicar tarea: {e}")
            return None

    def get_task(self, agent_name):
        """Obtener la siguiente tarea de la cola de un agente."""
        try:
            # Obtener la próxima tarea de la cola
            message = self.redis_client.blpop(self.task_queues[agent_name], timeout=0)
            if message:
                task_data = jsonpickle.decode(message[1])
                return task_data
            return None
        except Exception as e:
            print(f"Error al obtener tarea: {e}")
            return None

    def set_task_result(self, task_id, result):
        """Establecer el resultado de una tarea."""
        try:
            with self.lock:
                if task_id in self.task_results:
                    self.task_results[task_id]["status"] = "completed"
                    self.task_results[task_id]["result"] = result
                    self.task_results[task_id]["completed_at"] = datetime.now().isoformat()
        except Exception as e:
            print(f"Error al establecer resultado de tarea: {e}")

    def get_task_result(self, task_id):
        """Obtener el resultado de una tarea."""
        try:
            with self.lock:
                if task_id in self.task_results:
                    return self.task_results[task_id]
                return None
        except Exception as e:
            print(f"Error al obtener resultado de tarea: {e}")
            return None

    def task_completed(self, task_id):
        """Verificar si una tarea ha sido completada."""
        try:
            with self.lock:
                if task_id in self.task_results:
                    return self.task_results[task_id]["status"] == "completed"
                return False
        except Exception as e:
            print(f"Error al verificar estado de tarea: {e}")
            return False

    def get_pending_tasks(self, agent_name):
        """Obtener tareas pendientes para un agente específico."""
        try:
            pending_tasks = []
            for task_id, task_info in self.task_results.items():
                if task_info["agent"] == agent_name and task_info["status"] == "pending":
                    pending_tasks.append(task_info)
            return pending_tasks
        except Exception as e:
            print(f"Error al obtener tareas pendientes: {e}")
            return []

    def cleanup_completed_tasks(self, max_age_hours=24):
        """Limpiar tareas completadas que sean demasiado antiguas."""
        try:
            current_time = datetime.now()
            with self.lock:
                task_ids_to_remove = []
                for task_id, task_info in self.task_results.items():
                    if task_info["status"] == "completed":
                        task_time = datetime.fromisoformat(task_info["completed_at"])
                        if (current_time - task_time).total_seconds() > max_age_hours * 3600:
                            task_ids_to_remove.append(task_id)

                for task_id in task_ids_to_remove:
                    del self.task_results[task_id]
        except Exception as e:
            print(f"Error al limpiar tareas completadas: {e}")

# Ejemplo de uso
if __name__ == "__main__":
    # Inicializar el comunicador
    communicator = AgentCommunicator()

    # Inicializar colas para los agentes
    agents = ["analytic_agent", "executor_agent", "vision_agent", "memory_agent"]
    communicator.initialize_queues(agents)

    # Ejemplo: Publicar una tarea
    task_data = {
        "description": "Analizar el tráfico de red en los últimos 7 días",
        "context": {
            "time_range": "last_7_days",
            "network_interface": "eth0"
        }
    }

    task_id = communicator.publish_task("analytic_agent", task_data)
    print(f"Tarea publicada con ID: {task_id}")

    # Ejemplo: Obtener una tarea (simular lo que haría un agente)
    task = communicator.get_task("analytic_agent")
    if task:
        print(f"Tarea obtenida: {task['description']}")
        # Procesar la tarea...
        result = {"analysis": "Tráfico de red estable con picos los viernes", "details": {...}}
        communicator.set_task_result(task_id, result)
        print(f"Resultado establecido para tarea {task_id}")

    # Ejemplo: Obtener el resultado de una tarea
    result = communicator.get_task_result(task_id)
    print(f"Resultado de tarea {task_id}: {result}")