# 📜 **TASKS: DESARROLLO DEL NODO PHANTOM OSINT**
**Versión:** 1.0.0
**Fecha:** 02/06/2026
**Estado:** **Tareas Atómicas para Strict TDD**
**Autor:** Arquitecto de Software Senior

---

## 🎯 **Objetivo**
Dividir la implementación del nodo **NOD_PHANTOM_OSINT** en tareas atómicas para aplicar **Strict TDD (Test-Driven Development)**. Cada tarea incluye:
- **Descripción**.
- **Criterios de Aceptación** (GIVEN/WHEN/THEN).
- **Pruebas Unitarias** (mock y stubs).
- **Dependencias**.

---

## 📋 **Tareas Atómicas**

### **Tarea 1: Estructura Básica del Nodo**
**Descripción:**
Crear la estructura básica del nodo `NOD_PHANTOM_OSINT.py` con la clase principal y métodos esenciales.

**Criterios de Aceptación:**
| **ID**  | **Escenario**                                                                                     | **Criterio de Aceptación**                                                                         |
|---------|-------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------|
| TA1-001 | **GIVEN** una configuración válida, **WHEN** se inicializa el nodo, **THEN** debe crear una instancia de `PhantomOSINTNode` sin errores. | La clase se inicializa correctamente y no lanza excepciones.                                      |
| TA1-002 | **GIVEN** una configuración inválida, **WHEN** se intenta inicializar el nodo, **THEN** debe manejar la excepción y emitir un mensaje de error. | El nodo captura la excepción y no crashtea el sistema.                                           |

**Pruebas Unitarias:**
```python
# tests/test_node_init.py
def test_init_node_success():
    config = {'logger': None}
    node = PhantomOSINTNode(config)
    assert node is not None
    assert hasattr(node, 'tools')

def test_init_node_invalid_config():
    with pytest.raises(Exception):
        PhantomOSINTNode(None)
```

**Dependencias:**
- `Shadow-Core/nodes/__init__.py` (para importar la clase base si existe).

---

### **Tarea 2: Módulo de Telemetría**
**Descripción:**
Implementar el método `_emit_telemetry` para enviar eventos al servidor mediante WebSocket.

**Criterios de Aceptación:**
| **ID**  | **Escenario**                                                                                     | **Criterio de Aceptación**                                                                         |
|---------|-------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------|
| TA2-001 | **GIVEN** un evento de telemetría válido, **WHEN** se emite, **THEN** debe enviar el evento al servidor mediante WebSocket. | El evento se envía correctamente y no hay errores de conexión.                                      |
| TA2-002 | **GIVEN** una conexión fallida al servidor, **WHEN** se intenta emitir un evento, **THEN** debe manejar la excepción y registrar el error. | El nodo no crashtea y registra el error en el logger.                                           |

**Pruebas Unitarias:**
```python
# tests/test_telemetry.py
def test_emit_telemetry_success(mocker):
    mocker.patch('socketio.emit')
    node = PhantomOSINTNode({'logger': None})
    node._emit_telemetry('iniciando', {'tool': 'phoneinfoga'})
    socketio.emit.assert_called_once()

def test_emit_telemetry_failure(mocker):
    mocker.patch('socketio.emit', side_effect=Exception("Conexión fallida"))
    node = PhantomOSINTNode({'logger': None})
    with pytest.raises(Exception):
        node._emit_telemetry('error', {'message': 'Error de conexión'})
```

**Dependencias:**
- `flask_socketio` (para emitir eventos).
- `socketio` (configurado en `servidor_ame.py`).

---

### **Tarea 3: Ejecución Asíncrona de PhoneInfoga**
**Descripción:**
Implementar el método `_execute_phoneinfoga` para ejecutar PhoneInfoga de manera asíncrona y manejar errores.

