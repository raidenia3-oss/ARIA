#!/usr/bin/env python3
"""
task_scheduler.py - Motor de tareas internalizado con SQLite (Honker-Style)
Este módulo implementa una cola de tareas persistente en SQLite sin depender de brokers externos.
Usa un bucle en segundo plano que lee eventos pendientes de una tabla de eventos.
"""

import os
import sys
import sqlite3
import json
import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('task_scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("TaskScheduler")

class SQLiteTaskScheduler:
    """
    Motor de tareas internalizado con SQLite.
    Implementa una cola de tareas persistente sin depender de brokers externos.
    """

    def __init__(self, db_path: str = "aura_tasks.db"):
        self.db_path = db_path
        self.lock = threading.Lock()
        self.running = False
        self.shutdown_event = threading.Event()
        self._initialize_database()

    def _initialize_database(self):
        """Inicializa la base de datos SQLite con las tablas necesarias."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Crear tabla de tareas
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    task_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    assigned_node TEXT,
                    assigned_at TEXT,
                    parameters TEXT,
                    result TEXT,
                    error TEXT,
                    completed_at TEXT,
                    failed_at TEXT,
                    retries INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    metadata TEXT
                )
            """)

            # Crear tabla de nodos
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS nodes (
                    node_id TEXT PRIMARY KEY,
                    capabilities TEXT NOT NULL,
                    last_heartbeat TEXT,
                    status TEXT DEFAULT 'online'
                )
            """)

            # Crear tabla de eventos (para Pub/Sub)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    processed_at TEXT,
                    status TEXT DEFAULT 'pending'
                )
            """)

            # Crear índices para mejor rendimiento
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_status ON events(status)")

            conn.commit()

    def _get_db_connection(self):
        """Obtiene una conexión a la base de datos con manejo de errores."""
        try:
            return sqlite3.connect(self.db_path)
        except sqlite3.Error as e:
            logger.error(f"Error al conectar a la base de datos: {e}")
            return None

    def add_task(self, task_type: str, parameters: Dict, priority: int = 2,
                 metadata: Optional[Dict] = None) -> str:
        """
        Añade una nueva tarea a la cola.

        Args:
            task_type: Tipo de tarea (ej: "OSINT_SCAN", "SCAN_WIFI")
            parameters: Parámetros de la tarea como diccionario
            priority: Prioridad (1=alta, 2=media, 3=baja)
            metadata: Metadatos adicionales

        Returns:
            ID de la tarea creada
        """
        task_id = f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}_{os.urandom(4).hex()}"

        with self.lock:
            conn = self._get_db_connection()
            if not conn:
                return None

            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO tasks (
                        id, task_type, status, priority, created_at,
                        parameters, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    task_id,
                    task_type,
                    "pending",
                    priority,
                    datetime.now().isoformat(),
                    json.dumps(parameters),
                    json.dumps(metadata or {})
                ))
                conn.commit()
                logger.info(f"Tarea añadida: {task_id} ({task_type})")
                return task_id
            except sqlite3.Error as e:
                logger.error(f"Error al añadir tarea {task_id}: {e}")
                return None
            finally:
                conn.close()

    def get_pending_tasks(self, limit: int = 10) -> List[Dict]:
        """
        Obtiene tareas pendientes ordenadas por prioridad.

        Args:
            limit: Número máximo de tareas a devolver

        Returns:
            Lista de tareas pendientes
        """
        with self.lock:
            conn = self._get_db_connection()
            if not conn:
                return []

            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, task_type, parameters, priority, created_at, metadata
                    FROM tasks
                    WHERE status = 'pending'
                    ORDER BY priority ASC, created_at ASC
                    LIMIT ?
                """, (limit,))

                tasks = []
                for row in cursor.fetchall():
                    task_id, task_type, parameters, priority, created_at, metadata = row
                    tasks.append({
                        "id": task_id,
                        "type": task_type,
                        "parameters": json.loads(parameters),
                        "priority": priority,
                        "created_at": created_at,
                        "metadata": json.loads(metadata)
                    })
                return tasks
            except sqlite3.Error as e:
                logger.error(f"Error al obtener tareas pendientes: {e}")
                return []
            finally:
                conn.close()

    def update_task_status(self, task_id: str, status: str, result: Optional[Dict] = None,
                          error: Optional[str] = None, node_id: Optional[str] = None):
        """
        Actualiza el estado de una tarea.

        Args:
            task_id: ID de la tarea
            status: Nuevo estado ("pending", "assigned", "completed", "failed", "cancelled")
            result: Resultado de la tarea (opcional)
            error: Error ocurrido (opcional)
            node_id: Nodo asignado (opcional)
        """
        with self.lock:
            conn = self._get_db_connection()
            if not conn:
                return

            try:
                cursor = conn.cursor()

                # Actualizar estado básico
                cursor.execute("""
                    UPDATE tasks
                    SET status = ?, assigned_node = ?, assigned_at = ?
                    WHERE id = ?
                """, (
                    status,
                    node_id,
                    datetime.now().isoformat() if node_id else None,
                    task_id
                ))

                # Actualizar resultado o error según corresponda
                if status == "completed" and result:
                    cursor.execute("""
                        UPDATE tasks
                        SET result = ?, completed_at = ?
                        WHERE id = ?
                    """, (
                        json.dumps(result),
                        datetime.now().isoformat(),
                        task_id
                    ))
                elif status == "failed" and error:
                    cursor.execute("""
                        UPDATE tasks
                        SET error = ?, failed_at = ?, retries = retries + 1
                        WHERE id = ?
                    """, (
                        error,
                        datetime.now().isoformat(),
                        task_id
                    ))

                conn.commit()
                logger.info(f"Estado de tarea {task_id} actualizado a: {status}")
            except sqlite3.Error as e:
                logger.error(f"Error al actualizar estado de tarea {task_id}: {e}")
            finally:
                conn.close()

    def add_node(self, node_id: str, capabilities: List[str]):
        """
        Registra un nuevo nodo en el sistema.

        Args:
            node_id: Identificador único del nodo
            capabilities: Lista de capacidades del nodo
        """
        with self.lock:
            conn = self._get_db_connection()
            if not conn:
                return

            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO nodes (node_id, capabilities, last_heartbeat, status)
                    VALUES (?, ?, ?, ?)
                """, (
                    node_id,
                    json.dumps(capabilities),
                    datetime.now().isoformat(),
                    "online"
                ))
                conn.commit()
                logger.info(f"Nodo registrado: {node_id}")
            except sqlite3.Error as e:
                logger.error(f"Error al registrar nodo {node_id}: {e}")
            finally:
                conn.close()

    def get_available_nodes(self, required_capabilities: List[str]) -> List[str]:
        """
        Obtiene nodos disponibles que cumplen con las capacidades requeridas.

        Args:
            required_capabilities: Capacidades requeridas para la tarea

        Returns:
            Lista de IDs de nodos disponibles
        """
        with self.lock:
            conn = self._get_db_connection()
            if not conn:
                return []

            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT node_id, capabilities
                    FROM nodes
                    WHERE status = 'online'
                """)

                nodes = []
                for node_id, capabilities_json in cursor.fetchall():
                    try:
                        node_caps = json.loads(capabilities_json)
                        # Verificar si el nodo tiene todas las capacidades requeridas
                        if all(cap in node_caps for cap in required_capabilities):
                            nodes.append(node_id)
                    except json.JSONDecodeError:
                        logger.warning(f"Capacidades inválidas para nodo {node_id}")
                        continue

                return nodes
            except sqlite3.Error as e:
                logger.error(f"Error al obtener nodos disponibles: {e}")
                return []
            finally:
                conn.close()

    def add_event(self, event_type: str, payload: Dict) -> str:
        """
        Añade un evento al sistema de Pub/Sub.

        Args:
            event_type: Tipo de evento (ej: "task_completed", "node_heartbeat")
            payload: Payload del evento

        Returns:
            ID del evento creado
        """
        event_id = f"event_{datetime.now().strftime('%Y%m%d%H%M%S')}_{os.urandom(4).hex()}"

        with self.lock:
            conn = self._get_db_connection()
            if not conn:
                return None

            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO events (id, event_type, payload, created_at)
                    VALUES (?, ?, ?, ?)
                """, (
                    event_id,
                    event_type,
                    json.dumps(payload),
                    datetime.now().isoformat()
                ))
                conn.commit()
                logger.info(f"Evento añadido: {event_id} ({event_type})")
                return event_id
            except sqlite3.Error as e:
                logger.error(f"Error al añadir evento {event_id}: {e}")
                return None
            finally:
                conn.close()

    def process_events(self, limit: int = 10):
        """
        Procesa eventos pendientes del sistema Pub/Sub.

        Args:
            limit: Número máximo de eventos a procesar
        """
        with self.lock:
            conn = self._get_db_connection()
            if not conn:
                return

            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, event_type, payload
                    FROM events
                    WHERE status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT ?
                """, (limit,))

                for event_id, event_type, payload in cursor.fetchall():
                    try:
                        # Aquí iría la lógica de procesamiento del evento
                        # Por ejemplo: notificar a otros componentes, actualizar estado, etc.
                        logger.info(f"Procesando evento {event_id}: {event_type}")

                        # Marcar como procesado
                        cursor.execute("""
                            UPDATE events
                            SET status = ?, processed_at = ?
                            WHERE id = ?
                        """, (
                            "processed",
                            datetime.now().isoformat(),
                            event_id
                        ))

                    except Exception as e:
                        logger.error(f"Error al procesar evento {event_id}: {e}")
                        cursor.execute("""
                            UPDATE events
                            SET status = ?, error = ?
                            WHERE id = ?
                        """, (
                            "failed",
                            str(e),
                            event_id
                        ))

                conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Error al procesar eventos: {e}")
            finally:
                conn.close()

    def _worker_loop(self):
        """Bucle de trabajo principal que procesa tareas y eventos."""
        while not self.shutdown_event.is_set():
            try:
                # Procesar tareas pendientes
                pending_tasks = self.get_pending_tasks(5)
                for task in pending_tasks:
                    try:
                        # Aquí iría la lógica de asignación y ejecución de la tarea
                        # Por simplicidad, solo marcamos como asignada
                        self.update_task_status(
                            task["id"],
                            "assigned",
                            node_id="node_001"  # Asignar a un nodo disponible
                        )
                        logger.info(f"Tarea {task['id']} asignada a ejecución")
                    except Exception as e:
                        logger.error(f"Error al procesar tarea {task['id']}: {e}")
                        self.update_task_status(
                            task["id"],
                            "failed",
                            error=str(e)
                        )

                # Procesar eventos
                self.process_events(5)

                # Esperar antes de la próxima iteración
                time.sleep(1)

            except Exception as e:
                logger.error(f"Error en el bucle de trabajo: {e}")
                time.sleep(5)  # Esperar más tiempo si hay errores

    def start(self):
        """Inicia el scheduler en un hilo de fondo."""
        if not self.running:
            self.running = True
            self.shutdown_event.clear()
            self.worker_thread = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name="TaskSchedulerWorker"
            )
            self.worker_thread.start()
            logger.info("Scheduler de tareas iniciado")

    def stop(self):
        """Detiene el scheduler."""
        if self.running:
            self.running = False
            self.shutdown_event.set()
            if hasattr(self, 'worker_thread'):
                self.worker_thread.join(timeout=5)
            logger.info("Scheduler de tareas detenido")

def main():
    """Punto de entrada principal."""
    import argparse

    parser = argparse.ArgumentParser(description="Motor de tareas internalizado con SQLite")
    parser.add_argument("--db", help="Ruta a la base de datos SQLite", default="aura_tasks.db")
    parser.add_argument("--start", action="store_true", help="Iniciar el scheduler en segundo plano")
    parser.add_argument("--stop", action="store_true", help="Detener el scheduler")
    parser.add_argument("--add-task", help="Añadir una nueva tarea (ej: 'OSINT_SCAN {\"target\": \"example.com\"}')")
    args = parser.parse_args()

    scheduler = SQLiteTaskScheduler(db_path=args.db)

    if args.start:
        scheduler.start()
        print("Scheduler iniciado. Presione Ctrl+C para detener.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            scheduler.stop()
    elif args.stop:
        scheduler.stop()
    elif args.add_task:
        try:
            # Parsear los argumentos de la tarea
            import json
            import re

            # Extraer el tipo de tarea y los parámetros
            match = re.match(r'(\w+)\s+(.*)', args.add_task)
            if not match:
                print("Formato incorrecto. Ejemplo: 'OSINT_SCAN {\"target\": \"example.com\"}'")
                return

            task_type = match.group(1)
            params_str = match.group(2)

            # Parsear los parámetros como JSON
            try:
                parameters = json.loads(params_str)
            except json.JSONDecodeError:
                print("Error al parsear los parámetros JSON")
                return

            # Añadir la tarea
            task_id = scheduler.add_task(task_type, parameters)
            if task_id:
                print(f"Tarea añadida con éxito. ID: {task_id}")
            else:
                print("Error al añadir la tarea")
        except Exception as e:
            print(f"Error: {e}")
    else:
        print("Uso:")
        print("  python task_scheduler.py --start       # Iniciar scheduler")
        print("  python task_scheduler.py --stop        # Detener scheduler")
        print("  python task_scheduler.py --add-task 'TASK_TYPE {\"param\": \"value\"}'")

if __name__ == "__main__":
    main()