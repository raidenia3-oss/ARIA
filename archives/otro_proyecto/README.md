# Otro Proyecto

Este es un proyecto separado del repositorio principal `TRAIN`. Está dentro de su propia carpeta para que no se mezclen los archivos.

## Uso

1. Abre solo la carpeta `otro_proyecto` en VS Code.
2. Usa el comando de VS Code "Dev Containers: Reopen in Container" para ejecutar este proyecto dentro de un contenedor.

## Contenedor

El proyecto incluye un archivo `.devcontainer/devcontainer.json` y un `Dockerfile` para que VS Code pueda construir y abrir el contenedor automáticamente.

## Worker en segundo plano

El archivo `aura_worker.pyw` es el worker que se debe ejecutar en segundo plano cuando la PC esté encendida.

### Pasos para ponerlo en segundo plano en Windows

1. Instala las dependencias:

```bash
pip install -r requirements.txt
python -m playwright install
```

2. Configura tus credenciales de Upstash Redis en `aura_worker.pyw`:

```python
redis = Redis(url="TU_URL_AQUI", token="TU_TOKEN_AQUI")
```

3. Para ejecutarlo sin consola, usa `pythonw.exe`:

```powershell
pythonw .\aura_worker.pyw
```

4. Para iniciar automáticamente cuando prendes la PC, usa el Programador de tareas (Task Scheduler):

- Abre "Task Scheduler".
- Crea una tarea básica.
- Elige "When I log on" o "At startup".
- En "Action" selecciona "Start a program".
- Programa:
  - `Program/script`: `pythonw`
  - `Add arguments`: `C:\Users\User\Downloads\TRAIN\otro_proyecto\aura_worker.pyw`
  - `Start in`: `C:\Users\User\Downloads\TRAIN\otro_proyecto`

5. Guarda la tarea y prueba reiniciar o iniciar sesión.

## Control remoto desde Vercel / GitHub

Tu app en Vercel puede enviar tareas al worker usando Redis. El worker lee la lista `aura_tasks` y ejecuta acciones cuando encuentra una orden.

Ejemplo de envío con Python:

```python
import json
from upstash_redis import Redis

redis = Redis(url="TU_URL_AQUI", token="TU_TOKEN_AQUI")
redis.rpush("aura_tasks", json.dumps({"action": "start_rollercoin"}))
```

El worker procesará esa orden en cuanto la PC esté encendida y el script esté ejecutándose. Usa `pythonw` en la máquina para que el proceso permanezca invisible.

### Registro y depuración

El worker escribe logs en `aura_worker.log` dentro de la carpeta `otro_proyecto`.

### Nota

El archivo `.pyw` hace que no aparezca ventana de consola, perfecto para ejecutarlo en segundo plano.
