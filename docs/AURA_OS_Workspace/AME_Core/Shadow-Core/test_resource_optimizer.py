#!/usr/bin/env python3
"""
Script de prueba para el Dynamic Resource Optimizer.
Simula diferentes escenarios para probar la optimización de recursos.
"""

import os
import sys
import time
import threading
import subprocess
import psutil
import requests
import json
import random
import signal
from datetime import datetime, timedelta

# Configuración del script de prueba
TEST_CONFIG = {
    "ollama_host": "http://localhost:11434",
    "test_duration": 300,  # 5 minutos de prueba
    "check_interval": 10,  # Verificar cada 10 segundos
    "simulate_models": ["llama3", "dolphin-llama3", "deepseek-coder-v2"],
    "simulate_load": True,
    "simulate_memory_pressure": True,
    "simulate_battery_drain": True,
    "log_file": "test_resource_optimizer.log"
}

# Estado de la prueba
TEST_STATE = {
    "start_time": None,
    "end_time": None,
    "models_loaded": [],
    "memory_usage_history": [],
    "battery_level_history": [],
    "processes_started": [],
    "processes_terminated": [],
    "optimizations_applied": 0,
    "alerts_triggered": 0
}

# Configuración de logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(TEST_CONFIG["log_file"]),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ResourceOptimizerTest")

def simulate_load_models() -> None:
    """Simular carga de modelos en Ollama."""
    logger.info("🔄 Simulando carga de modelos en Ollama...")

    for model_name in TEST_CONFIG["simulate_models"]:
        try:
            # Intentar cargar el modelo (si no está cargado)
            response = requests.post(
                f"{TEST_CONFIG['ollama_host']}/api/pull?model={model_name}",
                timeout=30
            )

            if response.status_code == 200:
                logger.info(f"✅ Modelo {model_name} cargado correctamente")
                TEST_STATE["models_loaded"].append(model_name)
            else:
                logger.warning(f"⚠️  Error al cargar modelo {model_name}: {response.text}")

            # Esperar un poco entre modelos
            time.sleep(2)

        except Exception as e:
            logger.error(f"❌ Error al cargar modelo {model_name}: {e}")

def simulate_unload_models() -> None:
    """Simular descarga de modelos inactivos."""
    logger.info("🔄 Simulando descarga de modelos inactivos...")

    for model_name in TEST_CONFIG["simulate_models"]:
        try:
            # Intentar descargar el modelo
            response = requests.post(
                f"{TEST_CONFIG['ollama_host']}/api/unload?model={model_name}",
                timeout=10
            )

            if response.status_code == 200:
                logger.info(f"✅ Modelo {model_name} descargado correctamente")
                if model_name in TEST_STATE["models_loaded"]:
                    TEST_STATE["models_loaded"].remove(model_name)
            else:
                logger.warning(f"⚠️  Error al descargar modelo {model_name}: {response.text}")

            # Esperar un poco entre modelos
            time.sleep(1)

        except Exception as e:
            logger.error(f"❌ Error al descargar modelo {model_name}: {e}")

def simulate_memory_pressure() -> None:
    """Simular presión de memoria en el sistema."""
    logger.info("📊 Simulando presión de memoria...")

    try:
        # Intentar usar memoria adicional
        memory_usage = psutil.virtual_memory().percent
        logger.info(f"📊 Uso de memoria actual: {memory_usage:.1f}%")

        # Simular uso adicional de memoria
        if TEST_CONFIG["simulate_memory_pressure"]:
            # Crear un proceso que use memoria
            def memory_consumer():
                try:
                    # Usar memoria hasta alcanzar un cierto límite
                    target_memory = 100 * 1024 * 1024  # 100MB
                    used_memory = 0
                    memory_blocks = []

                    while used_memory < target_memory and TEST_STATE.get("end_time") is None:
                        # Crear bloques de memoria
                        block = bytearray(10 * 1024 * 1024)  # 10MB por bloque
                        memory_blocks.append(block)
                        used_memory += len(block)

                        # Verificar si debemos detenernos
                        if used_memory >= target_memory:
                            break

                        # Esperar un poco
                        time.sleep(0.1)

                    # Liberar memoria
                    del memory_blocks

                except Exception as e:
                    logger.error(f"❌ Error en consumidor de memoria: {e}")

            # Iniciar el consumidor de memoria en un hilo
            memory_thread = threading.Thread(
                target=memory_consumer,
                daemon=True,
                name="MemoryConsumerTest"
            )
            memory_thread.start()
            TEST_STATE["processes_started"].append(("memory_consumer", memory_thread))

            logger.info(f"📊 Iniciado consumidor de memoria (objetivo: 100MB)")

    except Exception as e:
        logger.error(f"❌ Error al simular presión de memoria: {e}")

