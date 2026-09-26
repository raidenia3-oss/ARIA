# AURA - Estado Actual y Próximos Pasos

## Estado actual

### Backend ✅
- `/health` - Estado del sistema
- `/api/discovery` - Descubrimiento público
- `/api/status` - Estado de servicios
- `/api/chat` - Chat con memoria y router de IAs
- `/api/chat/stream` - Streaming SSE
- `/api/ai` - Modelo Qwen 0.5B local
- `/api/conversations` - Memoria conversacional
- `/api/feedback` - Feedback
- Router: Qwen 0.5B → Groq → Gemini → OpenRouter → Ollama → local

### Godot Desktop ✅
- Discovery automático local/cloud
- Streaming SSE para chat
- Cache local
- Reconexión automática

### Godot Android 🟡
- Código preparado para cloud
- Export presets configurados
- **Pendiente**: Build APK (requiere configurar Android SDK en Godot Editor)

### Discord Bot ✅
- Código listo
- Docker-compose cloud-ready
- **Pendiente**: Credenciales reales (lo harás vos)

### Cloud Deployment 🟡
- Fly CLI instalado
- Configuración lista (fly.toml, Dockerfile.fly)
- **Pendiente**: Login y deploy manual en Fly.io

## Próximos pasos

### Fly.io (15 minutos)
1. Ejecutá en tu terminal:
   ```bash
   C:\Users\User\.fly\bin\flyctl.exe auth login
   cd C:\Users\User\Downloads\AURA\backend
   C:\Users\User\.fly\bin\flyctl.exe apps create aura-backend
   C:\Users\User\.fly\bin\flyctl.exe volumes create aura_models --size 2 --region iad
   C:\Users\User\.fly\bin\flyctl.exe secrets set AURA_API_KEY=tu-api-key
   C:\Users\User\.fly\bin\flyctl.exe deploy
   ```

### Android Build (10 minutos)
1. Abrí Godot Editor: `dist\Build_Android.bat`
2. Configurá Android SDK en Settings ^> Export ^> Android
3. Exportá APK a `dist/AURA_Android.apk`
4. Instalá con: `adb install -r dist/AURA_Android.apk`

### Discord Bot (5 minutos)
1. Crear bot en https://discord.com/developers/applications
2. Configurar `.env` en `services/discord-bot/`
3. Deploy en Fly.io cuando tengas credenciales

## Archivos clave
- Backend: `backend/main.py`
- Fly config: `backend/fly.toml`
- Discord bot: `services/discord-bot/bot.rb`
- Godot client: `godot/scripts/network/aura_client.gd`
- Android build: `dist/Build_Android.bat`
- Docs: `docs/deployment.md`, `docs/fly-deploy.md`, `docs/architecture.md`

## Costo estimado
- Fly.io backend: $0-3/mes
- Discord bot: $0
- Total: $0-5/mes
