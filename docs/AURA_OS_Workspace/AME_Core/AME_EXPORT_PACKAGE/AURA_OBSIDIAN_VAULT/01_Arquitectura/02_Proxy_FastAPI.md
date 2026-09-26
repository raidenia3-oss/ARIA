# Proxy FastAPI - Orquestador Central

Este documento describe el módulo central del ecosistema AURA/AME: el **Proxy FastAPI**, implementado en `core/server.py`. Este módulo actúa como orquestador central, proxy y punto de sincronización para todos los componentes del ecosistema.

## 🔧 Funcionalidades Principales

### 1. Proxy Compatible con OpenAI

El proxy implementa el estándar OpenAI para que las aplicaciones móviles puedan interactuar con modelos de lenguaje sin necesidad de conocer los detalles de implementación.

- **Endpoint**: `POST /v1/chat/completions`
- **Compatibilidad**: Las apps móviles (App Maid y APK AME) consumen este endpoint como si fuera un servicio OpenAI estándar.

### 2. Sincronización de Agentes

El proxy recibe datos de sincronización del agente de Termux y los procesa.

- **Endpoint**: `POST /v1/agent/sync`
- **Funcionalidades**:
  - Recepción de datos del agente de Termux.
  - Procesamiento y almacenamiento en memoria.
  - Sincronización bidireccional con el agente.

### 3. Consulta de Estado

Permite consultar el estado de los agentes conectados.

- **Endpoint**: `GET /v1/agent/status`
- **Respuesta**: JSON con información de estado de todos los agentes conectados.

### 4. Lista de Modelos

Proporciona información sobre los modelos disponibles.

- **Endpoint**: `GET /v1/models`
- **Funcionalidades**:
  - Lista de modelos gratuitos disponibles (Llama-3, Qwen-Coder, Mistral).
  - Rotación automática de modelos para evitar bloqueos.

### 5. Health Check

Endpoint para verificar el estado del servidor.

- **Endpoint**: `GET /health`
- **Respuesta**: JSON con información de estado del servidor.

## 🔄 Flujo de Datos

1. **Sincronización del Agente de Termux**:
   - El agente envía datos mediante `POST /v1/agent/sync`.
   - El proxy procesa los datos y los almacena en memoria.

2. **Interacción con Modelos**:
   - Las apps móviles envían solicitudes a `POST /v1/chat/completions`.
   - El proxy redirige las solicitudes a los modelos de lenguaje disponibles.

3. **Consulta de Estado**:
   - Las apps móviles pueden consultar el estado del agente mediante `GET /v1/agent/status`.

## 🛠 Configuración

### Variables de Entorno

El proxy utiliza las siguientes variables de entorno:

| Variable               | Descripción                                                     |
| ---------------------- | --------------------------------------------------------------- |
| `SERVER_URL`           | URL base del servidor (ej: `http://192.168.1.100:8000`).        |
| `MODELS`               | Lista de modelos disponibles (ej: `llama3,mistral,qwen-coder`). |
| `SYSTEM_PROMPT`        | Prompt de sistema para los modelos.                             |
| `OUTPUT_CLEANER_REGEX` | Regex para limpiar la salida de los modelos.                    |

### Ejemplo de Configuración

```bash
export SERVER_URL="http://192.168.1.100:8000"
export MODELS="llama3,mistral,qwen-coder"
export SYSTEM_PROMPT="Eres un asistente de auditoría de infraestructura..."
export OUTPUT_CLEANER_REGEX="\b(?:password|passwd|secret|token|key)\b.*?\n"
```

## 🔗 Enlaces Relacionados

- [[01_Arquitectura_General]]
- [[03_Nodo_Termux]]
- [[04_Apps_Móviles]]

## 📌 Notas Importantes

- **Seguridad**: Todos los endpoints están protegidos y solo accesibles desde dispositivos autorizados.
- **Uso legítimo**: Este proxy está diseñado para auditoría y gestión de infraestructura propia.
- **Enlaces internos**: Utiliza el formato `[[Archivo]]` para mantener la integridad del grafo de Obsidian.
