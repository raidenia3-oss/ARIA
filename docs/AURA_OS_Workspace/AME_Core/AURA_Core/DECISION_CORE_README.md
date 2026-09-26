# Decision Core - AURA

## Descripción

El Decision Core es el módulo central de toma de decisiones del sistema AURA. Gestiona tareas, recursos del sistema, caché y proporciona funcionalidad de "Modo Fantasma" para operaciones silenciosas.

## Características Principales

### 1. Gestión de Tareas

- **Cola de Prioridad**: Sistema de cola con prioridades (CRITICAL, HIGH, MEDIUM, LOW)
- **Procesamiento Concurrente**: Hilo dedicado para procesamiento de tareas
- **Reintentos**: Sistema automático de reintentos con límite configurable

### 2. Monitoreo de Recursos

- **CPU y Memoria**: Monitoreo en tiempo real del uso de recursos
- **Alertas**: Notificaciones cuando se superan umbrales críticos
- **Métricas**: Estadísticas detalladas de rendimiento

### 3. Sistema de Caché

- **Caché LRU**: Algoritmo Least Recently Used para gestión eficiente
- **TTL Configurable**: Tiempo de vida para entradas de caché
- **Estadísticas**: Hits, misses y tamaño actual de caché

### 4. Modo Fantasma

- **Operación Silenciosa**: Modo de ejecución discreta
- **Estado Persistente**: Mantenimiento de estado entre sesiones
- **Configuración Avanzada**: Parámetros ajustables para diferentes escenarios

### 5. Configuración Flexible

- **Archivos JSON**: Configuración personalizable mediante archivos JSON
- **Valores por Defecto**: Configuración segura predeterminada
- **Hot Reload**: Recarga de configuración sin reiniciar

## Archivos

### `decision_core.py`

Módulo principal que contiene la clase `DecisionCore` y todas sus funcionalidades.

### `test_decision_core.py`

Script de pruebas que valida el correcto funcionamiento del sistema.

### `run_decision_core.bat`

Script de inicio para Windows que ejecuta el Decision Core en el entorno virtual.

### `install_dependencies.bat`

Script para instalar todas las dependencias necesarias.

## Configuración

### Parámetros Disponibles

```json
{
  "max_tasks": 100, // Máximo de tareas en cola
  "cache_size": 1000, // Tamaño máximo de caché
  "monitoring_interval": 60, // Intervalo de monitoreo (segundos)
  "ghost_mode_timeout": 300, // Timeout del modo fantasma
  "max_retries": 3, // Intentos máximos por tarea
  "retry_delay": 5, // Delay entre reintentos
  "high_priority_timeout": 10, // Timeout para tareas de alta prioridad
  "medium_priority_timeout": 30, // Timeout para tareas de prioridad media
  "low_priority_timeout": 60 // Timeout para tareas de baja prioridad
}
```

### Ejemplo de Configuración Personalizada

Crear un archivo `config.json` en el directorio de trabajo:

```json
{
  "max_tasks": 50,
  "cache_size": 500,
  "monitoring_interval": 30
}
```

## Uso

### Iniciar el Decision Core

```bash
# Usando el script de Windows
.\run_decision_core.bat

# O directamente con Python
python decision_core.py
```

### Ejecutar Pruebas

```bash
# Usando el entorno virtual
.\venv_decision_core\Scripts\activate
python test_decision_core.py
```

### Ejemplos de Código

```python
from decision_core import DecisionCore, TaskPriority

# Crear instancia
core = DecisionCore()

# Iniciar el sistema
core.start()

# Añadir tarea
def mi_tarea():
    return {"resultado": "éxito"}

task_id = core.add_task(mi_tarea, TaskPriority.HIGH)

# Activar modo fantasma
core.toggle_ghost_mode()

# Obtener métricas
metrics = core.get_metrics()
print(f"Tareas procesadas: {metrics['tasks_processed']}")

# Detener el sistema
core.stop()
```

## API

### Métodos Principales

| Método                       | Descripción                    |
| ---------------------------- | ------------------------------ |
| `start()`                    | Inicia el Decision Core        |
| `stop()`                     | Detiene el Decision Core       |
| `add_task(func, priority)`   | Añade una tarea a la cola      |
| `toggle_ghost_mode()`        | Activa/desactiva modo fantasma |
| `get_status()`               | Obtiene el estado actual       |
| `get_metrics()`              | Obtiene métricas del sistema   |
| `get_cached_result(task_id)` | Obtiene resultado de caché     |

### Prioridades de Tarea

| Prioridad | Nivel | Uso Recomendado             |
| --------- | ----- | --------------------------- |
| CRITICAL  | 1     | Tareas críticas del sistema |
| HIGH      | 2     | Tareas importantes          |
| MEDIUM    | 3     | Tareas estándar             |
| LOW       | 4     | Tareas de fondo             |

## Dependencias

- Python 3.7+
- psutil
- flask-socketio (opcional, para API web)

## Instalación de Dependencias

```bash
# Usando el script de Windows
.\install_dependencies.bat

# O manualmente
pip install psutil flask-socketio
```

## Solución de Problemas

### Error: "No module named 'psutil'"

```bash
pip install psutil
```

### Error: "config.json not found"

El sistema creará automáticamente una configuración por defecto.

### Alto uso de CPU/Memoria

- Reducir `monitoring_interval` en `config.json`
- Disminuir `max_tasks` si es necesario
- Verificar tareas en ejecución

## Licencia

Parte del ecosistema AURA - Licencia MIT
