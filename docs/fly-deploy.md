# Fly.io Deploy - Instrucciones

## Requisitos previos
- Fly CLI instalado: `C:\Users\User\.fly\bin\flyctl.exe`
- Cuenta en https://fly.io
- Modelo Qwen 0.5B en `C:\Users\User\Downloads\AURA\models\qwen-0.5b`

## Paso 1: Login
Abrí una terminal normal (no PowerShell) y ejecutá:
```bash
C:\Users\User\.fly\bin\flyctl.exe auth login
```

## Paso 2: Crear app y volumen
```bash
cd C:\Users\User\Downloads\AURA\backend
C:\Users\User\.fly\bin\flyctl.exe apps create aura-backend
C:\Users\User\.fly\bin\flyctl.exe volumes create aura_models --size 2 --region iad
```

## Paso 3: Configurar secrets
```bash
C:\Users\User\.fly\bin\flyctl.exe secrets set AURA_API_KEY=tu-api-key-segura-aqui
C:\Users\User\.fly\bin\flyctl.exe secrets set GEMINI_API_KEY=tu-gemini-key
C:\Users\User\.fly\bin\flyctl.exe secrets set GROQ_API_KEY=tu-groq-key
```

## Paso 4: Deploy
```bash
C:\Users\User\.fly\bin\flyctl.exe deploy
```

## Paso 5: Verificar
```bash
C:\Users\User\.fly\bin\flyctl.exe status
C:\Users\User\.fly\bin\flyctl.exe logs
```

## Paso 6: Obtener URL
```bash
C:\Users\User\.fly\bin\flyctl.exe info
```
Anotá la URL del backend (ej: `https://aura-backend.fly.dev`)

## Paso 7: Deploy Discord bot (opcional)
```bash
cd C:\Users\User\Downloads\AURA\services\discord-bot
C:\Users\User\.fly\bin\flyctl.exe apps create aura-discord-bot
C:\Users\User\.fly\bin\flyctl.exe secrets set DISCORD_BOT_TOKEN=tu-token
C:\Users\User\.fly\bin\flyctl.exe secrets set DISCORD_CLIENT_ID=tu-client-id
C:\Users\User\.fly\bin\flyctl.exe secrets set DISCORD_GUILD_ID=tu-guild-id
C:\Users\User\.fly\bin\flyctl.exe secrets set AURA_BACKEND_URL=https://aura-backend.fly.dev
C:\Users\User\.fly\bin\flyctl.exe deploy
```

## Troubleshooting
- Si falla el deploy, revisar logs: `flyctl logs`
- Si el modelo no carga, verificar que el volumen tenga el modelo
- Si falta Java/SDK para Android, configurar en Godot Editor
