# Prompt para Cline: Fase 4 - Puesta en Producción y Monitoreo

## Contexto
Fases 1-3 completadas. El pipeline de entrenamiento continuo funciona, el router está integrado en FastAPI, hay feedback y dashboard. Ahora necesitamos endurecer el sistema para uso real y añadir monitoreo.

## Entorno
- Working directory: `C:\Users\User\Downloads\AURA`
- Python 3.11, venv `venv-training/`
- Backend FastAPI en `ame_backend/`
- Modelo: `models/qwen-0.5b/` + LoRA `fine-tuned-ame/aura_finetuned_lora/`
- Windows 10/11, Git Bash

## Tareas

### 1. Verificar arranque del backend
- Revisar `ame_backend/src/main.py` y asegurar que todas las rutas funcionen
- Probar inicio con `uvicorn` o el comando definido en el proyecto
- Corroborar que `/api/chat?router=true` responda
- Corroborar que `/api/feedback/stats` responda
- Reportar cualquier error de import, ruta o variable de entorno faltante

### 2. Probar flujo end-to-end
- Simular 10 consultas variadas al endpoint `/api/chat` con `router=true`
- Enviar feedback up/down mezclado
- Ejecutar `training/scripts/quality_filter.py` y confirmar que exporte `high_quality_pairs.jsonl`
- Ejecutar `training/scripts/orchestrator.py --skip-synthetic --epochs 1 --max-samples 10`
- Confirmar que un nuevo adaptador LoRA se guarde en `fine-tuned-ame/aura_finetuned_lora/`

### 3. Health checks y monitoreo
- En `ame_backend/src/main.py`, crear o mejorar `/health` con:
  - Estado de cada proveedor de IA (Gemini, Groq, OpenRouter, local Ollama)
  - Estado del modelo local (si el adapter LoRA existe)
  - Cantidad de interacciones logged
  - Cantidad de feedback recibido
- Crear `training/scripts/monitor.py` que lea `training/data/` y `fine-tuned-ame/` y reporte:
  - Último entrenamiento (fecha, epochs, samples)
  - Cantidad de pares de alta calidad disponibles
  - Sugerencia: "entrenar ahora" / "esperar más datos"

### 4. Backup y versionado de modelos
- Crear `training/scripts/backup_model.py` que:
  - Copie `fine-tuned-ame/aura_finetuned_lora/` a `fine-tuned-ame/backups/aura_finetuned_lora_<timestamp>/`
  - Mantenga solo los últimos 5 backups (borre los más viejos)
  - Registre en `fine-tuned-ame/backups/manifest.json` el historial

### 5. Script de inicio todo-en-uno (producción)
- Crear `scripts/start_aura_production.sh` (o `.bat` para Windows) que:
  1. Verifique que Ollama esté corriendo y tenga `qwen2.5:0.5b`
  2. Inicie el backend FastAPI en background
  3. Ejecute `dashboard.py` una vez para mostrar estado inicial
  4. Guarde PIDs para poder detener todo con `stop_aura_production.sh/.bat`

## Reglas
- NO modifiques `docs/`, `README.md`, ni prompts de agente
- NO subas modelos a HuggingFace
- Usa `logging` en lugar de `print()`
- Mantén compatibilidad con endpoints existentes
- Si una tarea tarda >5 min, reporta y continúa

## Entregables
1. `ame_backend/src/main.py` con `/health` mejorado
2. `training/scripts/monitor.py`
3. `training/scripts/backup_model.py`
4. `scripts/start_aura_production.bat`
5. `scripts/stop_aura_production.bat`

## Validación final
Ejecutar:
```bash
python training/scripts/monitor.py
python training/scripts/backup_model.py
scripts/start_aura_production.bat
```

Verificar que el backend responda en `http://localhost:8000/health`.
