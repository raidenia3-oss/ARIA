# Prompt para Cline: Fase 5 - Conectar Frontend Next.js y Discord Bot al Backend

## Contexto
Fases 1-4 completadas. El backend FastAPI está funcionando en `ame_backend/` con:
- `/api/chat` con router híbrido (`?router=true`)
- `/api/feedback` (up/down) y `/api/feedback/stats`
- `/health` con estado de proveedores, LoRA, interactions, feedback
- Modelo local: `models/qwen-0.5b/` + LoRA `fine-tuned-ame/aura_finetuned_lora/`

Ahora necesitamos conectar el frontend Next.js y el Discord bot existentes a este backend real.

## Entorno
- Working directory: `C:\Users\User\Downloads\AURA`
- Backend: `ame_backend/src/main.py` (FastAPI, puerto 8000 por defecto)
- Frontend: `frontend/` (Next.js, App Router)
- Discord bot: `packages/discord-bot/` (Ruby)
- Variables de entorno en `.env.ai` y `.env.example`

## Tareas

### 1. Conectar frontend al backend real
- En `frontend/app/api/ame-core/route.ts` (o la ruta principal de API):
  - Cambiar el endpoint de `https://raiden456-aura-chat.hf.space` (o el que esté hardcodeado) a `http://localhost:8000` en desarrollo
  - Soportar el flag `router=true` en el payload
  - Manejar feedback: enviar `?feedback=up` o `?feedback=down` después de cada respuesta
  - NO exponer `HF_TOKEN` ni otras API keys al cliente
- En `frontend/app/api/hf-chat/route.ts`:
  - Asegurar que solo se use server-side y nunca devuelva tokens al cliente
  - Si el backend local no está disponible, fallback a proveedor cloud configurado

### 2. Preparar el Discord bot para conectarse al backend
- En `packages/discord-bot/bot.rb` (o el archivo principal del bot):
  - Reemplazar la lógica de respuesta hardcodeada por llamadas a `http://localhost:8000/api/chat?router=true`
  - Manejar comandos slash básicos: `/status`, `/health`, `/feedback up`, `/feedback down`
  - Si el backend no responde, responder con mensaje de fallback informativo
- Crear `packages/discord-bot/.env.example` con:
  - `DISCORD_BOT_TOKEN`
  - `AURA_BACKEND_URL=http://localhost:8000`

### 3. Crear script de inicio conjunto
- `scripts/start_aura_full.bat` que:
  1. Verifique Ollama corriendo con `qwen2.5:0.5b`
  2. Inicie el backend FastAPI (`uvicorn ame_backend.src.main:app --reload`)
  3. Inicie el frontend Next.js (`npm run dev` en `frontend/`)
  4. Inicie el Discord bot (Ruby) si hay token configurado
  5. Guarde PIDs para `stop_aura_full.bat`

### 4. Mejorar manejo de errores en el frontend
- En la interfaz de chat del frontend:
  - Mostrar indicador de "Local" vs "Cloud" según el proveedor devuelto por el backend
  - Mostrar estado de conexión con el backend
  - Si el backend falla, mostrar mensaje claro y ofrecer reintento
  - Agregar botones de feedback (👍/👎) que llamen a `/api/feedback`

### 5. Documentación de conexión
- Crear `docs/deployment/local_development.md` con:
  - Requisitos previos (Python 3.11, Node.js, Ollama, Ruby para bot)
  - Pasos para levantar backend + frontend + bot
  - Variables de entorno necesarias
  - Troubleshooting común

## Reglas
- NO modifiques `docs/training/strategy.md` ni prompts de agente
- NO subas secretos ni API keys al repo
- Usa `fetch` con `next: { revalidate: 0 }` en API routes de Next.js para evitar cache
- Mantén compatibilidad con el comportamiento actual del frontend
- Si una tarea requiere cambios en el backend, coordina para no romper endpoints existentes

## Entregables
1. `frontend/app/api/ame-core/route.ts` actualizado
2. `frontend/app/api/hf-chat/route.ts` revisado/mejorado
3. `packages/discord-bot/bot.rb` actualizado
4. `packages/discord-bot/.env.example` creado
5. `scripts/start_aura_full.bat` y `scripts/stop_aura_full.bat`
6. `docs/deployment/local_development.md`

## Validación final
1. Iniciar backend: `uvicorn ame_backend.src.main:app --reload`
2. Verificar `/health` y `/api/chat?router=true`
3. Iniciar frontend: `npm run dev` en `frontend/`
4. Abrir `http://localhost:3000` y enviar un mensaje
5. Verificar que el mensaje llegue al backend y se guarde en `interactions.jsonl`
6. Enviar feedback y verificar que se guarde en `feedback.jsonl`
