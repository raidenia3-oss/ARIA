# Discord Bot — Handoff / Prompt para siguiente agente

## Estado actual
- Ruby 3.3 instalado en `C:\Ruby33-x64` (wingit + ridk install devtoolchain).
- Gems instaladas: discordrb ~> 3.4, redis ~> 5.0, dotenv ~> 2.8, httparty ~> 0.21.
- `bundle install` completado en `services/discord-bot/`.
- Specs pasan (5/5) con `skip_registration` para evitar registro real de commands en tests.
- Código listo en `bot.rb`, `Gemfile`, `Dockerfile`, `.env.example`, `start.bat`.

### Comandos literarios implementados
- `/story status` — Consulta el contexto literario activo (work + character) para la sesión Discord.
- `/story set-work` — Vincula una obra (y opcionalmente personaje) a la sesión Discord.
- `/story set-character` — Cambia el personaje activo sin cambiar la obra.
- `/story check-coherence` — Valida un texto contra la Character Bible y el canon.
- `/story persona` — Invoca la voz/personalidad de un personaje registrado (Character Bible) en el canal.
- `/story canon` — Lista los eventos de canon de la obra activa.
- `/story unbind` — Desvincula el contexto literario de la sesión Discord.

### Pipeline de notas de voz a canon (BLOQUE 28)
- Intercepta adjuntos de audio (`.ogg`, `.mp3`, `.wav`, `.m4a`, `.webm`) en cualquier mensaje.
- Descarga temporal segura y transcripción simulada (en producción: Faster-Whisper local).
- POST a `/api/story/{work_id}/canon` con `scene_ref: "discord_voice:{session_id}"`.
- Publica evento a `POST /api/discord/canon-feed` para broadcast.

### Endpoint backend nuevo
- `POST /api/discord/canon-feed` — Recibe eventos de canon feed del bot; los registra en `data/discord_canon_feed.json` (últimos 200 eventos).
- `GET /api/story/{work_id}/canon` — Lista eventos canónicos existente.
- `GET /api/story/{work_id}/characters` — Lista personajes existente.
- `GET /api/story/sessions/{session_id}/context` — Estado de vinculación existente.

## Qué falta para conexión real con Discord
1. Crear aplicación en Discord Developer Portal:
   - https://discord.com/developers/applications
   - New Application → nombre (ej: AURA Bot).
   - Bot → Reset Token → copiar token.
   - OAuth2 → General → copiar Client ID.
   - (Opcional) Server Members Intent y Message Content Intent activados en Bot settings.

2. Configurar variables en `services/discord-bot/.env`:
   - DISCORD_BOT_TOKEN=<token del bot>
   - DISCORD_CLIENT_ID=<client id>
   - DISCORD_GUILD_ID=<id del servidor de prueba> (opcional, para commands instantáneos)
   - DISCORD_NOTIFY_CHANNEL=ops (nombre del canal de notificaciones)
   - AURA_BACKEND_URL=http://localhost:8000 (o la URL real del backend)
   - REDIS_URL=redis://localhost:6379/0 (o URL de Redis remota)

3. Sincronizar commands:
   - Si usas `guild_id`, los commands se registran solo en ese servidor (instantáneo).
   - Si no usas `guild_id`, se registran globalmente (puede tardar hasta 1 hora en aparecer).

4. Levantar el bot:
   - Windows: `services/discord-bot/start.bat`
   - Linux/Mac: `cd services/discord-bot && bundle exec ruby bot.rb`

## Tareas pendientes sugeridas para el siguiente agente
- Verificar que el backend AURA exponga los endpoints:
  - GET /api/status
  - GET /api/logs?service=...&lines=...
  - POST /api/restart
  - POST /api/deploy
  - API Story (literaria): GET /api/story/works, POST /api/story/{work_id}/characters/{char_id}, GET /api/story/{work_id}/characters, POST /api/story/sessions/{session_id}/context, GET /api/story/sessions/{session_id}/context, DELETE /api/story/sessions/{session_id}/context, POST /api/story/{work_id}/check-consistency
- Ajustar `call_backend` si el backend usa auth/JWT.
- Agregar manejo de errores más robusto en commands (ej: timeouts, fallback si backend no responde).
- Configurar Redis real si se despliega el bot en producción (Railway, Render, etc.).
- Agregar tests de integración ligeros con `webmock` o `vcr` para `call_backend` y los endpoints story.
- Revisar permisos del bot en Discord (Application Commands, Send Messages, Read Message History).
- El rate-limit móvil se gestiona ahora vía `GET /api/mobile/story` (proxy server-side) y `GET /api/story/mobile/story` (backend).

## Notas técnicas
- libsodium no está instalado; voice support no funcionará hasta instalar libsodium.
- `register_command` helper evita pasar `guild_id: nil` a discordrb 3.4 (causaba `ArgumentError`).
- `skip_registration` en `initialize` permite testear sin registrar commands reales.
- No hardcodear secrets en repo; usar `.env` local y variables de entorno en deploy.
