# Tactical Event Logger - Shadow-Core

## Descripción

Módulo de registro de eventos tácticos para Shadow-Core que registra eventos del sistema y los envía al EventBus de AURA. Diseñado para monitorear operaciones del sistema de manera segura y legal, sin capturar datos sensibles como teclas o portapapeles.

## Características

- **Eventos del sistema**: Registra eventos como reinicios de servicio, cambios de red, uso de disco, etc.
- **Integración con EventBus**: Envía eventos al EventBus de AURA en formato JSON estructurado.
- **Cola de eventos**: Maneja una cola de eventos para evitar pérdida de datos.
- **Configuración flexible**: Permite configurar qué eventos registrar y con qué frecuencia.
- **Manejo de errores**: Reintenta la conexión al EventBus si falla.

## Instalación

### Requisitos

- Python 3.7+
- Librerías: `websockets`, `asyncio`
- Nmap instalado (para pruebas de red)

### Instalación de dependencias

```bash
pip install websockets
```

## Configuración

El módulo crea automáticamente un archivo de configuración en:

```
Shadow-Core/config/tactical_events.json
```

Ejemplo de configuración:

```json
{
  "enabled_events": [
    "system_startup",
    "service_restart",
    "network_change",
    "disk_usage",
    "process_termination"
  ],
  "event_interval": 60,
  "max_queue_size": 1000
}
```

## Uso

### Inicialización

```python
from Shadow_Core.tactical_event_logger import tactical_event_logger

# Iniciar el logger
tactical_event_logger.start()
```

### Métodos disponibles

#### Registrar eventos específicos

```python
# Reinicio de servicio
tactical_event_logger.log_service_restart("Shadow-Core")

# Terminación de proceso
tactical_event_logger.log_process_termination("test_script.py", 0)

# Uso de disco
tactical_event_logger.log_disk_usage("/")

# Cambio de red
tactical_event_logger.log_network_change()
```

#### Detener el logger

```python
tactical_event_logger.stop()
```

## Eventos registrados

| Evento                | Descripción                 | Ejemplo de uso                            |
| --------------------- | --------------------------- | ----------------------------------------- |
| `system_startup`      | Inicio del sistema          | Evento automático al iniciar el logger    |
| `service_restart`     | Reinicio de un servicio     | `log_service_restart("Shadow-Core")`      |
| `network_change`      | Cambio en interfaces de red | `log_network_change()`                    |
| `disk_usage`          | Uso de disco                | `log_disk_usage("/")`                     |
| `process_termination` | Terminación de proceso      | `log_process_termination("script.py", 0)` |

## Formato de eventos

Los eventos se envían al EventBus en formato JSON con la siguiente estructura:

```json
{
  "type": "event_type",
  "timestamp": "2023-01-01T00:00:00",
  "system_info": {
    "timestamp": "2023-01-01T00:00:00",
    "hostname": "shadow-host",
    "os": "Linux",
    "python_version": "3.9.7",
    "cpu_cores": 8,
    "memory_usage": {
      "total": "16GB",
      "free": "4GB",
      "available": "8GB"
    }
  },
  "details": {
    "service": "Shadow-Core",
    "timestamp": "2023-01-01T00:00:00"
  },
  "source": "Shadow-Core"
}
```

## Integración con EventBus

El módulo envía eventos al EventBus de AURA usando WebSocket. El formato del mensaje es:

```json
{
    "node": "Shadow-Core",
    "event": "TACTICAL_CAPTURE",
    "payload": {event_data},
    "ts": "2023-01-01T00:00:00"
}
```

## Ejemplo de uso completo

```python
from Shadow_Core.tactical_event_logger import tactical_event_logger
import time

# Iniciar el logger
tactical_event_logger.start()

# Registrar eventos
tactical_event_logger.log_service_restart("Shadow-Core")
tactical_event_logger.log_disk_usage("/")
tactical_event_logger.log_network_change()

# Esperar un tiempo para procesar los eventos
time.sleep(5)

# Detener el logger
tactical_event_logger.stop()
```

## Pruebas

Para probar el módulo, ejecute el script de prueba:

```bash
python Shadow-Core/test_logger_clean.py
```

## Notas importantes

1. **Seguridad**: Este módulo solo registra eventos del sistema autorizados y no captura datos sensibles.
2. **EventBus**: La conexión al EventBus se maneja de manera asíncrona y se reintenta automáticamente si falla.
3. **Cola de eventos**: Los eventos se almacenan en una cola para evitar pérdida de datos si el EventBus no está disponible.
4. **Configuración**: La configuración se guarda en un archivo JSON para persistencia entre ejecuciones.

## Soporte

Para problemas o preguntas, contactar al equipo de desarrollo de Shadow-Core.
