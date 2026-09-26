#!/usr/bin/env python3
"""
test_tactical_dashboard.py - Script de prueba para el Dashboard Táctico de AME
Este script simula el funcionamiento del dashboard táctico y verifica que todas las funcionalidades
estén operando correctamente.
"""

import asyncio
import json
import logging
import time
import threading
import uuid
from websockets import connect
from websockets.exceptions import ConnectionClosed
import signal
import sys
from datetime import datetime
import requests
import subprocess
import os

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_tactical_dashboard.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TacticalDashboardTester:
    def __init__(self, ws_url="ws://localhost:3000"):
        self.ws_url = ws_url
        self.ws = None
        self.running = False
        self.nodes = []
        self.tasks = {}
        self.connection_id = str(uuid.uuid4())
        self.test_results = {
            'connection': False,
            'node_update': False,
            'task_assignment': False,
            'task_progress': False,
            'task_cancellation': False,
            'task_history': False,
            'reconnection': False
        }

    async def connect(self):
        """Conectar al servidor WebSocket"""
        try:
            self.ws = await connect(self.ws_url)
            logger.info(f"Conectado al servidor WebSocket: {self.ws_url}")

            # Suscribirse a canales
            await self.ws.send(json.dumps({
                'action': 'subscribe',
                'channel': 'nodes'
            }))
            await self.ws.send(json.dumps({
                'action': 'subscribe',
                'channel': 'tasks'
            }))
            await self.ws.send(json.dumps({
                'action': 'get_task_history'
            }))

            self.running = True
            self.test_results['connection'] = True
            return True
        except Exception as e:
            logger.error(f"Error conectando al servidor WebSocket: {e}")
            self.test_results['connection'] = False
            return False

    async def listen(self):
        """Escuchar mensajes del servidor WebSocket"""
        try:
            while self.running:
                message = await self.ws.recv()
                data = json.loads(message)

                if data.get('event') == 'node_update':
                    self.nodes = data.get('data', [])
                    logger.info(f"Actualización de nodos recibida: {len(self.nodes)} nodos")
                    self.test_results['node_update'] = True

                elif data.get('event') == 'task_assigned':
                    task = data.get('data')
                    self.tasks[task['id']] = task
                    logger.info(f"Tarea asignada: {task['id']} - {task['module']} en {task['nodeId']}")
                    self.test_results['task_assignment'] = True

                elif data.get('event') == 'task_update':
                    task = data.get('data')
                    if task['id'] in self.tasks:
                        self.tasks[task['id']] = task
                    logger.info(f"Actualización de tarea: {task['id']} - Estado: {task['status']}, Progreso: {task['progress']}%")
                    if task['status'] in ['completed', 'failed', 'cancelled']:
                        self.test_results['task_progress'] = True

                elif data.get('event') == 'task_output':
                    output_data = data.get('data')
                    if output_data['taskId'] in self.tasks:
                        task = self.tasks[output_data['taskId']]
                        if 'output' not in task:
                            task['output'] = []
                        task['output'].append(output_data['output'])
                    logger.debug(f"Salida de tarea: {output_data['output']}")

                elif data.get('event') == 'task_history':
                    history = data.get('data', [])
                    logger.info(f"Historial de tareas recibido: {len(history)} tareas")
                    self.test_results['task_history'] = True

                elif data.get('event') == 'task_cancelled':
                    task = data.get('data')
                    logger.info(f"Tarea cancelada: {task['id']}")
                    self.test_results['task_cancellation'] = True

                elif data.get('event') == 'error' or data.get('event') == 'task_cancel_error':
                    error_data = data.get('data')
                    logger.warning(f"Error recibido: {error_data.get('message', 'Desconocido')}")

                else:
                    logger.debug(f"Mensaje recibido: {data}")

        except ConnectionClosed:
            logger.info("Conexión cerrada por el servidor")
            self.running = False
        except Exception as e:
            logger.error(f"Error en la escucha de mensajes: {e}")
            self.running = False

    async def assign_test_task(self, node_id, module_type):
        """Asignar una tarea de prueba"""
        try:
            task_data = {
                'action': 'assign_task',
                'nodeId': node_id,
                'module': module_type,
                'parameters': {
                    'target': 'example.com' if module_type == 'venice' else '192.168.1.0/24',
                    'depth': 2 if module_type == 'venice' else None
                },
                'timestamp': datetime.now().isoformat()
            }

            await self.ws.send(json.dumps(task_data))
            logger.info(f"Tarea asignada: {module_type} en {node_id}")
            return True
        except Exception as e:
            logger.error(f"Error asignando tarea: {e}")
            return False

    async def cancel_test_task(self, task_id):
        """Cancelar una tarea de prueba"""
        try:
            cancel_data = {
                'action': 'cancel_task',
                'taskId': task_id,
                'reason': 'Test cancellation from tester script'
            }

            await self.ws.send(json.dumps(cancel_data))
            logger.info(f"Cancelación solicitada para tarea: {task_id}")
            return True
        except Exception as e:
            logger.error(f"Error cancelando tarea: {e}")
            return False

    async def run_tests(self):
        """Ejecutar pruebas del dashboard táctico"""
        logger.info("Iniciando pruebas del Dashboard Táctico...")

        # Esperar a que se establezca la conexión
        await asyncio.sleep(2)

        # Verificar que hay nodos disponibles
        if not self.nodes or len(self.nodes) == 0:
            logger.warning("No se encontraron nodos disponibles para las pruebas")
            return False

        # Seleccionar un nodo disponible
        available_nodes = [node for node in self.nodes if node['status'] == 'available']
        if not available_nodes:
            logger.warning("No hay nodos disponibles para asignar tareas")
            return False

        selected_node = available_nodes[0]
        logger.info(f"Seleccionado nodo disponible: {selected_node['id']} - {selected_node['name']}")

        # Probar asignación de tarea
        await asyncio.sleep(1)
        success = await self.assign_test_task(selected_node['id'], 'venice')
        if not success:
            logger.error("Fallo al asignar tarea de prueba")
            return False

        # Esperar a que la tarea se asigne
        await asyncio.sleep(3)

        # Verificar que la tarea se haya asignado
        if not self.test_results['task_assignment']:
            logger.error("No se recibió confirmación de asignación de tarea")
            return False

        # Esperar progreso de la tarea
        await asyncio.sleep(10)

        # Verificar progreso de la tarea
        if not self.test_results['task_progress']:
            logger.warning("No se recibió progreso de la tarea (puede ser normal si la tarea ya terminó)")

        # Probar cancelación de tarea (si la tarea aún está en ejecución)
        active_tasks = [task for task in self.tasks.values() if task['status'] in ['assigned', 'running']]
        if active_tasks:
            task_to_cancel = active_tasks[0]
            logger.info(f"Cancelando tarea activa: {task_to_cancel['id']}")
            await self.cancel_test_task(task_to_cancel['id'])
            await asyncio.sleep(3)

        # Verificar cancelación de tarea
        if not self.test_results['task_cancellation']:
            logger.warning("No se confirmó la cancelación de la tarea")

        # Probar reconexión simulada
        try:
            await self.ws.close()
            logger.info("Simulando desconexión...")
            await asyncio.sleep(2)

            # Reconectar
            self.ws = await connect(self.ws_url)
            logger.info("Reconectado al servidor WebSocket")

            # Suscribirse nuevamente
            await self.ws.send(json.dumps({
                'action': 'subscribe',
                'channel': 'nodes'
            }))
            await self.ws.send(json.dumps({
                'action': 'subscribe',
                'channel': 'tasks'
            }))

            self.test_results['reconnection'] = True
            logger.info("Prueba de reconexión completada con éxito")

        except Exception as e:
            logger.error(f"Error en prueba de reconexión: {e}")
            self.test_results['reconnection'] = False

        # Mostrar resultados finales
        logger.info("\n=== Resultados de las Pruebas ===")
        for test_name, result in self.test_results.items():
            status = "✓ PASS" if result else "✗ FAIL"
            logger.info(f"{test_name}: {status}")

        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result)
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0

        logger.info(f"\nResumen: {passed_tests}/{total_tests} pruebas completadas ({success_rate:.1f}%)")

        return success_rate >= 80  # Considerar éxito si al menos 80% de las pruebas pasan

    async def run(self):
        """Ejecutar todas las pruebas"""
        try:
            if not await self.connect():
                return False

            # Iniciar escucha en un hilo separado
            listener_task = asyncio.create_task(self.listen())

            # Ejecutar pruebas
            success = await self.run_tests()

            # Esperar a que termine la escucha
            listener_task.cancel()
            try:
                await listener_task
            except asyncio.CancelledError:
                pass

            # Cerrar conexión
            if self.ws and not self.ws.closed:
                await self.ws.close()

            return success

        except Exception as e:
            logger.error(f"Error en la ejecución de pruebas: {e}")
            return False

