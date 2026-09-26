"""
Ejemplo de uso del TacticalEventLogger en Shadow-Core.
Demonstra cómo registrar eventos del sistema y enviarlos al EventBus de AURA.
"""

import time
import random
from Shadow_Core.tactical_event_logger import tactical_event_logger

def simulate_system_operations():
    """
    Simula operaciones del sistema que generan eventos.
    """
    print("🚀 Iniciando simulación de operaciones del sistema...")

    # Iniciar el logger
    tactical_event_logger.start()
    print("✅ TacticalEventLogger iniciado y conectado al EventBus")

    # Simular eventos de reinicio de servicio
    services = ["Shadow-Core", "AURA-Core", "GodotService", "NetworkMonitor"]
    for i, service in enumerate(services):
        print(f"🔄 Simulando reinicio de servicio {service}...")
        tactical_event_logger.log_service_restart(service)
        time.sleep(random.uniform(0.5, 1.5))

    # Simular uso de disco en diferentes rutas
    paths = ["/", "/var", "/home", "/tmp"]
    for path in paths:
        print(f"💾 Verificando uso de disco en {path}...")
        tactical_event_logger.log_disk_usage(path)
        time.sleep(random.uniform(0.3, 0.8))

    # Simular cambios de red
    print("🌐 Simulando cambios de red...")
    tactical_event_logger.log_network_change()
    time.sleep(1)

    # Simular terminación de procesos
    processes = [
        ("python", 0),
        ("shadow_service", 1),
        ("test_script.py", 0),
        ("network_scan", 2),
        ("data_processor", 0)
    ]
    for process, exit_code in processes:
        print(f"🔴 Simulando terminación de proceso {process} (código {exit_code})...")
        tactical_event_logger.log_process_termination(process, exit_code)
        time.sleep(random.uniform(0.2, 0.5))

    # Simular evento de error crítico
    print("⚠️ Simulando evento de error crítico...")
    tactical_event_logger._log_system_event("critical_error", {
        "message": "Error de conexión con el EventBus",
        "severity": "high",
        "timestamp": "2023-01-01T00:00:00"
    })
    time.sleep(1)

    # Simular evento de recuperación
    print("✅ Simulando recuperación del sistema...")
    tactical_event_logger._log_system_event("system_recovery", {
        "message": "Recuperación exitosa después de error crítico",
        "timestamp": "2023-01-01T00:00:05"
    })
    time.sleep(1)

    # Detener el logger
    tactical_event_logger.stop()
    print("⏹️ TacticalEventLogger detenido")

def monitor_system_health():
    """
    Monitorea la salud del sistema y registra eventos periódicos.
    """
    print("\n📊 Iniciando monitoreo de salud del sistema...")

    # Iniciar el logger
    tactical_event_logger.start()

    try:
        for i in range(5):
            print(f"🔄 Ciclo {i+1}/5 de monitoreo de salud...")

            # Registrar uso de disco cada ciclo
            tactical_event_logger.log_disk_usage("/")

            # Registrar cambio de red cada 2 ciclos
            if i % 2 == 0:
                tactical_event_logger.log_network_change()

            # Esperar un tiempo aleatorio
            time.sleep(random.uniform(1, 3))

    except KeyboardInterrupt:
        print("\n🛑 Monitoreo interrumpido por el usuario")

    finally:
        tactical_event_logger.stop()
        print("🏠 Monitoreo de salud finalizado")

def main():
    """
    Ejemplo principal de uso del TacticalEventLogger.
    """
    print("=" * 60)
    print("📋 EJEMPLO DE USO DEL TACTICAL EVENT LOGGER")
    print("=" * 60)

    try:
        # Ejemplo 1: Simulación de operaciones del sistema
        print("\n📌 Ejemplo 1: Simulación de operaciones del sistema")
        simulate_system_operations()

        # Ejemplo 2: Monitoreo de salud del sistema
        print("\n📌 Ejemplo 2: Monitoreo de salud del sistema")
        monitor_system_health()

        print("\n" + "=" * 60)
        print("🎉 EJEMPLOS DE USO COMPLETADOS")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error durante la ejecución: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()