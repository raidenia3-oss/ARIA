# AURA Free GPU Training Guide

## Opción Recomendada: Google Colab (GRATIS)

### ¿Por qué Colab?
- **GPU T4 gratuita** (16GB VRAM) - suficiente para fine-tuning de Qwen2.5-1.5B
- **No requiere hardware local** - todo se ejecuta en la nube
- **2x más rápido** con Unsloth + 70% menos VRAM
- **Sin costo** - completamente gratuito

### ¿Por qué no otras opciones?
| Plataforma | VRAM | Costo | Limitaciones |
|------------|------|-------|--------------|
| **Google Colab** | 16GB (T4) | GRATIS | Sesiones de 12h, requiere Google account |
| Kaggle | 15.6GB (T4) | GRATIS | 30h/semana, configuración más compleja |
| HuggingFace ZeroGPU | 48GB | GRATIS | Solo para Spaces, no para entrenamiento |
| RunPod/Modal | Variable | $0.34-1.19/hr | Requiere tarjeta de crédito |

---

## Instrucciones Paso a Paso

### Paso 1: Preparar Datos (YA HECHO)
```bash
# Los datos ya están mezclados en:
aura_merged_training.jsonl (12,498 samples, 4.7MB)
```

### Paso 2: Abrir Colab
1. Ve a: https://colab.research.google.com/
2. Inicia sesión con tu cuenta de Google
3. Sube el archivo `AURA_Colab_Training.ipynb`

### Paso 3: Configurar GPU
1. Ve a `Runtime` > `Change runtime type`
2. Selecciona `T4 GPU` en Hardware accelerator
3. Click `Save`

### Paso 4: Configurar Hugging Face (Opcional pero recomendado)
1. Crea una cuenta en https://huggingface.co/
2. Ve a Settings > Access Tokens > New token (role: Write)
3. En Colab, click en el ícono 🔒 ( Secrets) a la izquierda
4. Agrega un nuevo secreto:
   - Name: `HF_TOKEN`
   - Value: tu token de Hugging Face

### Paso 5: Ejecutar Entrenamiento
1. Click en `Connect` (arriba a la derecha)
2. Ve a `Runtime` > `Run all`
3. El entrenamiento tomará aproximadamente 30-60 minutos

### Paso 6: Descargar Modelo
El modelo fine-tuned se descargará automáticamente al final.

---

## Archivos Creados

| Archivo | Descripción |
|---------|-------------|
| `AURA_Colab_Training.ipynb` | Notebook completo de Colab listo para ejecutar |
| `aura_merged_training.jsonl` | Dataset combinado (12,498 samples) |
| `scripts/merge_training_data.py` | Script para regenerar el dataset combinado |
| `scripts/colab_trainer.py` | Script auxiliar para preparar datos |

---

## Configuración del Modelo

### Para empezar (recomendado):
- **Modelo**: Qwen/Qwen2.5-1.5B-Instruct
- **Batch size**: 2
- **Epochs**: 3
- **Learning rate**: 2e-4
- **LoRA rank**: 16

### Si tienes problemas de memoria:
- Reducir `MAX_SEQ_LENGTH` a 1024
- Reducir `BATCH_SIZE` a 1
- Reducir `LORA_R` a 8
- Usar `Qwen/Qwen2.5-0.5B-Instruct` (modelo más pequeño)

---

## Solución de Problemas

### CUDA Out of Memory
- Reducir `BATCH_SIZE` a 1
- Reducir `MAX_SEQ_LENGTH` a 1024
- Reducir `LORA_R` a 8

### Sesión se desconecta
- Guardar checkpoints cada 20 pasos (ya configurado)
- Colab free tier tiene límite de tiempo

### Modelo no aprende
- Aumentar `NUM_EPOCHS` a 5-10
- Verificar que los datos estén en formato correcto
- Aumentar `LEARNING_RATE` a 3e-4

---

## Uso del Modelo Fine-Tuned

### Con Ollama (local):
```bash
# Convertir GGUF a formato Ollama
ollama create aura-finetuned -f Modelfile
```

### Con llama.cpp:
```bash
./llama-cli -m aura_finetuned.gguf -ngl 99
```

### Con Python:
```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

base_model = "Qwen/Qwen2.5-1.5B-Instruct"
model = AutoModelForCausalLM.from_pretrained(base_model, load_in_4bit=True)
model = PeftModel.from_pretrained(model, "aura_finetuned_lora")
```

---

## Notas Importantes

1. **Datos**: El dataset combinado tiene 12,498 samples de 20 archivos diferentes
2. **Tiempo**: Entrenamiento ~30-60 min en T4 gratis
3. **Costo**: $0 (completamente gratuito)
4. **Requisitos**: Solo una cuenta de Google

---

## Siguiente Paso

Después de entrenar, puedes:
1. Probar el modelo con los prompts de prueba incluidos
2. Descargar el modelo y usarlo localmente
3. Subirlo a Hugging Face Hub para compartir
4. Integrarlo en tu aplicación AURA local
