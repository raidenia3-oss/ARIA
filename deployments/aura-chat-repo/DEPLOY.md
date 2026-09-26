# 🚀 Guía de Despliegue — AURA Chat en Hugging Face Space

## Paso 1: Crear el Space

1. Ve a https://huggingface.co/new-space
2. Configura:
   - **Space Name**: `aura-chat` (quedará como `raiden456/aura-chat`)
   - **License**: MIT
   - **SDK**: Gradio
   - **Hardware**: CPU free tier
3. Haz clic en **Create Space**

## Paso 2: Subir archivos

```bash
git clone https://huggingface.co/spaces/raiden456/aura-chat
cd aura-chat

cp /ruta/a/AURA/aura-chat-repo/app.py .
cp /ruta/a/AURA/aura-chat-repo/requirements.txt .
cp /ruta/a/AURA/aura-chat-repo/README.md .
cp -r /ruta/a/AURA/aura-chat-repo/src/ .

git add .
git commit -m "Initial commit: AURA Chat"
git push
```

## Paso 3: Variables de entorno

En **Settings** → **Repository Secrets**:
- `BACKEND_URL`: URL pública del backend AURA (ej: `https://aura-backend.onrender.com`)
- `HF_TOKEN`: tu token de Hugging Face (para fallback local)
- `HF_MODEL`: modelo fallback. Por defecto `openbmb/MiniCPM5-1B`

## Paso 4: Desplegar el backend

El backend AURA debe estar accesible públicamente. Opciones:
- **Render**: `ame_backend` con `render.yaml`
- **Railway**: servicio Python con `uvicorn ame_backend.src.main:app --host 0.0.0.0 --port $PORT`
- **VPS/Docker**: exponer puerto 8000 o 5000

Verifica que `/health` responda:
```bash
curl https://tu-backend.onrender.com/health
```

## Paso 5: Verificar despliegue

1. Espera el build automático del Space
2. Accede a https://huggingface.co/spaces/raiden456/aura-chat
3. Revisa **Logs** para confirmar que carga sin errores
4. Prueba enviar un mensaje; si `BACKEND_URL` está configurado, el Space consultará al backend

## Paso 6: Mantener activo 24/7

### Opción A: Hugging Face Pro ($9/mes)
Activa **"Keep Space Awake"** en Settings.

### Opción B: Ping automático
Configura un cron/ping a `https://raiden456-aura-chat.hf.space/health` cada 5 minutos.

### Opción C: Réplicas gratuitas
Ve a **Settings** → **Replicas** y agrega 1 réplica.

## Solución de problemas

### Backend no responde
Verifica que `BACKEND_URL` sea accesible desde internet y que el puerto esté abierto.

### Space sin créditos HF
Sin `BACKEND_URL`, el Space cae al modelo local de HF. Configura `BACKEND_URL` para usar tu backend propio.

### Model not found
Verificá que `HF_TOKEN` tenga acceso al modelo. Probá con `openbmb/MiniCPM5-1B` que es público.

### Space sleeping
Activa "Keep Space Awake" o configurá un ping automático.

## Actualizar

```bash
cd aura-chat
git pull
# ... cambios ...
git add .
git commit -m "Update"
git push
```
