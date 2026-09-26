# AURA Deployment Guide - Cloud + Local + Android + Discord

## Arquitectura Final

```
Cloud (siempre activo):
  - Backend FastAPI + Qwen 0.5B
  - PostgreSQL + Redis
  - Discord Bot

Local (cuando PC encendida):
  - Backend FastAPI opcional
  - Qwen 0.5B local opcional
  - Godot Desktop

Movil:
  - Godot Android (cliente cloud)
```

## Paso 1: Hostear modelo en cloud

### Opcion A: Fly.io (recomendado)
1. Instalar Fly CLI: `curl -L https://fly.io/install.sh | sh`
2. Login: `fly auth login`
3. Crear app: `fly apps create aura-backend`
4. Crear volumes:
   ```
   fly volumes create aura_models --size 2 --region iad
   fly volumes create aura_postgres --size 1 --region iad
   ```
5. Configurar secrets:
   ```bash
   fly secrets set AURA_API_KEY=tu-api-key-segura
   fly secrets set GEMINI_API_KEY=tu-gemini-key
   fly secrets set GROQ_API_KEY=tu-groq-key
   fly secrets set REDIS_URL=redis://localhost:6379/0
   fly secrets set DATABASE_URL=postgres://postgres:postgres@localhost:5432/aura
   ```
6. Deploy:
   ```bash
   fly deploy -C backend
   ```
7. Verificar: `fly logs -C backend`

### Opcion B: Railway
1. Conectar repo de GitHub
2. Nuevo servicio desde `backend/Dockerfile`
3. Variables de entorno igual que Fly.io
4. Deploy automatico en cada push

## Paso 2: Discord Bot en cloud

1. Crear bot en https://discord.com/developers/applications
2. Copiar token, client ID y guild ID
3. Configurar secrets en Fly/Railway:
   ```bash
   fly secrets set DISCORD_BOT_TOKEN=tu-token
   fly secrets set DISCORD_CLIENT_ID=tu-client-id
   fly secrets set DISCORD_GUILD_ID=tu-guild-id
   fly secrets set AURA_BACKEND_URL=https://aura-backend.fly.dev
   ```
4. Deploy bot:
   ```bash
   fly deploy -C services/discord-bot
   ```

## Paso 3: Godot Desktop (local/cloud automatico)

El cliente Godot ya incluye:
- Discovery automatico de backend local o cloud
- Reconexion automatica si falla
- Cache local de conversaciones

Configuracion:
```gdscript
# En AuraClient, modificar segun necesites:
var _cloud_url = "https://tu-backend.fly.dev"  # URL de tu backend cloud
```

Exportar para Windows/Mac/Linux desde Godot 4.6.

## Paso 4: Godot Android

1. En Godot: Project > Export > Android
2. Configurar keystore para firma
3. Exportar APK/AAB
4. El cliente se conecta automaticamente al backend cloud
5. No necesita modelo local (consulta por HTTP)

Permisos necesarios:
- Internet
- Almacenamiento (cache)

## Paso 5: APIs externas para entrenamiento

Configurar en backend:
```bash
GEMINI_API_KEY=AIzaSy...      # Razonamiento complejo
GROQ_API_KEY=gsk_...          # Alta velocidad
OPENROUTER_API_KEY=sk-or-...  # Modelos variados
HF_TOKEN=hf_...               # Modelos custom
```

El backend implementa un router que prueba:
1. Modelo local Qwen 0.5B
2. Groq (si hay key)
3. Gemini (si hay key)
4. OpenRouter (si hay key)
5. HF Space (si hay URL)
6. Fallback local hardcodeado

## Paso 6: Entrenamiento continuo

Recolectar conversaciones:
```bash
# Exportar conversaciones desde backend
curl -H "X-API-Key: tu-key" https://aura-backend.fly.dev/api/conversations
```

Generar dataset:
```python
# Convertir conversaciones a formato de entrenamiento
python training/convert_conversations_to_dataset.py
```

Fine-tuning:
```bash
# En cloud o local con GPU
python training/run_training_job.py --model Qwen/Qwen2.5-0.5B --dataset fine-tuning-data.jsonl
```

Actualizar modelo en produccion:
```bash
fly volumes snap aura_models -C backend
# Subir nuevo modelo al volume
fly deploy -C backend
```

## Verificacion

### Backend cloud
```bash
fly status -C backend
fly logs -C backend
```

### Discord bot
```bash
fly status -C services/discord-bot
fly logs -C services/discord-bot
```

### Godot Desktop
1. Abrir app
2. Verificar conexion en logs
3. Probar chat

### Godot Android
1. Instalar APK
2. Abrir app
3. Verificar conexion
4. Probar chat

## Costos

| Servicio | Costo/mes |
|----------|-----------|
| Fly.io Backend (1 CPU, 256MB) | $0-3 |
| Fly.io Volume 2GB | $0.15 |
| Discord Bot | $0 |
| PostgreSQL (Neon/Supabase) | $0 |
| Redis (Upstash) | $0 |
| **Total** | **$0-5/mes** |

## Troubleshooting

### Backend no responde
```bash
fly logs -C backend
# Verificar que el modelo este cargado
```

### Discord bot offline
```bash
fly logs -C services/discord-bot
# Verificar token y backend URL
```

### Godot no conecta
- Verificar que el backend cloud este accesible
- Verificar CORS en backend
- Verificar API key en cliente

### Modelo lento en cloud
- Fly.io free tier tiene limitacion de CPU
- Considerar upgrade a plan basico ($3/mes)
- O usar Groq para respuestas rapidas

## Proximos pasos

1. Crear cuenta en Fly.io
2. Deploy backend con modelo Qwen 0.5B
3. Crear bot Discord
4. Deploy bot en cloud
5. Exportar Godot Android
6. Probar flujo completo sin PC encendida
7. Configurar APIs externas
8. Implementar entrenamiento continuo