**Criterios de Aceptación:**
| **ID**  | **Escenario**                                                                                     | **Criterio de Aceptación**                                                                         |
|---------|-------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------|
| TA3-001 | **GIVEN** un comando válido para PhoneInfoga, **WHEN** se ejecuta, **THEN** debe iniciar el proceso asíncrono y emitir eventos de telemetría. | El proceso se ejecuta en segundo plano y emite eventos `iniciando`, `procesando` y `finalizado`. |
| TA3-002 | **GIVEN** un parámetro inválido (ej: `target` faltante), **WHEN** se ejecuta PhoneInfoga, **THEN** debe emitir un evento `error`. | El nodo emite un evento `error` con un mensaje descriptivo.                                      |
| TA3-003 | **GIVEN** un timeout en la ejecución, **WHEN** el proceso supera los 300 segundos, **THEN** debe cancelar la ejecución y emitir un evento `timeout`. | El nodo cancela el proceso y emite un evento `timeout`.                                           |

**Pruebas Unitarias:**
```python
# tests/test_phoneinfoga.py
def test_execute_phoneinfoga_success(mocker):
    mocker.patch('subprocess.run', return_value=Mock(returncode=0, stdout='{"result": "success"}'))
    mocker.patch.object(PhantomOSINTNode, '_emit_telemetry')
    node = PhantomOSINTNode({'logger': None})
    node._execute_phoneinfoga({'target': '1234567890'})
    assert node._emit_telemetry.call_count == 3  # iniciando, procesando, finalizado

def test_execute_phoneinfoga_invalid_params(mocker):
    mocker.patch.object(PhantomOSINTNode, '_emit_telemetry')
    node = PhantomOSINTNode({'logger': None})
    node._execute_phoneinfoga({})
    node._emit_telemetry.assert_called_with('error', {'message': 'Parámetro "target" es obligatorio para PhoneInfoga.'})

def test_execute_phoneinfoga_timeout(mocker):
    mocker.patch('subprocess.run', side_effect=subprocess.TimeoutExpired('cmd', 300))
    mocker.patch.object(PhantomOSINTNode, '_emit_telemetry')
    node = PhantomOSINTNode({'logger': None})
    node._execute_phoneinfoga({'target': '1234567890'})
    node._emit_telemetry.assert_called_with('timeout', {'message': 'Timeout al ejecutar PhoneInfoga (300 segundos).'})
```

**Dependencias:**
- `subprocess` (para ejecutar comandos en la terminal).
- `asyncio` o `threading` (para ejecución asíncrona).

---

### **Tarea 4: Ejecución Asíncrona de theHarvester**
**Descripción:**
Implementar el método `_execute_theharvester` para ejecutar theHarvester de manera asíncrona y manejar errores.

**Criterios de Aceptación:**
| **ID**  | **Escenario**                                                                                     | **Criterio de Aceptación**                                                                         |
|---------|-------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------|
| TA4-001 | **GIVEN** un comando válido para theHarvester, **WHEN** se ejecuta, **THEN** debe iniciar el proceso asíncrono y emitir eventos de telemetría. | El proceso se ejecuta en segundo plano y emite eventos `iniciando`, `procesando` y `finalizado`. |
| TA4-002 | **GIVEN** un parámetro inválido (ej: `domain` faltante), **WHEN** se ejecuta theHarvester, **THEN** debe emitir un evento `error`. | El nodo emite un evento `error` con un mensaje descriptivo.                                      |
| TA4-003 | **GIVEN** un error en la ejecución, **WHEN** theHarvester falla, **THEN** debe emitir un evento `error` con detalles del error. | El nodo emite un evento `error` con la traza de la excepción.                                      |

**Pruebas Unitarias:**
```python
# tests/test_theharvester.py
def test_execute_theharvester_success(mocker):
    mocker.patch('subprocess.run', return_value=Mock(returncode=0, stdout='{"results": []}'))
    mocker.patch.object(PhantomOSINTNode, '_emit_telemetry')
    node = PhantomOSINTNode({'logger': None})
    node._execute_theharvester({'domain': 'ejemplo.com'})
    assert node._emit_telemetry.call_count == 3  # iniciando, procesando, finalizado

def test_execute_theharvester_invalid_params(mocker):
    mocker.patch.object(PhantomOSINTNode, '_emit_telemetry')
    node = PhantomOSINTNode({'logger': None})
    node._execute_theharvester({})
    node._emit_telemetry.assert_called_with('error', {'message': 'Parámetro "domain" es obligatorio para theHarvester.'})
```

