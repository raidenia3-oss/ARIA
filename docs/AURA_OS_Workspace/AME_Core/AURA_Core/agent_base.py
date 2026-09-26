#!/usr/bin/env python3
"""
Agent Base para AURA.
Módulo base que los agentes especializados pueden heredar para facilitar la comunicación y el manejo de tareas.
"""

import os
import json
import time
import uuid
import redis
from datetime import datetime
import jsonpickle
import threading
from flask import Flask, request, jsonify

class AgentBase:
    def __init__(self, name, communicator=None):
        self.name = name
        self.communicator = communicator or AgentCommunicator()
        self.app = Flask(f"{name}_agent")
        self.task_queue = f"task_queue:{name}"
        self.setup_routes()

    def setup_routes(self):
        """Configurar rutas para el agente."""
        @self.app.route('/api/agent/task', methods=['POST'])
        def handle_task():
            """Manejar una tarea recibida."""
            data = request.get_json()
            if not data or 'task_id' not in data or 'description' not in data:
                return jsonify({"status": "error", "message": "ID de tarea y descripción requeridos"}), 400

            task_id = data['task_id']
            description = data['description']
            context = data.get('context', {})

            try:
                # Procesar la tarea
                result = self.process_task(description, context)

                # Establecer el resultado en el comunicador
                self.communicator.set_task_result(task_id, result)

                return jsonify({"status": "ok", "message": "Tarea procesada correctamente"})
            except Exception as e:
                error_result = {"status": "error", "message": str(e)}
                self.communicator.set_task_result(task_id, error_result)
                return jsonify({"status": "error", "message": f"Error al procesar tarea: {str(e)}"}), 500

    def process_task(self, description, context):
        """Procesar una tarea específica."""
        # Implementación base: solo devuelve un mensaje de que la tarea fue procesada
        return {
            "status": "processed",
            "description": description,
            "context": context,
            "result": f"Tarea '{description}' procesada por {self.name}",
            "timestamp": datetime.now().isoformat()
        }

    def run(self, host='0.0.0.0', port=None):
        """Iniciar el agente."""
        if not port:
            port = 5000 + list(self.communicator.task_queues.keys()).index(self.name.split('_')[0]) if self.name.split('_')[0] in self.communicator.task_queues else 5011

        # Iniciar el servidor Flask en un hilo separado
        threading.Thread(target=self.app.run, kwargs={'host': host, 'port': port, 'debug': False}).start()
        print(f"🚀 Agente {self.name} iniciado en el puerto {port}")

        # Escuchar tareas en segundo plano
        self.listen_for_tasks()

    def listen_for_tasks(self):
        """Escuchar tareas en la cola del agente."""
        while True:
            try:
                task_data = self.communicator.get_task(self.name)
                if task_data:
                    print(f"📥 {self.name} recibió tarea: {task_data['description']}")
                    # Procesar la tarea usando el endpoint
                    response = self.app.test_client().post(
                        '/api/agent/task',
                        json=task_data
                    )
                    if response.status_code == 200:
                        print(f"✅ {self.name} procesó tarea {task_data['task_id']}")
                    else:
                        print(f"❌ {self.name} falló al procesar tarea {task_data['task_id']}: {response.data}")
            except Exception as e:
                print(f"Error al escuchar tareas para {self.name}: {e}")
                time.sleep(1)

class AgentCommunicator:
    """Comunicador entre agentes usando Redis."""
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

    # Ejemplo: Crear un agente base
    class ExampleAgent(AgentBase):
        def __init__(self, name, communicator):
            super().__init__(name, communicator)

        def process_task(self, description, context):
            """Procesar una tarea específica."""
            return {
                "status": "processed",
                "description": description,
                "context": context,
                "result": f"Ejemplo de resultado para la tarea: '{description}'",
                "agent": self.name,
                "timestamp": datetime.now().isoformat()
            }

    # Crear y ejecutar un agente de ejemplo
    example_agent = ExampleAgent("example_agent", communicator)
    example_agent.run(host='0.0.0.0', port=5011)