# Desarrollo Local AURA

Guía para levantar el stack completo de AURA en tu máquina.

## Requisitos previos

- Python 3.11+ con venv `venv-training/`
- Node.js 18+ (para frontend Next.js)
- Ruby 3.3+ (para Discord bot)
- Ollama instalado y corriendo
- Git Bash o terminal compatible

## Variables de entorno

Copia `.env.example` a `.env.local` en `ame_backend/` y define:

```env
GEMINI_API_KEY=
GROQ_API_KEY=
OPENROUTER_API_KEY=
HF_TOKEN=
```

En `packages/discord-bot/.env` (o `.env.local`):

```env
DISCORD_BOT_TOKEN=
DISCORD_CLIENT_ID=
DISCORD_GUILD_ID=
AURA_BACKEND_URL=http://localhost:8000
```

En `frontend/.env.local`:

```env
NEXT_PUBLIC_AURA_BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_HF_SPACE_URL=
HF_TOKEN=
```

## Inicio rápido

### Opción 1: Script todo-en-uno (recomendado)

```bash
scripts/start_aura_full.bat
```

Este script:
1. Verifica Ollama y descarga `qwen2.5:0.5b` si falta
2. Inicia el backend FastAPI en puerto 8000
3. Inicia el frontend Next.js en puerto 3000
4. Muestra el dashboard inicial
5. Guarda información de procesos en `%TEMP%\aura_fullstack.info`

### Opción 2: Inicio manual

**Terminal 1 - Backend:**
```bash
cd ame_backend
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm install
npm run dev
```

**Terminal 3 - Discord bot (opcional):**
```bash
cd services/discord-bot
bundle install
ruby bot.rb
```

## Verificación

- Backend health: http://localhost:8000/health
- Frontend: http://localhost:3000
- API chat: http://localhost:8000/api/chat
- Feedback stats: http://localhost:8000/api/feedback/stats

Envía un mensaje desde el frontend o Discord con `/chat Hola` y verifica que se guarde en `training/data/interactions.jsonl`.

## Troubleshooting

### Backend no responde
- Verifica que no haya otro proceso en puerto 8000: `netstat -ano | findstr :8000`
- Revisa logs en `training/output/train_light.log`
- Asegúrate de que el venv tenga instaladas las dependencias: `pip install transformers torch peft`

### Frontend no se conecta
- Verifica `NEXT_PUBLIC_AURA_BACKEND_URL=http://localhost:8000`
- Abre http://localhost:3000/api/ame-core directamente para ver el error

### Ollama no disponible
- Inicia Ollama manualmente: `ollama serve`
- Verifica modelo: `ollama list | grep qwen2.5:0.5b`

### Discord bot no se conecta
- Verifica `DISCORD_BOT_TOKEN` y `DISCORD_CLIENT_ID`
- Asegúrate de que el bot esté autorizado en tu servidor de Discord