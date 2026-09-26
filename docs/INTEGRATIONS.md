# Integraciones APIs - Documentación

## Slack Bot

### Eventos Soportados
- `/api/slack/events` - Webhook para eventos de Slack
- Verificación de URL challenge
- Procesamiento de mensajes

### Comandos
- `/ame-status` - Estado del sistema AME
- `/ame-health` - Health check

---

## Discord Bot

### Webhook
- `/api/discord/webhook` - Endpoint para mensajes entrantes

### Comandos
- `!ame-status` - Estado general
- `!ame-help` - Ayuda

---

## Telegram Bot

### Webhook
- `/api/telegram/webhook` - Recibir mensajes

### Comandos
- `/ame` - Estado
- `/help` - Ayuda

---

## Teams

### Instalación
- `/api/teams` - App manifest y configuración

### Actividad
- Proactive messaging
- Task modules

---

## Webhooks Generales

### Endpoint
- `POST /api/webhooks` - Registrar webhook
- Ver eventos guardados en logs

### Ejemplo
```json
{
  "event": "test",
  "data": {}
}
```

---

## Health Check

- `GET /api/health` - Estado del sistema

## AME Core

- `GET /api/ame-core` - Núcleo AME