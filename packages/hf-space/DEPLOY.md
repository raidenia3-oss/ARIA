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

cp /ruta/a/AURA/hf-space/app.py .
cp /ruta/a/AURA/hf-space/requirements.txt .
cp /ruta/a/AURA/hf-space/README.md .
cp -r /ruta/a/AURA/hf-space/src/ .

git add .
git commit -m "Initial commit: AURA Chat"
git push
```

## Paso 3: Variables de entorno

En **Settings** → **Repository Secrets**:
- `HF_TOKEN`: tu token de Hugging Face
- `HF_MODEL`: modelo a usar. Por defecto `openbmb/MiniCPM5-1B`

## Paso 4: Verificar despliegue

1. Espera el build automático
2. Accede a https://huggingface.co/spaces/raiden456/aura-chat
3. Revisa **Logs** para confirmar que carga sin errores

## Paso 5: Mantener activo 24/7

### Opción A: Hugging Face Pro ($9/mes)
Activa **"Keep Space Awake"** en Settings.

### Opción B: Ping automático
Configura un cron/ping a `https://raiden456-aura-chat.hf.space/health` cada 5 minutos.

### Opción C: Réplicas gratuitas
Ve a **Settings** → **Replicas** y agrega 1 réplica.

## Paso 6: Actualizar

```bash
cd aura-chat
git pull
# ... cambios ...
git add .
git commit -m "Update"
git push
```

## Solución de problemas

### Out of memory
Usá solo modelos 1B-3B en CPU. Cambiá a T4 GPU solo si el modelo lo requiere.

### Model not found
Verificá que `HF_TOKEN` tenga acceso al modelo. Probá con `openbmb/MiniCPM5-1B` que es público.

### Space sleeping
Activa "Keep Space Awake" o configurá un ping automático.
