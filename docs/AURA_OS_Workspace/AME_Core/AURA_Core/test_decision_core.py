"""
Script de prueba para Decision Core
Ejecuta validaciones básicas del sistema de decisión
"""

import sys
import os
import time
import json
from datetime import datetime

# Añadir directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Prueba que todos los módulos se importan correctamente"""
    print("=== Prueba 1: Importación de módulos ===")
    try:
        from decision_core import DecisionCore, TaskPriority
        print("✓ DecisionCore importado correctamente")
        print("✓ TaskPriority importado correctamente")
        return True
    except ImportError as e:
        print(f"✗ Error al importar: {e}")
        return False

def test_initialization():
    """Prueba la inicialización del Decision Core"""
    print("\n=== Prueba 2: Inicialización ===")
    try:
        from decision_core import DecisionCore, TaskPriority
        
        # Crear instancia
        core = DecisionCore()
        print("✓ DecisionCore instanciado correctamente")
        
        # Verificar estado inicial
        status = core.get_status()
        assert status["state"] == "INITIALIZING", f"Estado inicial incorrecto: {status['state']}"
        print(f"✓ Estado inicial correcto: {status['state']}")
        
        # Verificar métricas iniciales
        metrics = core.get_metrics()
        assert metrics["tasks_processed"] == 0, "Contador de tareas inicial incorrecto"
        print("✓ Métricas iniciales correctas")
        
        return True
    except Exception as e:
        print(f"✗ Error en inicialización: {e}")
        return False

def test_task_management():
    """Prueba la gestión de tareas"""
    print("\n=== Prueba 3: Gestión de tareas ===")
    try:
        from decision_core import DecisionCore, TaskPriority
        
        core = DecisionCore()
        
        # Función de prueba
        def test_task():
            return {"result": "success", "timestamp": datetime.now().isoformat()}
        
        # Añadir tarea
        task_id = core.add_task(test_task, TaskPriority.HIGH)
        assert task_id is not None, "No se pudo añadir la tarea"
        print(f"✓ Tarea añadida con ID: {task_id[:8]}...")
        
        # Verificar cola
        status = core.get_status()
        assert status["tasks_queue_size"] >= 1, "La cola debería tener al menos 1 tarea"
        print(f"✓ Cola de tareas tiene {status['tasks_queue_size']} tarea(s)")
        
        return True
    except Exception as e:
        print(f"✗ Error en gestión de tareas: {e}")
        return False

def test_ghost_mode():
    """Prueba el modo fantasma"""
    print("\n=== Prueba 4: Modo Fantasma ===")
    try:
        from decision_core import DecisionCore
        
        core = DecisionCore()
        
        # Estado inicial
        status = core.get_status()
        assert status["ghost_mode"] == False, "El modo fantasma debería estar desactivado inicialmente"
        print("✓ Modo fantasma inicial: Desactivado")
        
        # Activar
        result = core.toggle_ghost_mode()
        assert result == True, "El modo fantasma debería estar activado"
        print("✓ Modo fantasma activado correctamente")
        
        # Desactivar
        result = core.toggle_ghost_mode()
        assert result == False, "El modo fantasma debería estar desactivado"
        print("✓ Modo fantasma desactivado correctamente")
        
        return True
    except Exception as e:
        print(f"✗ Error en modo fantasma: {e}")
        return False

def test_cache_system():
    """Prueba el sistema de caché"""
    print("\n=== Prueba 5: Sistema de Caché ===")
    try:
        from decision_core import DecisionCore
        
        core = DecisionCore()
        
        # Guardar en caché
        test_data = {"test": "data", "timestamp": datetime.now().isoformat()}
        core._cache_result("test_task_1", test_data)
        print("✓ Datos guardados en caché")
        
        # Recuperar de caché
        cached = core.get_cached_result("test_task_1")
        assert cached is not None, "Los datos deberían estar en caché"
        assert cached["test"] == "data", "Los datos en caché son incorrectos"
        print("✓ Datos recuperados de caché correctamente")
        
        # Verificar métricas
        metrics = core.get_metrics()
        assert metrics["cache_hits"] >= 1, "Debería haber al menos 1 cache hit"
        print(f"✓ Métricas de caché: {metrics['cache_hits']} hits")
        
        return True
    except Exception as e:
        print(f"✗ Error en sistema de caché: {e}")
        return False

def test_lifecycle():
    """Prueba el ciclo de vida del Decision Core"""
    print("\n=== Prueba 6: Ciclo de Vida ===")
    try:
        from decision_core import DecisionCore
        
        core = DecisionCore()
        
        # Iniciar
        result = core.start()
        assert result == True, "El sistema debería iniciar correctamente"
        status = core.get_status()
        assert status["state"] == "RUNNING", f"Estado debería ser RUNNING, es {status['state']}"
        print("✓ Sistema iniciado correctamente")
        
        # Esperar un momento
        time.sleep(1)
        
        # Detener
        result = core.stop()
        assert result == True, "El sistema debería detenerse correctamente"
        status = core.get_status()
        assert status["state"] == "STOPPED", f"Estado debería ser STOPPED, es {status['state']}"
        print("✓ Sistema detenido correctamente")
        
        return True
    except Exception as e:
        print(f"✗ Error en ciclo de vida: {e}")
        return False

def test_config_loading():
    """Prueba la carga de configuración"""
    print("\n=== Prueba 7: Carga de Configuración ===")
    try:
        from decision_core import DecisionCore
        
        # Crear archivo de configuración temporal
        test_config = {
            "max_tasks": 50,
            "cache_size": 500,
            "monitoring_interval": 30
        }
        
        config_path = "test_config.json"
        with open(config_path, 'w') as f:
            json.dump(test_config, f)
        
        # Cargar configuración
        core = DecisionCore(config_path=config_path)
        
        # Verificar que se cargó correctamente
        assert core.config["max_tasks"] == 50, "Configuración max_tasks incorrecta"
        assert core.config["cache_size"] == 500, "Configuración cache_size incorrecta"
        print("✓ Configuración personalizada cargada correctamente")
        
        # Limpiar
        os.remove(config_path)
        
        return True
    except Exception as e:
        print(f"✗ Error en carga de configuración: {e}")
        return False

def run_all_tests():
    """Ejecuta todas las pruebas"""
    print("=" * 60)
    print("PRUEBAS DE DECISION CORE - AURA")
    print("=" * 60)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 60)
    
    tests = [
        test_imports,
        test_initialization,
        test_task_management,
        test_ghost_mode,
        test_cache_system,
        test_lifecycle,
        test_config_loading
    ]
    
    results = []
    
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ Error inesperado en {test.__name__}: {e}")
            results.append(False)
    
    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN DE PRUEBAS")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    for i, (test, result) in enumerate(zip(tests, results), 1):
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{i}. {test.__name__}: {status}")
    
    print("-" * 60)
    print(f"Resultado: {passed}/{total} pruebas pasaron")
    
    if passed == total:
        print("\n🎉 ¡TODAS LAS PRUEBAS PASARON EXITOSAMENTE!")
        return True
    else:
        print(f"\n⚠️  {total - passed} prueba(s) fallaron")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)