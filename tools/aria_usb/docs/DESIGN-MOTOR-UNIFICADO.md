# INVESTIGACIÓN: Unificar modelos IA para ARIA (motor+cerebro) + método de des-censura/entrenamiento no-manual y gratis

## Objetivo
Investigar cómo unificar múltiples modelos (texto, visión, audio/voz, video) en un solo "motor+cerebro" reutilizable para ARIA/AIRIS, y cómo entrenar (fine-tune/LoRA/RLHF ligero o pipeline abierto) para remover restricciones, mejorar visión/video/escucha y mantenerlo 100% gratis (local o pipeline entrenable en Kaggle/Colab, sin APIs pagas).

## Alcance: gratis, no manual, reproducible
- No manual: scripts/automatización
- Gratis: open weights, GGUF, kaggle/colab free tiers (documentar límites oct 2026)
- Local-first compatible (llama.cpp/vllm? CPU-first si GPU limitada)
- No salir de .scratch y repo (como ya establecido)

## 1) Unificación "motor+cerebro" (multi-modelo → sistema unificado)
Explorar arquitecturas:
- Router + dispatcher (ai_router.py existe) pero unificado
- Multi-modal single model (LLaVA, Qwen2.5-VL, LLaMA-3.2-vision, Phi-4-multimodal, Gemma3, Mistral Small?) vs ensemble ligero
- Tool-calling centralizado (PermissionEngine)
- Shared context + long-term memory (existe backend/memory)
- ModelManager central (load/unload, one-at-a-time o dynamic)

Hipótesis: usar un modelo base unificado (multi-modal chico) + router fino. Evaluar overhead RAM.

## 2) Des-censura + entrenamiento gratis (método)
Opciones:
- LoRA en dataset abierto (Dolly/OpenHermes/Capybara, no tóxicos pero útil) vía Unsloth (Kaggle T4 gratis) o LlamaFactory (open)
- Instruction-tuning + system prompt alignment
- Synthetic data (generado local) para reducir costos
- DPO/RLHF ligero? complejo; priorizar SFT+LoRA
- Remove refusal patterns vía dataset curated

Requisito "sin nada manual": script automatiza dataset prep → train → merge → quant GGUF.

## 3) Visión/lectura/video/escucha
- Vision: Qwen2.5-VL GGUF, LLaVA-OneVision (CPU)
- Video: frame sampling + captioning (local)
- OCR: RapidOCR ya mencionado
- Audio/STT: Whisper.cpp GGUF (tiny/base)
- TTS opcional
- UIA + vision combo

## 4) Investigación a hacer
- ¿Modelos base multi-modales estables en GGUF (CPU)?
- ¿LlamaFactory/Unsloth en free tiers sin intervención manual?
- ¿Métodos reproducibles para "uncensor" vía LoRA (papers/open)
- ¿Cómo integrar todo al router de ARIA sin romper PermissionEngine?
- ¿Presupuesto RAM/CPU para Ryzen 5700G 15.4GB?

## Entregable
	ools/aria-usb/docs/DESIGN-MOTOR-UNIFICADO.md conciso con:
- Arquitectura propuesta
- Modelos candidatos (GGUF, gratuitos)
- Pipeline entrenamiento automático (Kaggle/Colab)
- Integración con ARIA (puntos mínimos)
- Viabilidad CPU
- Pasos concretos (sin código pesado, diseño)
- 3 dudas puntuales

Empezar lectura: ai_router.py, backend/memory/*, DESIGN.md existente
