# Prompt para Cline: Fase 6 - Testing, Hardening y Deployment

## Contexto
Fases 1-5 completadas. El stack completo está implementado pero no ha sido probado en un escenario real prolongado ni endurecido contra errores comunes. Necesitamos encontrar y corregir fallos, añadir validaciones y preparar deployment.

## Entorno
- Working directory: `C:\Users\User\Downloads\AURA`
- Python 3.11, venv `venv-training/`
- Backend FastAPI en `ame_backend/` (puerto 8000)
- Frontend Next.js en `frontend/` (puerto 3000)
- Discord bot en `services/discord-bot/` (Ruby)
- Modelo local: `models/qwen-0.5b/` + LoRA `fine-tuned-ame/aura_finetuned_lora/`

## Tareas

### 1. Prueba end-to-end del backend
- Iniciar backend en background: `uvicorn ame_backend.src.main:app --host 0.0.0.0 --port 8000`
- Probar con `curl` o Python requests:
  - `GET http://localhost:8000/health`
  - `POST http://localhost:8000/api/chat` con `{"prompt": "Hola", "router": true}`
  - `POST http://localhost:8000/api/chat/feedback` o el endpoint de feedback correspondiente
  - `GET http://localhost:8000/api/feedback/stats`
- Anotar errores, timeouts, respuestas inesperadas
- Corregir cualquier fallo encontrado

### 2. Validación de inputs y seguridad
- En `ame_backend/src/main.py` y endpoints de chat:
  - Validar que `prompt` no esté vacío y tenga longitud máxima (ej. 4000 chars)
  - Validar que `feedback` solo acepte `up`/`down`
  - Limitar rate de requests por IP (ej. 30 req/min) con middleware simple
  - Sanitizar prompts para evitar injection en logs
- En `training/scripts/`:
  - Validar que `interactions.jsonl` no crezca sin límite (rotar o truncar a 10k entradas)
  - Agregar checksums o validación de JSONL corrupto

### 3. Manejo de errores y fallbacks
- Mejorar fallbacks en `SmartRouterAdapter`:
  - Si Ollama no responde, marcar provider como "unavailable" y no reintentar local por N segundos
  - Si todas las APIs cloud fallan, devolver mensaje amigable en lugar de excepción
- En el frontend:
  - Agregar retry lógico con backoff exponencial para llamadas a `/api/chat`
  - Mostrar estados: "pensando...", "conectando...", "error"

### 4. Optimización de rendimiento
- En `infer_local.py` y `train_aura_light.py`:
  - Cachear modelo en memoria entre llamadas (singleton o variable global)
  - Liberar memoria GPU/CPU explícitamente con `torch.cuda.empty_cache()` o `gc.collect()`
  - Medir y reportar tokens/segundo en inferencia
- En backend:
  - Agregar timeout global a llamadas a proveedores externos (max 30s)
  - Implementar cache simple en memoria para consultas repetidas (TTL 5 min)

### 5. Docker compose para stack completo
- Crear `docker-compose.yml` en la raíz que levante:
  - Backend FastAPI (puerto 8000)
  - Frontend Next.js (puerto 3000) — opcional, puede ser solo el backend
  - Ollama (puerto 11434) con modelo `qwen2.5:0.5b` pre-pullado
  - Redis para cache (opcional pero recomendado)
- Crear `Dockerfile` para el backend
- Crear `Dockerfile` para el frontend (o usar Node oficial)
- Verificar que `docker compose up` levante todo sin errores

## Reglas
- NO modifiques `docs/training/strategy.md`, `README.md`, ni prompts de agente
- NO subas secretos a ningún lado
- Usa `logging` en lugar de `print()`
- Mantén compatibilidad total con endpoints existentes
- Si una tarea requiere más de 10 minutos, reporta y continúa con las demás

## Entregables
1. Informe de testing end-to-end con errores encontrados y corregidos
2. `ame_backend/src/main.py` con validaciones y rate limiting
3. Mejoras en `SmartRouterAdapter` con cache de providers caídos
4. `infer_local.py` optimizado con cache de modelo
5. `docker-compose.yml` + Dockerfiles para backend y opcionalmente frontend

## Validación final
1. Ejecutar backend y probar todos los endpoints con `curl`
2. Ejecutar `python training/scripts/infer_local.py --prompt "test"` dos veces seguidas (segunda debe ser más rápida por cache)
3. Ejecutar `docker compose config` para validar sintaxis
4. Reportar tiempos de inferencia antes y después de optimización
