# Prompt para Cline: Fase 3 - Evaluación, Feedback Loop y Producción

## Contexto
Fase 2 completada. El pipeline de entrenamiento continuo funciona. Ahora necesitamos medir calidad, capturar feedback real y endurecer el sistema para uso productivo.

## Entorno
- Working directory: `C:\Users\User\Downloads\AURA`
- Python 3.11, venv `venv-training/`
- Modelo base: `models/qwen-0.5b/`
- LoRA fine-tuneado: `fine-tuned-ame/aura_finetuned_lora/`
- Backend FastAPI en `ame_backend/`

## Tareas

### 1. Crear evaluador de modelo (`training/scripts/evaluate_model.py`)
- Cargar modelo base vs modelo fine-tuneado (con LoRA)
- Ejecutar 30 preguntas de test predefinidas (diversas complejidades)
- Comparar respuestas: longitud, tiempo de inferencia, y score de "calidad" usando un modelo externo (Gemini/Groq) como juez
- Guardar resultados en `training/output/evaluation_report.json`
- Métricas: avg latency, avg tokens, quality score (0-100), win rate del fine-tuned vs base

### 2. Sistema de feedback en el backend
- En `ame_backend/src/main.py`, modificar el endpoint `/api/chat` para aceptar `?feedback=up` o `?feedback=down`
- Guardar feedback en `training/data/feedback.jsonl` con: timestamp, prompt, response, provider, model, feedback value
- Solo guardar si `router=true` está activo (para aislar el impacto del router)
- Agregar endpoint `/api/feedback/stats` que devuelva estadísticas agregadas

### 3. Filtro de calidad para entrenamiento (`training/scripts/quality_filter.py`)
- Leer `training/data/interactions.jsonl` y `training/data/feedback.jsonl`
- Asignar score de calidad a cada interacción:
  - Si tiene feedback=up: score += 2
  - Si tiene feedback=down: score -= 3
  - Si provider=cloud y latency < 2s: score += 1
  - Si complexity=high: score += 1
- Filtrar solo pares con score >= 2 para entrenamiento
- Exportar `training/data/high_quality_pairs.jsonl`

### 4. Mejorar `infer_local.py` para usar el modelo fine-tuneado
- Modificar para cargar automáticamente LoRA si existe
- Agregar modo `--compare` que compare respuesta base vs fine-tuneada para el mismo prompt
- Mostrar diferencia de latencia y longitud

### 5. Dashboard de métricas (script, no web)
- `training/scripts/dashboard.py` que lea:
  - `training/data/benchmark_results.json`
  - `training/output/evaluation_report.json`
  - `training/data/feedback.jsonl`
  - `training/data/interactions.jsonl`
- Imprimir resumen en consola:
  - Precisión del router
  - Distribución de complejidad
  - Latencia promedio por proveedor
  - Win rate del modelo fine-tuneado
  - Cantidad de feedback positivo/negativo
  - Próximo entrenamiento recomendado (cuántas muestras nuevas hay)

## Reglas
- NO modifiques `docs/`, `README.md`, `PROMPT_NEXT_AGENT*.md`
- Usa `logging` en lugar de `print()`
- Si una tarea requiere más de 5 minutos de ejecución, reporta y continúa
- Para usar Gemini como juez en evaluate_model.py, usa `ame_backend/src/services/ai_engine.py` (no hagas llamadas directas)

## Entregables
1. `training/scripts/evaluate_model.py`
2. Modificación en `ame_backend/src/main.py` con feedback
3. `training/scripts/quality_filter.py`
4. `training/scripts/infer_local.py` mejorado
5. `training/scripts/dashboard.py`

## Validación final
Ejecutar:
```bash
python training/scripts/evaluate_model.py
python training/scripts/quality_filter.py
python training/scripts/dashboard.py
```

Reportar métricas clave de cada uno.
