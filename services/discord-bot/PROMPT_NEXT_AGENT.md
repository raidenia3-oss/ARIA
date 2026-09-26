# Prompt para Cline: Tareas de Implementación AURA

## Contexto
Eres un agente de implementación trabajando en el proyecto AURA. Tu objetivo es completar tareas concretas de integración, testing y deployment. NO avances en arquitectura ni diseño; ejecuta solo lo listado abajo.

## Entorno
- Working directory: `C:\Users\User\Downloads\AURA`
- Python 3.11, venv activo en `venv-training/` (PyTorch CPU, transformers, peft, datasets, trl)
- Windows 10/11, Git Bash disponible
- Repo sin cambios sin commit

## Tareas

### 1. Verificar dependencias de entrenamiento
- Revisa que `venv-training` tenga instalados: `torch`, `transformers`, `peft`, `datasets`, `trl`, `accelerate`
- Ejecuta `python -m py_compile` en:
  - `training/scripts/synthetic_data_generator.py`
  - `training/scripts/smart_ai_router.py`
  - `training/scripts/continual_trainer.py`
  - `training/scripts/train_aura_light.py`
- Si hay errores de import o sintaxis, corrígelos.
- Reporta en consola: "OK" o lista de errores corregidos.

### 2. Descargar modelo base 0.5B
- Si no existe `models/qwen-0.5b/`, descarga `Qwen/Qwen2.5-0.5B-Instruct` usando `huggingface-cli download` (requiere HF_TOKEN) o Python.
- Verifica tamaño aproximado (~1.2 GB).
- Guarda en `models/qwen-0.5b/`.

### 3. Crear script de validación de datos
- Crea `training/scripts/validate_dataset.py` que:
  - Acepte `--path` a un JSONL
  - Verifique que cada línea tenga `text` y `output`
  - Reporte: total samples, duplicados, samples vacíos, longitud promedio
  - Salida: JSON a `training/data/validation_report.json`

### 4. Crear script de benchmark del router
- Crea `training/scripts/benchmark_router.py` que:
  - Cargue `SmartAIRouter` en modo `hybrid`
  - Pruebe 20 consultas predefinidas (5 low, 10 medium, 5 high)
  - Mida latencia por consulta y por proveedor
  - Guarde resultados en `training/data/benchmark_results.json`

### 5. Integrar router con backend existente
- En `ame_backend/src/services/ai_engine.py`, crea un wrapper `SmartRouterAdapter` que:
  - Importe `SmartAIRouter`
  - Exponga método `chat(prompt, context)` que use el router y devuelva formato compatible con `AIEngine.chat()`
  - Si el router falla, haga fallback a `AIEngine.chat()` directo
  - No rompas la interfaz existente de `AIEngine`

## Reglas
- NO modifiques `docs/`, `README.md`, ni archivos de configuración global sin necesidad.
- NO uses `print()` para logging; usa `logging` o el formato existente en cada módulo.
- NO subas nada a HuggingFace Hub.
- NO crees archivos `.md` a menos que el test lo requiera.
- Si una tarea requiere dependencias nuevas, añádelas a `venv-training` con `pip install` y reporta.
- Cada tarea debe ser independiente; si una falla, continua con las demás.

## Entregables
1. `training/scripts/validate_dataset.py`
2. `training/scripts/benchmark_router.py`
3. Modificación en `ame_backend/src/services/ai_engine.py` con el adapter
4. Log de ejecución en consola con resumen final: "TASK_X: OK/FAIL"

## Ejecución
Al terminar, ejecuta:
```bash
python training/scripts/validate_dataset.py --path training/data/continual_dataset.jsonl
python training/scripts/benchmark_router.py --queries 20
```

Si `continual_dataset.jsonl` no existe, usa `training-data.jsonl` como fallback.
