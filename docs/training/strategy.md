# Estrategia de Entrenamiento Ligero + Cerebro Híbrido

## Problema
Entrenar modelos pequeños (0.5B-1.5B) en CPU consume horas y recursos sin garantizar mejoras significativas si los datos son genéricos.

## Solución: Hybrid Brain Architecture

### 1. Smart AI Router (`smart_ai_router.py`)
Clasifica cada consulta por complejidad:
- **low**: tareas simples (hora, fecha, listar, ayuda) -> modelo local 0.5B
- **medium**: tareas moderadas -> modelo local por defecto, fallback a cloud si falla
- **high**: tareas complejas (análisis, razonamiento, código complejo, contexto amplio) -> API externa (Gemini/Groq/OpenRouter)

Beneficio: 80% del tráfico se resuelve local en milisegundos, sin costo API ni carga CPU.

### 2. Synthetic Data Generator (`synthetic_data_generator.py`)
Genera datasets de alta calidad usando APIs externas para dominios específicos de AURA (setup, system control, voice, vision, etc.).

Beneficio: el modelo pequeño aprende de "maestros" sin necesidad de datasets masivos ni horas de entrenamiento.

### 3. Continual Trainer (`continual_trainer.py`)
- Lee logs de interacciones del router.
- Filtra pares de alta calidad (respuestas cloud, complejidad media/alta, latencia baja).
- Genera un dataset incremental.
- Ejecuta QLoRA ligero en CPU (0.5B, r=4, max_seq=256, batch=1, 1 epoch).

Beneficio: entrenamientos de 5-15 minutos en CPU, actualizaciones frecuentes, mejora continua.

### 4. Lightweight Trainer (`train_aura_light.py`)
Script optimizado para CPU:
- Sin 4-bit (innecesario en CPU, añade overhead).
- LoRA r=4, max_seq=256.
- batch_size=1, gradient_accumulation=4.
- 1-2 epochs por sesión.

## Flujo completo

```text
User query
   |
   v
SmartAIRouter (clasifica complejidad)
   |
   +-- low --> Local 0.5B (Ollama) --> responde + loguea
   |
   +-- high --> Gemini/Groq/OpenRouter --> responde + loguea
   |
   v
(Background) ContinualTrainer
   |
   +-- Lee logs + synthetic data
   +-- Filtra calidad
   +-- QLoRA ligero 1 epoch
   +-- Nuevo adaptador LoRA
   |
   v
Local 0.5B mejora gradualmente
```

## Configuración recomendada

| Variable | Valor | Descripción |
|----------|-------|-------------|
| `SMART_ROUTER_MODE` | `hybrid` | auto | local_only | cloud_only |
| `SMART_ROUTER_LOCAL_MODEL` | `qwen2.5:0.5b` | Modelo local Ollama |
| `SMART_ROUTER_CLOUD_MODEL` | `gemini-2.0-flash-exp` | Modelo cloud preferido |
| `SYNTH_PROVIDER` | `auto` | Proveedor para generar datos sintéticos |

## Uso

```bash
# 1. Generar datos sintéticos (una vez o periódicamente)
python training/scripts/synthetic_data_generator.py

# 2. Usar el router en modo híbrido
python training/scripts/smart_ai_router.py --mode hybrid

# 3. Entrenar continuamente con datos acumulados
python training/scripts/continual_trainer.py

# 4. Entrenamiento ligero directo
python training/scripts/train_aura_light.py --model-name Qwen/Qwen2.5-0.5B-Instruct --epochs 1
```

## Ventajas vs entrenamiento tradicional

| Enfoque tradicional | Hybrid Brain |
|---------------------|--------------|
| Fine-tuning completo 3 epochs en 1.5B | QLoRA 1 epoch en 0.5B (5-15 min CPU) |
| Dataset estático de 2.8k muestras | Dataset dinámico: synthetic + interacciones reales |
| Sin mejora continua | Mejora cada vez que el usuario interactúa |
| Costo API 100% del tiempo | Costo API solo en tareas complejas |
| Overhead CPU alto constante | Overhead CPU solo en entrenamientos cortos |

## Notas
- El modelo local debe descargarse previamente: `ollama pull qwen2.5:0.5b`
- Las APIs externas requieren configurar `GEMINI_API_KEY`, `GROQ_API_KEY` o `OPENROUTER_API_KEY`.
- Los logs de interacciones se guardan en `training/data/interactions.jsonl` para auditoría y entrenamiento.
