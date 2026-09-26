#!/usr/bin/env python3
"""
task_manager.py - JARVIS Micro-Task & Goal System (FASE 30)
Gestor de cola de tareas para objetivos dinámicos de AURA y sus bots.
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime

logger = logging.getLogger("JARVIS_TaskManager")


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class Task:
    """Representa un micro-objetivo en la cola de JARVIS."""

    def __init__(self, task_id: str, task_type: str, payload: Dict[str, Any] = None):
        self.task_id = task_id
        self.task_type = task_type
        self.payload = payload or {}
        self.status = TaskStatus.PENDING
        self.created_at = datetime.now().isoformat()
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None
        self.result: Optional[Any] = None
        self.error: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "payload": self.payload,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
        }


class TaskManager:
    """
    Gestor de cola de tareas para JARVIS.
    - Bucle asíncrono de control continuo.
    - Operaciones: add_task, remove_task, show_tasks, quit_task.
    - Integración con Chronos y bots.
    - Sincronización con Nexus para HUD.
    """

    def __init__(self, nexus_ref=None):
        self.tasks: List[Task] = []
        self.running = False
        self.current_task: Optional[Task] = None
        self.nexus = nexus_ref
        self._task_counter = 0

    def _generate_task_id(self) -> str:
        self._task_counter += 1
        return f"task_{int(time.time())}_{self._task_counter}"

    def add_task(self, task_type: str, payload: Dict[str, Any] = None) -> Task:
        """
        Añade un nuevo objetivo a la cola.
        Ejemplos: "ejecutar_minijuego_rollercoin", "extraer_balance_ame"
        """
        task_id = self._generate_task_id()
        task = Task(task_id, task_type, payload)
        self.tasks.append(task)
        logger.info(f"[ADD_TASK] {task_type} -> {task_id}")
        self._sync_to_nexus()
        return task

    def remove_task(self, task_id: str) -> bool:
        """Elimina/completa una tarea por ID."""
        for i, task in enumerate(self.tasks):
            if task.task_id == task_id:
                removed = self.tasks.pop(i)
                logger.info(f"[REMOVE_TASK] {removed.task_type} ({task_id}) eliminada.")
                self._sync_to_nexus()
                return True
        logger.warning(f"[REMOVE_TASK] Tarea {task_id} no encontrada.")
        return False

    def show_tasks(self) -> List[Dict]:
        """Muestra el estado actual de la cola."""
        return [task.to_dict() for task in self.tasks]

    def quit_task(self, task_id: str) -> bool:
        """Aborta una tarea en ejecución o pendiente."""
        for task in self.tasks:
            if task.task_id == task_id:
                if task.status == TaskStatus.RUNNING:
                    task.status = TaskStatus.ABORTED
                    task.completed_at = datetime.now().isoformat()
                    task.error = "Aborted by user/system"
                    logger.info(f"[QUIT_TASK] Tarea en ejecución abortada: {task_id}")
                elif task.status == TaskStatus.PENDING:
                    task.status = TaskStatus.ABORTED
                    task.completed_at = datetime.now().isoformat()
                    logger.info(f"[QUIT_TASK] Tarea pendiente abortada: {task_id}")
                self._sync_to_nexus()
                return True
        return False

    async def _execute_task(self, task: Task):
        """Ejecuta una tarea individual (lógica de bot/Chronos)."""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now().isoformat()
        logger.info(f"[EXECUTE] Iniciando {task.task_type} ({task.task_id})")
        self._sync_to_nexus()

        try:
            # Aquí se invocaría la lógica específica del bot/Chronos
            # Por ahora, simulamos ejecución
            await self._dispatch_to_bot(task)
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now().isoformat()
            task.result = {"status": "success"}
            logger.info(f"[EXECUTE] Completada {task.task_type} ({task.task_id})")
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now().isoformat()
            task.error = str(e)
            logger.error(f"[EXECUTE] Fallo en {task.task_type} ({task.task_id}): {e}")
        finally:
            self.current_task = None
            self._sync_to_nexus()

    async def _dispatch_to_bot(self, task: Task):
        """
        Despacha la tarea al módulo correspondiente.
        Integración con Chronos, bots de automatización, etc.
        """
        # Mapeo de tipos de tarea a módulos
        task_handlers = {
            "ejecutar_minijuego_rollercoin": self._handle_rollercoin,
            "extraer_balance_ame": self._handle_ame_balance,
            "scan_osint": self._handle_osint_scan,
            "deploy_apk": self._handle_deploy_apk,
        }

        handler = task_handlers.get(task.task_type)
        if handler:
            await handler(task.payload)
        else:
            # Tarea genérica: simular ejecución
            await asyncio.sleep(0.5)
            logger.info(f"[DISPATCH] Tarea genérica ejecutada: {task.task_type}")

    async def _handle_rollercoin(self, payload: Dict):
        """Handler para tareas de Rollercoin."""
        logger.info(f"[ROLLERCOIN] Ejecutando minijuego con payload: {payload}")
        # Importar módulo de rollercoin si existe
        try:
            from automation.rollercoin_bot import execute_game

            await execute_game(payload)
        except ImportError:
            logger.warning("[ROLLERCOIN] Módulo no disponible, simulación.")
            await asyncio.sleep(1)

    async def _handle_ame_balance(self, payload: Dict):
        """Handler para extracción de balance AME."""
        logger.info(f"[AME_BALANCE] Extrayendo balance: {payload}")
        try:
            from AURA_Core.ame_client import get_balance

            result = await get_balance(payload)
            return result
        except ImportError:
            logger.warning("[AME_BALANCE] Cliente AME no disponible.")
            await asyncio.sleep(0.5)

    async def _handle_osint_scan(self, payload: Dict):
        """Handler para escaneo OSINT."""
        logger.info(f"[OSINT_SCAN] Iniciando escaneo: {payload}")
        try:
            from AURA_Core.osint_engine import run_scan

            await run_scan(payload)
        except ImportError:
            logger.warning("[OSINT_SCAN] Motor OSINT no disponible.")
            await asyncio.sleep(1)

    async def _handle_deploy_apk(self, payload: Dict):
        """Handler para despliegue de APK."""
        logger.info(f"[DEPLOY_APK] Desplegando APK: {payload}")
        await asyncio.sleep(1)

    async def start(self):
        """Inicia el bucle asíncrono de control continuo."""
        self.running = True
        logger.info("[TASK_MANAGER] Iniciando bucle de control...")
        self._sync_to_nexus()

        while self.running:
            try:
                # Procesar siguiente tarea pendiente si no hay ninguna en ejecución
                if self.current_task is None:
                    pending_tasks = [t for t in self.tasks if t.status == TaskStatus.PENDING]
                    if pending_tasks:
                        self.current_task = pending_tasks[0]
                        await self._execute_task(self.current_task)
                    else:
                        # No hay tareas, esperar
                        await asyncio.sleep(0.5)
                else:
                    # Hay tarea en ejecución, esperar
                    await asyncio.sleep(0.5)

                # Telemetría hacia Nexus cada ciclo
                self._sync_to_nexus()

            except asyncio.CancelledError:
                logger.info("[TASK_MANAGER] Bucle cancelado.")
                break
            except Exception as e:
                logger.error(f"[TASK_MANAGER] Error en bucle: {e}")
                await asyncio.sleep(1)

    def stop(self):
        """Detiene el gestor de tareas."""
        self.running = False
        logger.info("[TASK_MANAGER] Deteniendo...")

    def _sync_to_nexus(self):
        """
        Sincroniza la lista de tareas con el estado global de Nexus.
        Permite que el HUD de JARVIS renderice la lista en tiempo real.
        """
        if self.nexus is None:
            return

        try:
            nexus_state = {
                "task_queue": self.show_tasks(),
                "current_task": self.current_task.to_dict() if self.current_task else None,
                "total_pending": len([t for t in self.tasks if t.status == TaskStatus.PENDING]),
                "total_running": len([t for t in self.tasks if t.status == TaskStatus.RUNNING]),
                "total_completed": len([t for t in self.tasks if t.status == TaskStatus.COMPLETED]),
                "timestamp": datetime.now().isoformat(),
            }
            # Nexus puede exponer un método update_task_state o similar
            if hasattr(self.nexus, "update_task_state"):
                self.nexus.update_task_state(nexus_state)
            elif hasattr(self.nexus, "task_queue"):
                self.nexus.task_queue = nexus_state
            else:
                # Fallback: almacenar en atributo genérico
                setattr(self.nexus, "_jarvis_task_state", nexus_state)
        except Exception as e:
            logger.error(f"[TASK_MANAGER] Error sincronizando con Nexus: {e}")


# ============================================================
# INTEGRACIÓN CON CHRONOS
# ============================================================


class ChronosTaskInjector:
    """
    Permite que Chronos inyecte tareas dinámicamente en el TaskManager.
    Ejemplo de uso:
        injector = ChronosTaskInjector(task_manager)
        injector.inject("ejecutar_minijuego_rollercoin", {"user": "test"})
    """

    def __init__(self, task_manager: TaskManager):
        self.task_manager = task_manager

    def inject(self, task_type: str, payload: Dict[str, Any] = None) -> Task:
        """Inyecta una tarea desde Chronos o cualquier módulo externo."""
        logger.info(f"[CHRONOS_INJECT] Inyectando tarea: {task_type}")
        return self.task_manager.add_task(task_type, payload)


# ============================================================
# EJECUCIÓN STANDALONE
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    # Crear gestor sin Nexus (modo standalone)
    manager = TaskManager()
    loop = asyncio.get_event_loop()

    # Ejemplo de tareas
    manager.add_task("ejecutar_minijuego_rollercoin", {"mode": "auto"})
    manager.add_task("extraer_balance_ame", {"account": "primary"})
    manager.add_task("scan_osint", {"target": "192.168.1.0/24"})
    manager.add_task("deploy_apk", {"environment": "debug"})

    # Mostrar cola inicial
    print("\n=== COLA DE TAREAS INICIAL ===")
    for t in manager.show_tasks():
        print(f"- {t['task_id']}: {t['task_type']} [{t['status']}]")

    try:
        loop.run_until_complete(manager.start())
    except KeyboardInterrupt:
        manager.stop()
        print("\n[SHUTDOWN] Gestor de tareas detenido.")
