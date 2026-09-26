# Nodo Termux - Agente Ligero

Este documento describe el **Nodo Termux**, implementado en `ame_termux_node.py`, que actúa como cliente ligero para consumir los endpoints del servidor central desde un dispositivo con Termux.

## 🔧 Funcionalidades Principales

### 1. Sincronización Bidireccional

El nodo Termux se encarga de sincronizar datos con el servidor central.

- **Endpoint consumido**: `POST /v1/agent/sync`
- **Funcionalidades**:
  - Envío de datos de telemetría y eventos.
  - Recepción de comandos y actualizaciones del servidor.
  - Sincronización de configuración y estado.

### 2. Consumo de Endpoints del Servidor

El nodo consume los endpoints del servidor central para interactuar con los modelos de lenguaje.

- **Endpoint consumido**: `POST /v1/chat/completions`
- **Funcionalidades**:
  - Interacción con modelos de lenguaje disponibles.
  - Envío de consultas y recepción de respuestas.

### 3. Integración con Herramientas de Termux

El nodo está diseñado para integrarse con herramientas nativas de Termux.

- **Funcionalidades**:
  - Uso de ganchos nativos de Termux.
  - Ejecución de comandos locales.
  - Integración con scripts de automatización.

## 🔄 Flujo de Operación

1. **Inicialización**:
   - El nodo se inicia y establece conexión con el servidor central.
   - Se configura la sincronización bidireccional.

2. **Sincronización**:
   - El nodo envía datos de telemetría y eventos al servidor.
   - Recibe comandos y actualizaciones del servidor.

3. **Interacción con Modelos**:
   - El nodo envía consultas al servidor mediante `POST /v1/chat/completions`.
   - Recibe respuestas de los modelos de lenguaje.

4. **Procesamiento Local**:
   - Ejecución de comandos locales en el dispositivo Termux.
   - Integración con herramientas de Termux.

## 🛠 Configuración

### Variables de Entorno

El nodo Termux utiliza las siguientes variables de entorno:

| Variable      | Descripción                                                 |
| ------------- | ----------------------------------------------------------- |
| `SERVER_URL`  | URL del servidor central (ej: `http://192.168.1.100:8000`). |
| `AGENT_ID`    | Identificador único del agente.                             |
| `TERMUX_HOME` | Ruta base de la instalación de Termux.                      |

### Ejemplo de Configuración

```bash
export SERVER_URL="http://192.168.1.100:8000"
export AGENT_ID="termux-node-001"
export TERMUX_HOME="$HOME/.termux"
```

### Archivo de Configuración

El nodo utiliza un archivo de configuración JSON (`ame_config_template.json`) para definir parámetros adicionales.

```json
{
  "sync_interval": 30,
  "max_retries": 3,
  "timeout": 10,
  "hooks": {
    "on_start": ["echo 'Nodo Termux iniciado'"],
    "on_sync": ["date >> /sdcard/ame_sync.log"]
  }
}
```

## 🔗 Enlaces Relacionados

- [[01_Arquitectura_General]]
- [[02_Proxy_FastAPI]]
- [[04_Apps_Móviles]]

## 📌 Notas Importantes

- **Seguridad**: El nodo debe configurarse para conectarse solo a servidores autorizados.
- **Uso legítimo**: Este nodo está diseñado para auditoría y gestión de infraestructura propia.
- **Enlaces internos**: Utiliza el formato `[[Archivo]]` para mantener la integridad del grafo de Obsidian.
- **Instalación**: Para instalar el nodo, sigue las instrucciones en `[[02_Configuracion/03_Instalacion_Termux]]`.
