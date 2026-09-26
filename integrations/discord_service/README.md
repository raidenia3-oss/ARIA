# Discord Bot Service

Este servicio ejecuta `discord_bot.py` como un servicio independiente en Railway.

## Configuración

- `DISCORD_TOKEN`: Token del bot de Discord.
- `AURA_CHAT_URL`: URL del endpoint de chat de AURA. Por defecto usa `https://aura-server-01.vercel.app/chat`.

## Deploy en Railway

1. Crea un nuevo servicio en Railway.
2. Usa la carpeta `discord_service` como la raíz del servicio.
3. Railway detectará `railway.json` y ejecutará `python ../discord_bot.py`.
4. Asegúrate de definir `DISCORD_TOKEN` en las variables de entorno del servicio.