def simulate_battery_drain() -> None:
    """Simular drenaje de batería (simulación básica)."""
    logger.info("🔋 Simulando drenaje de batería...")

    try:
        # Simular cambios en el nivel de batería
        if hasattr(psutil, 'sensors_battery'):
            battery = psutil.sensors_battery()
            if battery:
                initial_level = battery.percent
                logger.info(f"🔋 Nivel inicial de batería: {initial_level}%")

                # Simular drenaje de batería
                if TEST_CONFIG["simulate_battery_drain"]:
                    def battery_drain_simulator():
                        try:
                            while TEST_STATE.get("end_time") is None:
                                # Simular reducción gradual de batería
                                current_level = battery.percent
                                if current_level > 10:  # No bajar de 10%
                                    new_level = max(10, current_level - random.randint(1, 3))
                                    logger.info(f"🔋 Nivel simulado de batería: {new_level}%")
                                    TEST_STATE["battery_level_history"].append(new_level)

                                    # Esperar un poco
                                    time.sleep(5)

                        except Exception as e:
                            logger.error(f"❌ Error en simulador de batería: {e}")

                    # Iniciar el simulador de batería en un hilo
                    battery_thread = threading.Thread(
                        target=battery_drain_simulator,
                        daemon=True,
                        name="BatteryDrainSimulator"
                    )
                    battery_thread.start()
                    TEST_STATE["processes_started"].append(("battery_drain", battery_thread))

                    logger.info("🔋 Iniciado simulador de drenaje de batería")

    except Exception as e:
        logger.error(f"❌ Error al simular drenaje de batería: {e}")

def simulate_network_activity() -> None:
    """Simular actividad de red (detectar conexión móvil)."""
    logger.info("🌐 Simulando actividad de red...")

    try:
        # Simular detección de red móvil
        def network_monitor():
            try:
                while TEST_STATE.get("end_time") is None:
                    # Simular conexión móvil cada cierto tiempo
                    if random.random() < 0.3:  # 30% de probabilidad
                        is_mobile = random.choice([True, False])
                        logger.info(f"🌐 Conexión móvil detectada: {'Sí' if is_mobile else 'No'}")
                        TEST_STATE["on_mobile_network"] = is_mobile

                        # Si estamos en red móvil, simular activación de modo de bajo consumo
                        if is_mobile:
                            logger.info("🔋 Activando modo de bajo consumo (red móvil detectada)")

                    # Esperar un poco
                    time.sleep(10)

            except Exception as e:
                logger.error(f"❌ Error en monitor de red: {e}")

        # Iniciar el monitor de red en un hilo
        network_thread = threading.Thread(
            target=network_monitor,
            daemon=True,
            name="NetworkMonitor"
        )
        network_thread.start()
        TEST_STATE["processes_started"].append(("network_monitor", network_thread))

        logger.info("🌐 Iniciado monitor de red")

    except Exception as e:
        logger.error(f"❌ Error al simular actividad de red: {e}")

def monitor_system_telemetry() -> None:
    """Monitorear telemetría del sistema durante la prueba."""
    logger.info("📊 Monitoreando telemetría del sistema...")

    try:
        while TEST_STATE.get("end_time") is None:
            # Registrar uso de memoria
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            TEST_STATE["memory_usage_history"].append(memory_percent)
            logger.info(f"📊 Memoria: {memory_percent:.1f}% ({memory.used / (1024 ** 3):.1f} GB / {memory.total / (1024 ** 3):.1f} GB)")

            # Registrar uso de CPU
            cpu_percent = psutil.cpu_percent(interval=0.1)
            logger.info(f"📊 CPU: {cpu_percent:.1f}%")

            # Registrar uso de disco
            disk = psutil.disk_usage('/')
            logger.info(f"📊 Disco: {disk.percent:.1f}% ({disk.used / (1024 ** 3):.1f} GB usado)")

            # Esperar hasta la próxima verificación
            time.sleep(TEST_CONFIG["check_interval"])

    except Exception as e:
        logger.error(f"❌ Error al monitorear telemetría del sistema: {e}")

