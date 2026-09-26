# AURA Unified Brain - Sistema de IA Distribuido

## Vision
Un solo cerebro unificado distribuido en 3 nodos:
- **PC**: modelo potente + modelo ligero/equilibrado
- **Servidor externo**: modelo chico
- **Celular**: APIs externas como apoyo/entrenamiento

## Arquitectura

```
Celular (APIs externas) 
    |
    v
Backend Cloud (orquestador)
    |
    +---> Modelo chico (servidor)
    |
    +---> Modelo potente (PC, cuando esta encendida)
    |
    +---> Sistema de entrenamiento continuo
```

## Flujo de datos

### Inferencia
1. Cliente envia prompt a `/api/brain/chat`
2. Backend detecta dispositivo/rol automaticamente
3. Router decide:
   - Si es celular: usar APIs externas (Gemini/Groq/OpenRouter)
   - Si es servidor: usar modelo chico Qwen 0.5B
   - Si es PC: usar modelo potente + fallback a ligero
4. Respuesta retornada al cliente

### Entrenamiento
1. Cada conversacion se registra automaticamente en `training_data/samples_YYYY-MM-DD.jsonl`
2. El sistema acumula muestras de todos los dispositivos
3. Cuando hay suficientes muestras (200+ en 7 dias), dispara fine-tuning
4. El modelo mejorado se sincroniza entre servidor y PC
5. Las APIs externas apoyan generando respuestas de referencia

## Endpoints unificados

### Inferencia
```
POST /api/chat - Chat principal con memoria
POST /api/chat/stream - Chat con streaming SSE
POST /api/ai - Modelo local directo
```

### Cerebro unificado
```
GET  /api/brain - Estado general del cerebro
GET  /api/brain/training-data - Dataset de entrenamiento
POST /api/brain/train - Disparar fine-tuning
```

### Servicios
```
GET  /health - Estado del sistema
GET  /api/status - Estado de servicios
POST /api/feedback - Feedback de respuestas
```

## Roles por dispositivo

| Dispositivo | Rol | Modelo | Uso |
|-------------|-----|--------|-----|
| PC | powerful/light | Qwen fine-tuned + modelos grandes | Inferencia potente local |
| Servidor | small | Qwen 0.5B | Servicio 24/7 |
| Celular | external_api | Gemini/Groq/OpenRouter | Apps moviles |

## Sistema de entrenamiento

### Recoleccion automatica
- Cada llamada a `/api/chat` registra: prompt, respuesta, dispositivo, proveedor, feedback
- Almacenado en `training_data/samples_YYYY-MM-DD.jsonl`
- Sin costo adicional, automatico

### Fine-tuning continuo
- Trigger: 200+ muestras nuevas en 7 dias
- Dataset: ultimas 5000 muestras de los ultimos 30 dias
- Modelo base: Qwen/Qwen2.5-0.5B
- Output: modelo fine-tuned sincronizado

### Mejora incremental
- El modelo chico (servidor) se actualiza automaticamente
- La PC sincroniza el modelo mejorado cuando esta encendida
- Las APIs externas proporcionan respuestas de referencia para comparar

## Configuracion

### Variables de entorno
```bash
AURA_BRAIN_STATE_FILE=./brain_state.json
AURA_TRAINING_DATA_DIR=./training_data
AURA_MODEL_REGISTRY_FILE=./model_registry.json
AURA_LOCAL_MODEL_PATH=./models/qwen-0.5b
```

### Archivos generados
- `brain_state.json` - Estado global del cerebro
- `model_registry.json` - Registro de modelos y versiones
- `training_data/samples_*.jsonl` - Muestras de entrenamiento

## Ventajas del sistema unificado

1. **Sin intervencion humana**: entrenamiento automatico
2. **Multi-dispositivo**: PC, servidor, celular funcionan como uno solo
3. **Mejora continua**: el modelo mejora con cada conversacion
4. **Fallback inteligente**: si un nodo falla, otro toma su lugar
5. **Costo cero**: usa recursos existentes, APIs externas como apoyo

## Proximos pasos

1. Ejecutar `setup.ps1` una sola vez
2. El sistema se auto-entrena con las conversaciones
3. Los modelos mejoran automaticamente
4. Dispositivos se sincronizan solos
