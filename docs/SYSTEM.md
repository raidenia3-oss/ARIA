# AURA - Sistema Unificado Completo

## Estado actual: 100% funcional

### Backend
- `/health` - Estado del sistema
- `/api/discovery` - Descubrimiento público
- `/api/status` - Estado de servicios
- `/api/chat` - Chat con memoria y multimedia
- `/api/chat/stream` - Streaming SSE
- `/api/ai` - Modelo local Qwen 0.5B
- `/api/brain` - Estado del cerebro unificado
- `/api/brain/training-data` - Dataset de entrenamiento
- `/api/brain/train` - Entrenamiento automático
- `/api/orchestrator` - Estado de disponibilidad
- `/api/media/upload` - Subida de fotos/videos
- Soporte multimedia: imágenes, audio, video

### Orquestación
- Monitoreo automático cada 30s
- Failover: PC → Servidor → Celular
- Reconexión automática
- Sincronización de modelos

### Entrenamiento continuo
- Recolección automática de muestras
- Fine-tuning cada 7 días (200+ muestras)
- Mejora incremental continua
- Sincronización entre dispositivos

### Clientes
- Godot Desktop: auto-discovery, streaming, multimedia
- Godot Android: cliente cloud
- Discord: código listo (opcional)
- Telegram: código listo (opcional)

## Mejora continua implementada

### 1. Recolección de muestras
- Cada chat registra: prompt, respuesta, dispositivo, multimedia
- Almacenado en `training_data/samples_YYYY-MM-DD.jsonl`

### 2. Evaluación automática
- Sistema detecta cuando hay 200+ muestras en 7 días
- Evalúa calidad del modelo actual
- Genera dataset de entrenamiento

### 3. Fine-tuning automático
- Entrena modelo Qwen 0.5B con muestras nuevas
- Actualiza versión del modelo
- Sincroniza entre PC y servidor

### 4. Métricas
- `improvement_state.json` - Estado de mejoras
- `brain_state.json` - Estado del cerebro
- `orchestrator_state.json` - Estado del orquestador

## Archivos clave

```
backend/
├── main.py                      # API principal
├── brain_orchestrator.py        # Cerebro unificado
├── orchestrator.py              # Orquestador de disponibilidad
├── continuous_improvement.py    # Mejora continua
├── telegram_bot.py              # Telegram bot (opcional)
└── models.py                    # Modelos de BD

godot/
└── scripts/network/
    └── aura_client.gd           # Cliente Godot con multimedia

services/
└── discord-bot/
    └── bot.rb                   # Discord bot (opcional)

docs/
├── brain-unified.md             # Documentación cerebro
├── roadmap.md                   # Mejoras futuras
└── deployment.md                # Guía de deploy

setup/
├── setup.ps1                    # Setup autónomo
├── EJECUTAR_SETUP.bat           # Setup con doble clic
└── aura-watchdog.ps1            # Watchdog autónomo
```

## Cómo usarlo

### Setup inicial (una sola vez)
1. Doble clic en `EJECUTAR_SETUP.bat`
2. Ingresá credenciales
3. El sistema deployea solo

### Uso diario
- **PC encendida**: Godot Desktop se conecta local
- **PC apagada**: Godot Desktop se conecta cloud
- **Celular**: Godot Android consulta cloud
- **Entrenamiento**: automático cada 7 días

### Verificación
```bash
# Backend
curl https://<backend-url>/health

# Cerebro
curl https://<backend-url>/api/brain

# Orquestador
curl https://<backend-url>/api/orchestrator

# Mejora continua
curl https://<backend-url>/api/brain/training-data
```

## Próximas evoluciones

### Corto plazo
- [ ] Más modelos locales (Phi-3, Llama 3.2)
- [ ] Mejor streaming de video
- [ ] Cache de multimedia en Godot

### Mediano plazo
- [ ] Auth JWT unificado
- [ ] Multi-usuario
- [ ] Plugins extensibles

### Largo plazo
- [ ] Red P2P entre dispositivos
- [ ] Fine-tuning en edge
- [ ] Asistente de voz nativo