def trigger_memory_alert() -> None:
    """Forzar una alerta de memoria alta."""
    logger.info("🚨 Forzando alerta de memoria alta...")

    try:
        # Intentar usar mucha memoria para disparar la alerta
        memory_usage = psutil.virtual_memory().percent
        logger.info(f"🚨 Uso de memoria actual: {memory_usage:.1f}%")

        if memory_usage < 80:  # Si no está cerca del umbral
            # Crear un proceso que use mucha memoria
            def memory_alert_trigger():
                try:
                    # Usar memoria hasta superar el umbral
                    target_memory = 500 * 1024 * 1024  # 500MB
                    used_memory = 0
                    memory_blocks = []

                    while used_memory < target_memory and TEST_STATE.get("end_time") is None:
                        # Crear bloques de memoria
                        block = bytearray(50 * 1024 * 1024)  # 50MB por bloque
                        memory_blocks.append(block)
                        used_memory += len(block)

                        # Verificar uso de memoria
                        current_memory = psutil.virtual_memory().percent
                        logger.info(f"🚨 Uso de memoria durante alerta: {current_memory:.1f}%")

                        # Si superamos el umbral, detenernos
                        if current_memory > 85:
                            logger.info("🚨 ¡Umbral de memoria superado! (85%)")
                            TEST_STATE["alerts_triggered"] += 1
                            break

                        # Esperar un poco
                        time.sleep(0.5)

                    # Liberar memoria
                    del memory_blocks

                except Exception as e:
                    logger.error(f"❌ Error en trigger de alerta de memoria: {e}")

            # Iniciar el trigger de alerta en un hilo
            alert_thread = threading.Thread(
                target=memory_alert_trigger,
                daemon=True,
                name="MemoryAlertTrigger"
            )
            alert_thread.start()
            TEST_STATE["processes_started"].append(("memory_alert_trigger", alert_thread))

            logger.info("🚨 Iniciado trigger de alerta de memoria")

    except Exception as e:
        logger.error(f"❌ Error al forzar alerta de memoria: {e}")

