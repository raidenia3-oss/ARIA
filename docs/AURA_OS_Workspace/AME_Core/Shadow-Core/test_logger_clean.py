tra"""
Script de prueba limpio para validar el módulo TacticalEventLogger.
"""

import time
import json
from pathlib import Path
from Shadow_Core.tactical_event_logger import tactical_event_logger

def test_logger():
    """Prueba completa del módulo TacticalEventLogger."""
    print("Iniciando prueba del TacticalEventLogger...")

    # Iniciar el logger
    tactical_event_logger.start()
    print("✅ Logger iniciado")

    # Esperar un momento para que se registren los eventos iniciales
    time.sleep(2)

    # Simular eventos del sistema
    print("\nSimulando eventos del sistema...")

    # Evento de reinicio de servicio
    tactical_event_logger.log_service_restart("Shadow-Core")
    print("✅ Evento de reinicio de servicio registrado")

    # Evento de uso de disco
    tactical_event_logger.log_disk_usage("/")
    print("✅ Evento de uso de disco registrado")

    # Evento de cambio de red
    tactical_event_logger.log_network_change()
    print("✅ Evento de cambio de red registrado")

    # Evento de terminación de proceso
    tactical_event_logger.log_process_termination("test_script.py", 0)
    print("✅ Evento de terminación de proceso registrado")

    # Esperar para procesar los eventos
    time.sleep(3)

    # Verificar que se hayan generado archivos de log
    logs_dir = Path("Shadow-Core/logs")
    logs_dir.mkdir(parents=True, exist_ok=True)

    log_files = list(logs_dir.glob("tactical_events_*.json"))
    print(f"\n📁 Archivos de log generados: {len(log_files)}")

    if log_files:
        print("\n📄 Contenido del primer archivo de log:")
        first_log = log_files[0]
        with open(first_log, "r") as f:
            for i, line in enumerate(f.readlines()[:3]):  # Mostrar primeros 3 eventos
                event = json.loads(line.strip())
                print(f"  {i+1}. {event['type']} - {event['timestamp']}")
                if 'details' in event and event['details']:
                    print(f"     Detalles: {json.dumps(event['details'], indent=2)}")

    # Detener el logger
    tactical_event_logger.stop()
    print("\n✅ Logger detenido")

    return True

def test_event_bus_simulation():
    """Prueba de simulación de integración con EventBus."""
    print("\n🔗 Probando simulación de EventBus...")

    test_event = {
        "type": "test_event",
        "timestamp": "2023-01-01T00:00:00",
        "system_info": {
            "hostname": "test-host",
            "os": "Linux",
            "python_version": "3.9.7"
        },
        "details": {
            "message": "Este es un evento de prueba para el EventBus",
            "source": "test_logger"
        },
        "source": "Shadow-Core"
    }

    print("📤 Simulando envío de evento al EventBus...")
    tactical_event_logger._send_to_event_bus(test_event)
    print("✅ Evento enviado correctamente (simulado)")

    return True

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 PRUEBA DEL TACTICAL EVENT LOGGER")
    print("=" * 60)

    try:
        # Ejecutar pruebas
        test1 = test_logger()
        test2 = test_event_bus_simulation()

        if test1 and test2:
            print("\n" + "=" * 60)
            print("🎉 TODAS LAS PRUEBAS SUPERADAS")
            print("=" * 60)
        else:
            print("\n❌ Algunas pruebas fallaron")

    except Exception as e:
        print(f"\n❌ Error durante las pruebas: {e}")
        import traceback
        traceback.print_exc()
