# AURA - Arquitectura Completa

## Estado actual

### Backend (FastAPI)
- `/health` - Estado del sistema
- `/api/discovery` - Descubrimiento de backend (publico)
- `/api/status` - Estado de servicios
- `/api/chat` - Chat con memoria y router de IAs
- `/api/chat/stream` - Chat con streaming SSE
- `/api/ai` - Modelo local Qwen 0.5B
- `/api/conversations` - Gestion de memoria conversacional
- `/api/feedback` - Feedback de respuestas
- Router de IAs: Qwen 0.5B -> Groq -> Gemini -> OpenRouter -> Ollama -> local

### Discord Bot (Ruby)
- Comandos: /status, /logs, /restart, /deploy, /chat, /feedback
- Listo para cloud (Fly.io/Railway)
- docker-compose.yml incluido

### Godot Desktop
- Discovery automatico local/cloud
- Streaming SSE para chat
- Cache de conversaciones
- Reconexion automatica

### Godot Android
- Cliente cloud via HTTP
- Export listo para APK/AAB
- Sin modelo local (consulta backend)

## Como funciona sin PC encendida

1. Backend hosteado en Fly.io/Railway
2. Modelo Qwen 0.5B en el backend cloud
3. Discord bot en cloud
4. Godot Android se conecta al backend cloud
5. Godot Desktop se conecta al backend cloud

## Como funciona con PC encendida

1. Backend local en localhost:8000 (opcional)
2. Modelo local Qwen 0.5B (opcional)
3. Godot Desktop prefiere backend local
4. Si local falla, usa cloud automaticamente

## Deployment rapido

### 1. Cloud (Fly.io)
```bash
# Backend
fly apps create aura-backend
fly volumes create aura_models --size 2 --region iad
fly secrets set AURA_API_KEY=tu-api-key
fly deploy -C backend

# Discord bot
fly apps create aura-discord-bot
fly secrets set DISCORD_BOT_TOKEN=tu-token
fly deploy -C services/discord-bot
```

### 2. Android
- Exportar desde Godot 4.6
- Instalar APK
- Se conecta automaticamente al backend cloud

## Costos
- Fly.io backend: $0-3/mes
- Discord bot: $0
- Total: $0-5/mes

## Archivos clave
- Backend: `backend/main.py`
- Discord bot: `services/discord-bot/bot.rb`
- Godot client: `godot/scripts/network/aura_client.gd`
- Docker cloud: `docker-compose.cloud.yml`
- Docs: `docs/deployment.md`, `docs/architecture.md`
