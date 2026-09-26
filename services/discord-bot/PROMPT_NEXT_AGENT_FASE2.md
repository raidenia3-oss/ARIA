# Prompt para Cline: Fase 2 - Integración y Entrenamiento Real

## Contexto
Fase 1 completada. Ahora necesitamos conectar todos los módulos y ejecutar el primer entrenamiento real del modelo pequeño.

## Entorno
- Working directory: `C:\Users\User\Downloads\AURA`
- Python 3.11, venv `venv-training/` con todas las dependencias
- Modelo base descargado: `models/qwen-0.5b/` (~1 GB)
- Windows, Git Bash disponible

## Tareas

### 1. Ejecutar primer entrenamiento real (dry run opcional)
- Usar `training/scripts/train_aura_light.py` con el dataset existente `training-data.jsonl` (660 muestras).
- Configuración: `--model-name Qwen/Qwen2.5-0.5B-Instruct --epochs 1 --batch-size 1 --max-seq-length 256 --lora-r 4`
- Si el entrenamiento completo tarda >30 min, cancelar y reportar. Solo necesitamos confirmar que el pipeline funciona.
- Guardar logs en `training/output/train_light.log`.

### 2. Crear orquestador `training/scripts/orchestrator.py`
Script que ejecuta el ciclo completo:
1. Generar datos sintéticos (opcional, si `training/data/synthetic_generated.jsonl` no existe)
2. Ejecutar `validate_dataset.py` sobre el dataset final
3. Ejecutar `benchmark_router.py` (20 queries)
4. Ejecutar `train_aura_light.py` (1 epoch)
5. Exportar logs y métricas a `training/output/orchestrator_report.json`

Debe aceptar flags: `--skip-synthetic`, `--skip-benchmark`, `--epochs N`.

### 3. Integrar SmartRouterAdapter en endpoint FastAPI
- En `ame_backend/main.py` o donde esté el endpoint `/chat` o `/v1/chat`, agregar un parámetro `?router=true`.
- Si `router=true`, usar `SmartRouterAdapter.chat()` en lugar de `AIEngine.chat()`.
- Si `router=false` o no se envía, mantener comportamiento actual.
- No romper endpoints existentes.

### 4. Crear script de inferencia local
- `training/scripts/infer_local.py` que cargue el modelo fine-tuneado desde `fine-tuned-ame/aura_finetuned_lora/` (si existe) o el base.
- Acepte `--prompt` por CLI o entrada interactiva.
- Use `qwen2.5:0.5b` de Ollama como fallback si no hay adaptadores locales.
- Mida latencia de inferencia.

### 5. Crear workflow automático (opcional pero deseado)
- En `.github/workflows/`, crea `train_continuous.yml` que:
  - Se active cada vez que se modifique `training/data/interactions.jsonl` o `training/scripts/`.
  - Ejecute `orchestrator.py --skip-synthetic` en un runner Ubuntu con GPU.
  - Guarde el adaptador LoRA resultante como artifact.
  - NO suba modelos al Hub automáticamente.

## Reglas
- NO modifiques `docs/`, `README.md`, `PROMPT_NEXT_AGENT.md` ni archivos de deploy existentes.
- Usa `logging` en lugar de `print()`.
- Cada tarea debe ser independiente.
- Si una tarea requiere más de 10 minutos, reporta y continúa con las demás.

## Entregables
1. Log de entrenamiento: `training/output/train_light.log`
2. `training/scripts/orchestrator.py`
3. Modificación en `ame_backend/main.py` (o archivo de rutas) con flag `?router=true`
4. `training/scripts/infer_local.py`
5. `.github/workflows/train_continuous.yml` (si es posible)

## Validación final
Al terminar, ejecuta:
```bash
python training/scripts/orchestrator.py --skip-benchmark --epochs 1
python training/scripts/infer_local.py --prompt "Hola AURA, ¿qué puedes hacer?"
```

Si `infer_local.py` tarda >60 segundos en responder, optimiza la carga del modelo (usa `device_map="cpu"` y `low_cpu_mem_usage=True`).
