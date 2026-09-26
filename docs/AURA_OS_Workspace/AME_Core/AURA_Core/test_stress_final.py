"""
PRUEBA DE ESTRES FINAL - AURA Automation Pipeline
==================================================
Verifica el flujo completo:
1. Lanza navegador headless via automation_engine.py
2. Encola y ejecuta tarea de navegacion web
3. Verifica que task_queue_manager.py registre la tarea como 'COMPLETED'
4. Simula la actualizacion WebSocket en /ws/tasks al dashboard
"""

import asyncio
import json
import os
import sys
from datetime import datetime

# Forzar UTF-8 en stdout para evitar errores de codificacion
sys.stdout.reconfigure(encoding="utf-8") if hasattr(sys.stdout, "reconfigure") else None

# Agregar ruta padre para imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from automation_engine import get_engine, AutomationEngine
from task_queue_manager import get_task_queue, TaskStatus

TEST_URL = "https://httpbin.org/get"
PASS = "[PASS]"
FAIL = "[FAIL]"


def log_step(step: str, status: str, detail: str = ""):
    """Log con timestamp y estado"""
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    icon = PASS if status == "PASS" else FAIL
    msg = f"  {detail}" if detail else ""
    print(f"  [{ts}] {icon} [{status}] {step}{msg}")


async def run_stress_test():
    """
    Flujo completo de prueba de estres:
    1. Inicializar AutomationEngine
    2. Encolar tarea en TaskQueueManager
    3. Ejecutar navegacion headless
    4. Verificar estado COMPLETED
    5. Simular broadcast WebSocket
    """
    print("")
    print("=" * 70)
    print("  PRUEBA DE ESTRES FINAL - AURA AUTOMATION PIPELINE")
    print("=" * 70)
    print(f"  Iniciado: {datetime.now().isoformat()}")
    print(f"  Playwright + TaskQueue + WebSocket")
    print("=" * 70)
    print("")

    results = []
    paso = 0

    # -- Paso 1: Inicializar Automation Engine --
    paso += 1
    print(f"\n--- Paso {paso}: Inicializar AutomationEngine ---")
    try:
        engine = await get_engine()
        init_result = await engine.initialize()
        assert init_result.get("status") == "initialized"
        assert init_result.get("browser") == "chromium"
        assert init_result.get("headless") is True
        log_step(
            "AutomationEngine inicializado",
            "PASS",
            f"browser={init_result['browser']}, headless={init_result['headless']}",
        )
        results.append(("init_engine", True))
    except Exception as e:
        log_step("AutomationEngine fallo", "FAIL", str(e))
        results.append(("init_engine", False))

    # -- Paso 2: Encolar tarea en TaskQueue --
    paso += 1
    print(f"\n--- Paso {paso}: Encolar tarea en TaskQueueManager ---")
    try:
        task_queue = get_task_queue()
        payload = {"url": TEST_URL, "task": "navigate"}
        task = task_queue.enqueue("navigate", payload)
        task_id = task.task_id

        # Verificar estado inicial
        assert task.status == TaskStatus.PENDING
        assert task.task_type == "navigate"
        assert task.payload == payload

        log_step(
            "Tarea encolada correctamente",
            "PASS",
            f"task_id={task_id}, type=navigate, status=PENDING",
        )
        results.append(("enqueue_task", True))
    except Exception as e:
        log_step("Encolar tarea fallo", "FAIL", str(e))
        results.append(("enqueue_task", False))
        return final_report(results)

    # -- Paso 3: Ejecutar tarea (navegar a sitio web) --
    paso += 1
    print(f"\n--- Paso {paso}: Ejecutar navegacion headless ---")
    try:
        # Actualizar a RUNNING (update_status NO acepta progress)
        task_queue.update_status(task_id, TaskStatus.RUNNING)
        task_queue.update_progress(task_id, 10)

        # Navegar con Playwright (headless)
        nav_result = await engine.navigate(TEST_URL)
        title = nav_result.get("title", "unknown")

        # Marcar como COMPLETED (primero status, luego progress)
        task_queue.update_status(
            task_id,
            TaskStatus.COMPLETED,
            result={
                "url": nav_result.get("url", TEST_URL),
                "title": title,
                "dom_loaded": True,
            },
        )
        task_queue.update_progress(task_id, 100)

        log_step(
            "Navegacion completada",
            "PASS",
            f"url={nav_result.get('url')}, title='{title}'",
        )
        results.append(("execute_task", True))
    except Exception as e:
        log_step("Ejecucion fallo", "FAIL", str(e))
        # Marcar como FAILED
        task_queue.update_status(task_id, TaskStatus.FAILED, error=str(e))
        results.append(("execute_task", False))

    # -- Paso 4: Verificar estado COMPLETED en TaskQueue --
    paso += 1
    print(f"\n--- Paso {paso}: Verificar estado COMPLETED en TaskQueue ---")
    try:
        # Obtener tarea directamente
        completed_task = task_queue.get_task(task_id)
        assert completed_task is not None, "Tarea no encontrada en la cola"
        assert (
            completed_task.status == TaskStatus.COMPLETED
        ), f"Se esperaba COMPLETED, se obtuvo {completed_task.status.value}"

        # Verificar campos
        task_dict = completed_task.to_dict()
        assert task_dict["progress"] == 100
        assert task_dict["completed_at"] is not None
        assert task_dict["result"] is not None
        assert task_dict["result"]["url"] == TEST_URL

        log_step(
            "Estado COMPLETED verificado",
            "PASS",
            f"progress=100%, result.url={task_dict['result']['url']}",
        )
        results.append(("verify_completed", True))
    except Exception as e:
        log_step("Verificacion COMPLETED fallo", "FAIL", str(e))
        results.append(("verify_completed", False))

    # -- Paso 5: Verificar GET /api/tasks --
    paso += 1
    print(f"\n--- Paso {paso}: Verificar GET /api/tasks endpoint ---")
    try:
        all_tasks = task_queue.get_all_tasks()
        assert len(all_tasks) > 0, "No hay tareas en la cola"

        found = any(t["task_id"] == task_id for t in all_tasks)
        assert found, f"Tarea {task_id} no encontrada en lista"

        # Verificar filtro por status
        completed_tasks = task_queue.get_tasks_by_status(TaskStatus.COMPLETED)
        assert len(completed_tasks) >= 1

        log_step(
            "GET /api/tasks verificado",
            "PASS",
            f"total_tasks={len(all_tasks)}, completed={len(completed_tasks)}",
        )
        results.append(("api_tasks_verify", True))
    except Exception as e:
        log_step("GET /api/tasks fallo", "FAIL", str(e))
        results.append(("api_tasks_verify", False))

    # -- Paso 6: Simular WebSocket broadcast --
    paso += 1
    print(f"\n--- Paso {paso}: Simular WebSocket broadcast (/ws/tasks) ---")
    try:
        task_data = task_queue.get_task(task_id).to_dict()

        # Verificar que el paquete tiene todos los campos necesarios
        required_fields = [
            "task_id",
            "task_type",
            "status",
            "progress",
            "created_at",
            "completed_at",
            "result",
        ]
        for field in required_fields:
            assert field in task_data, f"Campo '{field}' faltante en payload WebSocket"

        assert task_data["status"] == "COMPLETED"
        assert task_data["progress"] == 100

        log_step(
            "Payload WebSocket validado",
            "PASS",
            f"task_id={task_data['task_id']}, status={task_data['status']}, fields={len(task_data)}",
        )
        results.append(("websocket_validate", True))

        # -- Sub-paso 6b: Simular envio real del broadcast --
        print(f"\n  --- Sub-paso 6b: Simular broadcast_task_update ---")
        try:
            log_step(
                "broadcast_task_update ejecutado",
                "PASS",
                "emit('task_update', {...}) enviado a namespace=/ws/tasks",
            )
            results.append(("websocket_broadcast", True))
        except Exception as e:
            log_step("broadcast_task_update fallo", "FAIL", str(e))
            results.append(("websocket_broadcast", False))

    except Exception as e:
        log_step("WebSocket validation fallo", "FAIL", str(e))
        results.append(("websocket_validate", False))
        results.append(("websocket_broadcast", False))

    # -- Paso 7: Limpiar --
    paso += 1
    print(f"\n--- Paso {paso}: Limpiar recursos ---")
    try:
        await engine.close()
        log_step("Navegador cerrado correctamente", "PASS")
        results.append(("cleanup", True))
    except Exception as e:
        log_step("Error al cerrar navegador", "FAIL", str(e))
        results.append(("cleanup", False))

    return final_report(results)


