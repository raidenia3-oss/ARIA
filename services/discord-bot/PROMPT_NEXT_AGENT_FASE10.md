# Prompt para Cline: Fase 10 - Optimización, Multi-modalidad y Cierre del Proyecto

## Contexto
Fases 1-9 completadas. El sistema tiene: entrenamiento continuo, router híbrido, backend FastAPI, frontend Next.js, Discord bot, Docker, CI/CD, deployment docs, observabilidad y alertas. Ahora necesitamos pulir rendimiento, añadir capacidades multi-modales reales y cerrar el proyecto con una experiencia de usuario completa.

## Entorno
- Working directory: `C:\Users\User\Downloads\AURA`
- Backend: `ame_backend/` (FastAPI, Python 3.11)
- Frontend: `frontend/` (Next.js, TypeScript)
- Modelo: `models/qwen-0.5b/` + LoRA `fine-tuned-ame/aura_finetuned_lora/`
- Ollama configurado con `qwen2.5:0.5b`

## Tareas

### 1. Optimización de inferencia local
- En `training/scripts/infer_local.py`:
  - Implementar carga perezosa (lazy loading) del modelo/tokenizer
  - Añadir soporte para streaming de tokens (`stream=True` en Ollama)
  - Implementar cache LRU en memoria para consultas repetidas (usar `functools.lru_cache` o diccionario con TTL)
  - Medir y reportar tokens/segundo
- En `ame_backend/src/services/ai_engine.py`:
  - Añadir timeout global configurable (max 30s) a llamadas a proveedores externos
  - Implementar cache simple en memoria para consultas repetidas (TTL 5 min, max 100 entradas)

### 2. Capacidades multi-modales reales
- En `ame_backend/src/main.py`, mejorar el endpoint `/api/chat` para soportar:
  - `image_url` en el payload: si se envía una URL o base64, usar Gemini para análisis de imagen
  - `audio_url` en el payload: si se envía audio, usar Whisper (local o API) para transcribir y luego procesar el texto
  - `file_url` en el payload: si se envía un PDF o documento, extraer texto y procesarlo
- Crear `ame_backend/src/tools/multimodal.py` con funciones:
  - `analyze_image(url_or_bytes, prompt)` → Gemini vision
  - `transcribe_audio(url_or_bytes)` → Whisper local o Groq
  - `extract_text_from_file(url_or_path)` → PyPDF2 o pdfplumber para PDFs
- Actualizar frontend para soportar upload de imágenes, audio y archivos en el chat

### 3. Mejoras de seguridad y sandboxing
- Revisar y endurecer `ame_backend/src/tools/gatekeeper.py` (si existe) o crear uno nuevo:
  - Whitelist de comandos permitidos en system control
  - Validación de paths: no permitir acceso a directorios sensibles (C:\Windows, /etc, /root)
  - Límite de tamaño de archivos a procesar (max 10MB)
- En `ame_backend/src/main.py`:
  - Añadir validación de tamaño máximo de payload (max 5MB)
  - Añadir CORS estricto en producción (no `*`)

### 4. Mejoras de experiencia de usuario (frontend)
- En `frontend/app/api/ame-core/route.ts`:
  - Implementar streaming de respuesta SSE (Server-Sent Events) para mostrar texto gradualmente
  - Mostrar indicador de proveedor (Local/Cloud) y modelo usado
  - Mostrar estado de conexión con el backend
  - Botones de feedback (👍/👎) que envían a `/api/feedback`
- En `frontend/app/page.tsx` o componente de chat:
  - Soporte para upload de imágenes y archivos
  - Historial de conversación persistente (localStorage o backend)
  - Botón para limpiar conversación

### 5. Scripts de utilidad y mantenimiento
- Crear `scripts/maintenance.py` que:
  - Limpie `interactions.jsonl` si supera 10k entradas (mantener últimas 10k)
  - Limpie `feedback.jsonl` si supera 5k entradas
  - Limpie `logs/metrics.jsonl` si supera 50k entradas
  - Verifique integridad de backups en `fine-tuned-ame/backups/`
  - Reporte espacio en disco usado por modelos y datos
- Crear `scripts/cleanup.bat` para Windows que ejecute mantenimiento

### 6. Cierre y documentación final
- Crear `docs/architecture/overview.md` con diagrama Mermaid de arquitectura completa
- Crear `docs/usage/user_guide.md` con guía de uso para el usuario final
- Crear `CHANGELOG.md` con resumen de fases 1-10
- Actualizar `README.md` con estado final del proyecto

## Reglas
- NO modifiques `docs/training/strategy.md`, `services/discord-bot/PROMPT_NEXT_AGENT*.md`
- NO subas secrets a ningún lado
- Usa `logging` en lugar de `print()`
- Mantén compatibilidad total con endpoints existentes
- Si una tarea requiere >10 min, reporta y continúa

## Entregables
1. `training/scripts/infer_local.py` optimizado con streaming y cache
2. `ame_backend/src/tools/multimodal.py`
3. Mejoras en `ame_backend/src/main.py` para multi-modalidad
4. `ame_backend/src/observability.py` mejorado con cache y timeout global
5. `ame_backend/src/main.py` endurecido (CORS, tamaño payload)
6. Mejoras en frontend (streaming, upload, historial)
7. `scripts/maintenance.py` y `scripts/cleanup.bat`
8. `docs/architecture/overview.md`
9. `docs/usage/user_guide.md`
10. `CHANGELOG.md`

## Validación final
```bash
python training/scripts/infer_local.py --prompt "test streaming" --stream
python scripts/maintenance.py --dry-run
curl -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" -d "{\"prompt\": \"Hola\", \"router\": true}"
```

Reportar estado de cada entregable y velocidad de inferencia mejorada.