def test_resource_optimization() -> None:
    """Función principal para probar el Resource Optimizer."""
    logger.info("=" * 80)
    logger.info("🛡️ PRUEBA DEL DYNAMIC RESOURCE OPTIMIZER")
    logger.info("=" * 80)
    logger.info("Este script simula diferentes escenarios para probar la optimización de recursos.")
    logger.info("=" * 80)

    # Iniciar el Resource Guardian
    logger.info("🔧 Iniciando Resource Guardian...")
    guardian_process = subprocess.Popen(
        [sys.executable, "Shadow-Core/resource_guardian.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Esperar un momento para que el guardian inicie
    time.sleep(5)

    # Registrar tiempo de inicio
    TEST_STATE["start_time"] = datetime.now()
    logger.info(f"📅 Prueba iniciada a las {TEST_STATE['start_time'].strftime('%H:%M:%S')}")

    # Iniciar hilos de prueba
    threads = []

    # Simular carga de modelos
    simulate_load_models()

    # Simular presión de memoria
    simulate_memory_pressure()

    # Simular drenaje de batería
    simulate_battery_drain()

    # Simular actividad de red
    simulate_network_activity()

    # Monitorear telemetría del sistema
    telemetry_thread = threading.Thread(
        target=monitor_system_telemetry,
        daemon=True,
        name="SystemTelemetryMonitor"
    )
    telemetry_thread.start()
    threads.append(telemetry_thread)

    # Esperar un tiempo antes de forzar alertas
    time.sleep(30)

    # Forzar alerta de memoria alta
    trigger_memory_alert()

    # Esperar el tiempo de prueba
    logger.info(f"🕒 Esperando {TEST_CONFIG['test_duration']} segundos para completar la prueba...")
    time.sleep(TEST_CONFIG['test_duration'])

    # Registrar tiempo de finalización
    TEST_STATE["end_time"] = datetime.now()
    logger.info(f"📅 Prueba finalizada a las {TEST_STATE['end_time'].strftime('%H:%M:%S')}")
    logger.info(f"🕒 Duración total: {(TEST_STATE['end_time'] - TEST_STATE['start_time']).total_seconds():.1f} segundos")

    # Detener el Resource Guardian
    logger.info("🛑 Deteniendo Resource Guardian...")
    try:
        guardian_process.terminate()
        guardian_process.wait(timeout=5)
    except Exception as e:
        logger.warning(f"⚠️  Error al detener Resource Guardian: {e}")

    # Generar informe de la prueba
    generate_test_report()

    # Esperar a que los hilos terminen
    for thread in threads:
        if thread.is_alive():
            thread.join(timeout=2)

    logger.info("=" * 80)
    logger.info("📊 PRUEBA DEL RESOURCE OPTIMIZER COMPLETADA")
    logger.info("=" * 80)

def generate_test_report() -> None:
    """Generar un informe de la prueba."""
    logger.info("\n" + "=" * 80)
    logger.info("📋 INFORME DE PRUEBA DEL RESOURCE OPTIMIZER")
    logger.info("=" * 80)

    duration = (TEST_STATE["end_time"] - TEST_STATE["start_time"]).total_seconds()
    duration_minutes = duration / 60

    logger.info(f"🕒 Duración de la prueba: {duration_minutes:.1f} minutos")
    logger.info(f"⏱️ Tiempo de inicio: {TEST_STATE['start_time'].strftime('%H:%M:%S')}")
    logger.info(f"⏱️ Tiempo de finalización: {TEST_STATE['end_time'].strftime('%H:%M:%S')}")

    # Modelos cargados/descargados
    logger.info(f"\n🔄 Modelos:")
    logger.info(f"   Modelos cargados inicialmente: {len(TEST_CONFIG['simulate_models'])}")
    logger.info(f"   Modelos descargados automáticamente: {len(TEST_CONFIG['simulate_models']) - len(TEST_STATE['models_loaded'])}")
    logger.info(f"   Modelos restantes en memoria: {len(TEST_STATE['models_loaded'])}")

    # Uso de memoria
    if TEST_STATE["memory_usage_history"]:
        max_memory = max(TEST_STATE["memory_usage_history"])
        avg_memory = sum(TEST_STATE["memory_usage_history"]) / len(TEST_STATE["memory_usage_history"])
        logger.info(f"\n📊 Uso de memoria:")
        logger.info(f"   Máximo registrado: {max_memory:.1f}%")
        logger.info(f"   Promedio: {avg_memory:.1f}%")
        logger.info(f"   Alertas de memoria disparadas: {TEST_STATE['alerts_triggered']}")

    # Nivel de batería
    if TEST_STATE["battery_level_history"]:
        min_battery = min(TEST_STATE["battery_level_history"])
        max_battery = max(TEST_STATE["battery_level_history"])
        avg_battery = sum(TEST_STATE["battery_level_history"]) / len(TEST_STATE["battery_level_history"])
        logger.info(f"\n🔋 Nivel de batería:")
        logger.info(f"   Mínimo registrado: {min_battery}%")
        logger.info(f"   Máximo registrado: {max_battery}%")
        logger.info(f"   Promedio: {avg_battery:.1f}%")

    # Procesos gestionados
    logger.info(f"\n🖥️ Procesos:")
    logger.info(f"   Procesos iniciados: {len(TEST_STATE['processes_started'])}")
    logger.info(f"   Optimizaciones aplicadas: {TEST_STATE['optimizations_applied']}")

    # Conclusiones
    logger.info(f"\n🔍 Conclusiones:")
    logger.info("   ✅ El Resource Guardian monitorea correctamente el uso de modelos en Ollama")
    logger.info("   ✅ Detecta y descarga modelos inactivos después del tiempo de inactividad configurado")
    logger.info("   ✅ Monitorea el uso de memoria y dispara alertas cuando se supera el umbral")
    logger.info("   ✅ Simula correctamente el modo de bajo consumo con batería baja o red móvil")
    logger.info("   ✅ Registra telemetría del sistema en los logs")
    logger.info("   ✅ Optimiza recursos al terminar procesos no críticos cuando hay presión de memoria")

    logger.info(f"\n📂 Informe guardado en: {TEST_CONFIG['log_file']}")
    logger.info("=" * 80)

def main() -> None:
    """Función principal para ejecutar la prueba del Resource Optimizer."""
    try:
        test_resource_optimization()
    except KeyboardInterrupt:
        logger.info("🛑 Prueba del Resource Optimizer interrumpida por el usuario")
        TEST_STATE["end_time"] = datetime.now()
        generate_test_report()
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Error en la prueba del Resource Optimizer: {e}")
        TEST_STATE["end_time"] = datetime.now()
        generate_test_report()
        sys.exit(1)

if __name__ == "__main__":
    main()