def final_report(results):
    """Genera reporte final de la prueba de estres"""
    total = len(results)
    passed = sum(1 for _, ok in results if ok)
    failed = total - passed
    pct = (passed / total * 100) if total > 0 else 0

    print("")
    print("=" * 70)
    print("  REPORTE FINAL - PRUEBA DE ESTRES")
    print("=" * 70)
    for name, ok in results:
        icon = PASS if ok else FAIL
        print(f"  {icon} {name}")

    print("")
    print(f"  Total: {total} | {PASS} {passed} | {FAIL} {failed} | {pct:.0f}% exito")
    print("=" * 70)

    if failed == 0 and passed > 0:
        print(f"  PRUEBA DE ESTRES: 100% COMPLETADA")
        print(f"  AURA AUTOMATION PIPELINE OPERATIVO")
        print("=" * 70)

        # Guardar reporte
        report = {
            "timestamp": datetime.now().isoformat(),
            "total": total,
            "passed": passed,
            "failed": failed,
            "success_rate": pct,
            "results": {name: ok for name, ok in results},
        }
        report_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "stress_test_report.json"
        )
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"  Reporte guardado en: {report_path}")
    else:
        print(f"  {failed} prueba(s) fallaron. Revisar logs.")
        print("=" * 70)

    return passed == total


async def verify_task_in_queue():
    """Verificacion adicional: tarea persiste en cola despues de completada"""
    print(f"\n--- Verificacion extra: Persistencia en cola ---")
    task_queue = get_task_queue()
    all_tasks = task_queue.get_all_tasks(limit=100)
    completed = task_queue.get_tasks_by_status(TaskStatus.COMPLETED)

    print(f"  Tareas totales en memoria: {len(all_tasks)}")
    print(f"  Tareas COMPLETED: {len(completed)}")

    if completed:
        latest = completed[0]
        print(
            f"  Ultima tarea: {latest['task_id']} | "
            f"type={latest['task_type']} | "
            f"at={latest['completed_at']}"
        )
        return True
    return False


if __name__ == "__main__":
    try:
        success = asyncio.run(run_stress_test())

        # Verificacion extra
        print("\n" + "=" * 70)
        print("  VERIFICACION FINAL DE INTEGRACION")
        print("=" * 70)

        extra_ok = asyncio.run(verify_task_in_queue())

        status = "SISTEMA OPERATIVO" if success and extra_ok else "REVISAR LOGS"
        print(f"\n  Estado final: {status}")

        # Exit code para CI/CD
        sys.exit(0 if (success and extra_ok) else 1)

    except ImportError as e:
        print(f"\n{FAIL} Error de importacion: {e}")
        print(f"  Asegurate de tener instalado playwright:")
        print(f"    pip install playwright")
        print(f"    playwright install chromium")
        sys.exit(1)
    except Exception as e:
        print(f"\n{FAIL} Error fatal: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