**Dependencias:**
- `subprocess` (para ejecutar comandos en la terminal).
- `asyncio` o `threading` (para ejecución asíncrona).

---

### **Tarea 5: Manejo de Errores y Excepciones**
**Descripción:**
Implementar el método `_handle_error` para centralizar el manejo de errores y excepciones.

**Criterios de Aceptación:**
| **ID**  | **Escenario**                                                                                     | **Criterio de Aceptación**                                                                         |
|---------|-------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------|
| TA5-001 | **GIVEN** una excepción inesperada, **WHEN** se maneja, **THEN** debe emitir un evento `error` con detalles de la excepción. | El nodo emite un evento `error` con la traza completa de la excepción.                           |
| TA5-002 | **GIVEN** un error de herramienta no instalada, **WHEN** se maneja, **THEN** debe emitir un evento `error` con un mensaje claro. | El nodo emite un evento `error` indicando que la herramienta no está instalada.                 |

**Pruebas Unitarias:**
```python
# tests/test_error_handling.py
def test_handle_error_exception(mocker):
    mocker.patch.object(PhantomOSINTNode, '_emit_telemetry')
    node = PhantomOSINTNode({'logger': None})
    try:
        raise Exception("Error inesperado")
    except Exception as e:
        node._handle_error(e)
    node._emit_telemetry.assert_called_with('error', {'message': 'Excepción inesperada: Error inesperado'})

def test_handle_error_tool_not_installed(mocker):
    mocker.patch.object(PhantomOSINTNode, '_emit_telemetry')
    node = PhantomOSINTNode({'logger': None})
    node._handle_error(Exception("Herramienta 'phoneinfoga' no instalada"))
    node._emit_telemetry.assert_called_with('error', {'message': 'Herramienta no instalada'})
```

**Dependencias:**
- `logging` (para registrar errores en el logger).

---

### **Tarea 6: Integración con el Servidor**
**Descripción:**
Implementar el método `start` para recibir comandos del servidor y orquestar la ejecución de las herramientas OSINT.

**Criterios de Aceptación:**
| **ID**  | **Escenario**                                                                                     | **Criterio de Aceptación**                                                                         |
|---------|-------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------|
| TA6-001 | **GIVEN** un comando válido, **WHEN** se inicia el nodo, **THEN** debe ejecutar la herramienta OSINT correspondiente. | El nodo ejecuta la herramienta OSINT y emite eventos de telemetría.                              |
| TA6-002 | **GIVEN** un comando inválido, **WHEN** se inicia el nodo, **THEN** debe emitir un evento `error`. | El nodo emite un evento `error` y no inicia la ejecución.                                        |

**Pruebas Unitarias:**
```python
# tests/test_integration.py
def test_start_node_success(mocker):
    mocker.patch.object(PhantomOSINTNode, '_execute_phoneinfoga')
    node = PhantomOSINTNode({'logger': None})
    node.start({'tool': 'phoneinfoga', 'params': {'target': '1234567890'}})
    node._execute_phoneinfoga.assert_called_once_with({'target': '1234567890'})

def test_start_node_invalid_command(mocker):
    mocker.patch.object(PhantomOSINTNode, '_emit_telemetry')
    node = PhantomOSINTNode({'logger': None})
    node.start({'tool': 'unknown_tool', 'params': {}})
    node._emit_telemetry.assert_called_with('error', {'message': 'Herramienta OSINT no soportada: unknown_tool'})
```

**Dependencias:**
- `servidor_ame.py` (para recibir comandos mediante WebSocket).

---