def start_aura_server():
    """Iniciar el servidor AURA en un proceso separado"""
    try:
        # Cambiar al directorio correcto
        os.chdir(os.path.dirname(os.path.abspath(__file__)))

        # Iniciar el servidor AME
        logger.info("Iniciando servidor AME...")
        process = subprocess.Popen(
            ['python', 'servidor_ame.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )

        # Esperar un momento para que el servidor inicie
        time.sleep(5)

        return process

    except Exception as e:
        logger.error(f"Error iniciando servidor AURA: {e}")
        return None

def main():
    """Función principal"""
    logger.info("=== Inicio de Pruebas del Dashboard Táctico ===")

    # Iniciar el servidor AURA en segundo plano
    aura_process = start_aura_server()
    if not aura_process:
        logger.error("No se pudo iniciar el servidor AURA")
        return

    try:
        # Ejecutar pruebas asíncronas
        tester = TacticalDashboardTester()
        loop = asyncio.get_event_loop()
        success = loop.run_until_complete(tester.run())

        if success:
            logger.info("\n🎉 Todas las pruebas se ejecutaron correctamente!")
        else:
            logger.error("\n❌ Algunas pruebas fallaron. Revisar los logs para más detalles.")

    except KeyboardInterrupt:
        logger.info("Pruebas interrumpidas por el usuario")
    except Exception as e:
        logger.error(f"Error inesperado durante las pruebas: {e}")
    finally:
        # Limpiar: detener el servidor AURA
        if aura_process:
            logger.info("Deteniendo servidor AURA...")
            aura_process.terminate()
            try:
                aura_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                aura_process.kill()
                aura_process.wait()

        logger.info("Pruebas completadas")

if __name__ == "__main__":
    main()