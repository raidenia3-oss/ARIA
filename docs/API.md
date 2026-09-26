# AURA OS v2.0 — API Reference

## Índice

1. [Autenticación](#autenticación)
2. [Chat API](#chat-api)
3. [Skills API](#skills-api)
4. [Voice API](#voice-api)
5. [Vision API](#vision-api)
6. [Plugins API](#plugins-api)
7. [Automation API](#automation-api)
8. [Kilo Agent API](#kilo-agent-api)
9. [Status & Health](#status--health)
10. [Error Handling](#error-handling)

---

## Autenticación

### Tokens JWT

Los endpoints protegidos requieren token JWT en el header:

```bash
Authorization: Bearer <token>
```

### Obtener Token

```bash
POST /api/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "password123"
}
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### Usar Token

```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/protected-endpoint
```

---

## Chat API

### POST /api/chat

Procesar mensaje con ReAct Loop.

**Request:**
```json
{
  "message": "¿Cuál es mi IP?",
  "context": {
    "user_id": "user123",
    "session": "session456"
  },
  "model": "local"
}
```

**Response:**
```json
{
  "response": "Tu IP local es 192.168.1.100 y tu IP pública es 203.0.113.42",
  "thinking": "El usuario quiere saber su IP. Usaré el skill de scan.",
  "skills_used": ["scan", "whois"],
  "tokens": {
    "input": 45,
    "output": 78,
    "total": 123
  },
  "timestamp": "2024-08-31T12:34:56Z",
  "latency_ms": 1240
}
```

**Status Codes:**
- `200` — Success
- `400` — Invalid message
- `500` — Backend error
- `503` — Service unavailable

**Ejemplos:**

```bash
# Chat simple
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hola, ¿cómo estás?"}'

# Chat con contexto
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Abre Firefox",
    "context": {"user": "admin"}
  }'

# Especificar modelo
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "¿Qué fecha es?",
    "model": "groq"
  }'
```

---

## Skills API

### GET /api/skills

Listar todos los skills disponibles.

**Response:**
```json
{
  "skills": [
    {
      "name": "status",
      "description": "Información del sistema",
      "category": "system",
      "enabled": true,
      "metrics": {
        "executions": 42,
        "success_rate": 0.98,
        "avg_latency_ms": 125
      }
    },
    {
      "name": "ping",
      "description": "Ping a host",
      "category": "network",
      "enabled": true,
      "metrics": {
        "executions": 18,
        "success_rate": 1.0,
        "avg_latency_ms": 250
      }
    }
  ],
  "total": 16,
  "categories": ["system", "network", "app", "media", "utility"]
}
```

### POST /api/skills/{skill_name}

Ejecutar un skill específico.

**Request:**
```json
{
  "host": "google.com",
  "timeout": 5
}
```

**Response:**
```json
{
  "skill": "ping",
  "status": "success",
  "result": {
    "host": "google.com",
    "time_ms": 45.2,
    "packets_sent": 4,
    "packets_received": 4,
    "packet_loss": 0.0
  },
  "execution_time_ms": 1240,
  "timestamp": "2024-08-31T12:34:56Z"
}
```

**Ejemplos:**

```bash
# Ejecutar skill status
curl -X POST http://localhost:8000/api/skills/status

# Ejecutar skill con parámetros
curl -X POST http://localhost:8000/api/skills/ping \
  -H "Content-Type: application/json" \
  -d '{"host": "8.8.8.8"}'

# Ejecutar skill scan
curl -X POST http://localhost:8000/api/skills/scan \
  -H "Content-Type: application/json" \
  -d '{"network": "192.168.1.0/24"}'
```

---

## Voice API

### POST /api/voice/tts

Síntesis de voz (Text-to-Speech).

**Request:**
```json
{
  "text": "Hola, ¿cómo estás?",
  "lang": "es",
  "speed": 1.0,
  "pitch": 1.0
}
```

**Response:**
```json
{
  "audio_base64": "//NExAAUAIIAkABAAH+AAAB/...",
  "format": "mp3",
  "duration_ms": 2400,
  "timestamp": "2024-08-31T12:34:56Z"
}
```

### GET /api/voice/listen

Escuchar micrófono y transcribir.

**Query Params:**
- `duration`: segundos a grabar (default: 5)
- `language`: código de idioma (default: "es")

**Response:**
```json
{
  "text": "¿Cuál es mi IP?",
  "confidence": 0.95,
  "language": "es",
  "duration_ms": 4500,
  "timestamp": "2024-08-31T12:34:56Z"
}
```

---

## Vision API

### POST /api/vision/capture

Capturar pantalla y analizar.

**Request:**
```json
{
  "region": null,
  "analyze": true
}
```

**Response:**
```json
{
  "image_base64": "iVBORw0KGgoAAAANSUhEUg...",
  "format": "png",
  "width": 1920,
  "height": 1080,
  "analysis": {
    "text_detected": ["AURA OS v2.0", "Skills", "Status"],
    "objects": ["window", "button", "text"],
    "description": "Pantalla de AURA OS mostrando el dashboard"
  },
  "timestamp": "2024-08-31T12:34:56Z"
}
```

### POST /api/vision/analyze

Analizar imagen con IA.

**Request:**
```json
{
  "image_base64": "...",
  "question": "¿Qué hay en la pantalla?"
}
```

**Response:**
```json
{
  "answer": "La pantalla muestra el dashboard de AURA OS con el orb animado, skills activos, y eventos en tiempo real.",
  "confidence": 0.92,
  "details": {
    "objects": ["orb", "skills_grid", "event_log"],
    "text": ["AURA OS", "Skills", "Events"]
  },
  "timestamp": "2024-08-31T12:34:56Z"
}
```

---

## Plugins API

### GET /api/plugins

Listar plugins activos.

**Response:**
```json
{
  "example_plugin": {
    "name": "Example Plugin",
    "version": "1.0.0",
    "description": "Plugin de ejemplo",
    "file": "backend/plugins/custom/example_plugin.py",
    "loaded_at": "2024-08-31T10:00:00Z",
    "hooks": ["on_startup", "on_chat", "on_skill_execute", "on_shutdown"]
  }
}
```

### POST /api/plugins/reload

Recargar todos los plugins.

**Response:**
```json
{
  "status": "plugins_reloaded",
  "count": 1,
  "plugins": ["example_plugin"],
  "timestamp": "2024-08-31T12:34:56Z"
}
```

### DELETE /api/plugins/{plugin_name}

Descargar un plugin.

**Response:**
```json
{
  "status": "plugin_unloaded",
  "plugin": "example_plugin",
  "timestamp": "2024-08-31T12:34:56Z"
}
```

---

## Automation API

### POST /api/automation/rules

Crear regla de automatización.

**Request:**
```json
{
  "name": "morning_briefing",
  "description": "Briefing matutino",
  "trigger": {
    "type": "on_time",
    "hour": 9,
    "minute": 0,
    "days": ["monday", "tuesday", "wednesday", "thursday", "friday"]
  },
  "actions": [
    {
      "type": "chat",
      "message": "Buenos días, ¿cuál es mi agenda?"
    },
    {
      "type": "skill",
      "skill": "weather"
    }
  ],
  "enabled": true,
  "tags": ["morning", "routine"]
}
```

**Response:**
```json
{
  "status": "rule_created",
  "rule_id": "ea9f5340",
  "rule_name": "morning_briefing",
  "timestamp": "2024-08-31T12:34:56Z"
}
```

### GET /api/automation/rules

Listar reglas (con filtros).

**Query Params:**
- `enabled_only`: boolean (listar solo habilitadas)
- `tag`: string (filtrar por tag)

**Response:**
```json
{
  "ea9f5340": {
    "id": "ea9f5340",
    "name": "morning_briefing",
    "trigger": {...},
    "actions": [...],
    "enabled": true,
    "execution_count": 5,
    "last_executed": "2024-08-31T09:00:00Z",
    "last_error": null
  }
}
```

### POST /api/automation/test/{rule_id}

Ejecutar regla manualmente.

**Response:**
```json
{
  "status": "executed",
  "success": true,
  "rule_id": "ea9f5340",
  "execution_count": 6,
  "duration_ms": 1240,
  "last_error": null
}
```

---

## Kilo Agent API

### POST /api/agents/kilo/delegate

Delegar tarea a Kilo.

**Request:**
```json
{
  "task_id": "task-8f3k",
  "objective": "Crear script Python que descargue datos de una API",
  "context": {
    "api_url": "https://jsonplaceholder.typicode.com/posts",
    "output_format": "csv"
  },
  "required_tools": ["python", "curl", "jq"],
  "timeout": 300
}
```

**Response:**
```json
{
  "task_id": "task-8f3k",
  "status": "delegated",
  "objective": "Crear script Python que descargue datos de una API",
  "prompt_file": "kilo_prompts/task-8f3k.md"
}
```

### POST /api/agents/kilo/callback

Recibir resultado de Kilo (callback).

**Request:**
```json
{
  "task_id": "task-8f3k",
  "status": "completed",
  "result": {"output": "script.py created"},
  "duration": 45
}
```

**Response:**
```json
{
  "status": "received"
}
```

### GET /api/agents/kilo/status/{task_id}

Ver estado de tarea.

**Response:**
```json
{
  "task_id": "task-8f3k",
  "status": "completed",
  "objective": "Crear script Python que descargue datos de una API",
  "completed_at": "2024-08-31T12:35:41Z",
  "duration": 45
}
```

### GET /api/agents/kilo/history

Ver historial de tareas.

**Query Params:**
- `limit`: número de tareas (default: 50)

**Response:**
```json
[
  {
    "task_id": "task-8f3k",
    "status": "completed",
    "result": {...},
    "duration": 45
  },
  {
    "task_id": "task-7e2j",
    "status": "completed",
    "result": {...},
    "duration": 120
  }
]
```

---

## Status & Health

### GET /health

Estado general del sistema.

**Response:**
```json
{
  "status": "healthy",
  "service": "aura-news-api"
}
```

### GET /api/health

Health check detallado.

**Response:**
```json
{
  "status": "ok",
  "mode": "aura-app-v2",
  "timestamp": "2024-08-31T12:34:56Z"
}
```

### GET /api/status

Status detallado del sistema.

**Response:**
```json
{
  "backend": "running",
  "cpu": 21.4,
  "memory": {
    "short_term": 0,
    "long_term": 0
  },
  "disk": 75.2,
  "mode": "aura-app-v2",
  "version": "2.0.0",
  "ai": {
    "enabled": true,
    "providers": ["local"],
    "best": "local"
  },
  "skills": 16
}
```

---

## Error Handling

### Error Response Format

Todos los errores retornan este formato:

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Message parameter is required",
    "details": {
      "field": "message",
      "reason": "empty"
    },
    "timestamp": "2024-08-31T12:34:56Z"
  }
}
```

### Errores Comunes

| Código | Status | Descripción |
|--------|--------|-------------|
| `INVALID_REQUEST` | 400 | Parámetros inválidos |
| `UNAUTHORIZED` | 401 | Falta token o inválido |
| `FORBIDDEN` | 403 | Sin permisos |
| `NOT_FOUND` | 404 | Recurso no encontrado |
| `CONFLICT` | 409 | Conflicto (duplicado, etc) |
| `RATE_LIMITED` | 429 | Demasiadas requests |
| `INTERNAL_ERROR` | 500 | Error interno |
| `SERVICE_UNAVAILABLE` | 503 | Backend no disponible |

### Ejemplo Manejo de Errores

```bash
# Request con error
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{}'

# Response
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "message field is required",
    "details": {"field": "message"},
    "timestamp": "2024-08-31T12:34:56Z"
  }
}
```

---

## Rate Limiting

API tiene rate limiting por usuario:

- **Free tier**: 100 requests/hour
- **Premium**: 1000 requests/hour

Los endpoints críticos (chat, skills) tienen límites adicionales:
- `/api/chat`: 20 requests/minute por IP
- `/api/skills/*`: 60 requests/minute por IP

Header de respuesta para tracking:
```
X-RateLimit-Limit: 20
X-RateLimit-Remaining: 19
X-RateLimit-Reset: 1693502400
```