### **Tarea 7: Pruebas de Integración**
**Descripción:**
Validar la integración completa del nodo con el servidor y las herramientas OSINT.

**Criterios de Aceptación:**
| **ID**  | **Escenario**                                                                                     | **Criterio de Aceptación**                                                                         |
|---------|-------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------|
| TA7-001 | **GIVEN** un entorno de prueba con el servidor y el nodo, **WHEN** se envía un comando OSINT, **THEN** debe ejecutarse correctamente y emitir telemetría. | El servidor recibe eventos `telemetry` del nodo y los reenvía al dashboard.                        |
| TA7-002 | **GIVEN** un error en la integración, **WHEN** ocurre, **THEN** debe manejarse sin afectar el sistema. | El sistema principal no crashtea y el error se registra correctamente.                              |

**Pruebas de Integración:**
```python
# tests/test_integration_full.py
def test_integration_full(mocker, event_loop):
    # Configurar mocks para el servidor y el nodo
    mocker.patch('socketio.emit')
    mocker.patch('subprocess.run', return_value=Mock(returncode=0, stdout='{"result": "success"}'))

    # Iniciar el nodo
    node = PhantomOSINTNode({'logger': None})

    # Simular un comando del servidor
    command = {'tool': 'phoneinfoga', 'params': {'target': '1234567890'}}
    node.start(command)

    # Verificar que se emitieron los eventos de telemetría
    assert socketio.emit.call_count == 3  # iniciando, procesando, finalizado
```

**Dependencias:**
- `pytest` (para pruebas de integración).
- `event_loop` (para pruebas asíncronas).

---

## 📌 **Resumen de Constraints y Restricciones**
### **1. Constraints Técnicas**
| **Constraint**               | **Descripción**                                                                                     | **Impacto en el Diseño**                                                                              |
|------------------------------|-------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------|
| **Asincronía**               | Ejecución no bloqueante de herramientas OSINT.                                                    | Uso de `asyncio` o `threading` para procesos en segundo plano.                                      |
| **Telemetría en Tiempo Real**| Comunicación bidireccional con el dashboard mediante WebSocket.                                   | Implementación de `_emit_telemetry` con eventos estructurados.                                    |
| **Resiliencia**              | Manejo de errores y excepciones sin afectar el sistema principal.                                  | Centralización de errores en `_handle_error` y uso de try/except en todos los métodos.              |
| **Entorno Restringido**     | Uso exclusivo del entorno virtual `env/` y herramientas instaladas localmente.                     | Validación de herramientas antes de ejecutarlas.                                                   |
| **Integración con MCP**      | Compatibilidad con el protocolo MCP para comunicación avanzada.                                   | Diseño modular para facilitar la integración futura con MCP.                                       |

### **2. Non-Goals (Fuera de Alcance)**
| **ID**  | **Descripción**                                                                                     |
|---------|-------------------------------------------------------------------------------------------------|
| NG-001  | Implementación de autenticación avanzada en el nodo.                                               |
| NG-002  | Soporte para herramientas OSINT externas no instaladas en el entorno virtual (`env/`).              |
| NG-003  | Integración con bases de datos externas o APIs de terceros.                                        |
| NG-004  | Desarrollo de una interfaz gráfica para el nodo.                                                   |
| NG-005  | Implementación de mecanismos de persistencia de datos más allá de la memoria del proceso.         |

---

## 📌 **Próximos Pasos**
1. **Implementación de Tareas:** Aplicar Strict TDD para cada tarea (escribir test primero, ejecutar, implementar, verificar).
2. **Integración con el Servidor:** Validar la comunicación bidireccional entre el nodo y `servidor_ame.py`.
3. **Pruebas de Integración:** Ejecutar pruebas de integración para asegurar que el nodo funcione correctamente en el ecosistema AURA.
4. **Documentación Final:** Generar un informe técnico con las decisiones de diseño y restricciones para el equipo Venice.

**¡Listo para iniciar la implementación con Strict TDD!**