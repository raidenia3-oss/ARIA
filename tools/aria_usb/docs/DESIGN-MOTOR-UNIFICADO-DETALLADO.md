# INVESTIGACIÓN COMPLETA: Motor unificado para ARIA + entrenamiento no-manual y gratis

## 1) Contexto y objetivo
Unificar texto/visión/audio/video en "motor+cerebro" único reutilizable por ARIA/AIRIS. Entrenar con método no-manual para reducir censura/refusals, mejorar visión/video/escucha, 100% gratis y CPU-friendly (Ryzen 5700G, 15.4GB RAM).

## 2) Unificación: router + ModelManager + capa multimodal
- Extender ackend/ai_router.py con ModelManager (load/unload, one-at-a-time por defecto, lazy load)
- Mantener PermissionEngine intacto (acciones riesgosas pasan por puente Termux+ARIA)
- Contexto compartido con ackend/memory/* (working/short/long)
- Un modelo multi-modal base (Qwen2.5-VL GGUF chico Q4) puede cubrir visión + texto; audio/STT vía Whisper.cpp separado pero orquestado
- Tool-calling centralizado: schema estricto, fail-closed, diff-first

## 3) Candidatos GGUF (CPU-viables)
| Modelo | Multimodal | Tamaño Q4 | RAM aprox | Notas |
|---|---|---|---|---|
| Qwen2.5-VL 3B/7B | Sí (visión+texto) | ~2–4GB | 3–6GB | Bueno en GGUF comunitario, tool-calling variable |
| LLaVA-OneVision 7B | Sí | ~4GB | 5–7GB | Más estable visión |
| Phi-4-mini-multimodal | Sí | ~2GB | 3–4GB | Ligero |
| Gemma 3 1B/4B | Sí | ~1–3GB | 2–4GB | Equilibrado CPU |

Recomendado iniciar con 3B–4B Q4 para equilibrio.

## 4) Des-censura + entrenamiento no-manual y gratis
Priorizar **SFT + LoRA** (reproducible). Pipeline automatizable:
1. Dataset builder (scripts): filtra/refuerza respuestas útiles, elimina/refusal patterns
2. Entrenar en Kaggle/Colab (T4 gratis) con Unsloth/LlamaFactory CLI headless
3. Merge LoRA → base
4. GGUF quant (llama-quantize)
5. Validar local (tool-calling + casos)

Datasets abiertos: OpenHermes-2.5, Capybara, Dolly, LIMA (curados). Evitar datasets tóxicos.

## 5) Visión/video/escucha
- Vision: Qwen2.5-VL (frames)
- Video: muestreo temporal (keyframes) → descripción
- OCR: RapidOCR
- STT: Whisper.cpp (small/base/tiny)
- Orquestador decide si usa visión/audio según tarea

## 6) Integración con ARIA (mínima)
- ai_router: añadir unified_model_id, mode=unified|separate
- ModelManager con warmup/lazy
- Bridge Termux usa mismo router
- No tocar PermissionEngine

## 7) Viabilidad Ryzen 5700G 15.4GB
- Un modelo multi-modal Q4 3–4B: ~3–5GB RAM
- Resto para memoria + tools + llama-server: OK con one-at-a-time
- CPU: suficiente para inferencia razonable
- Evitar cargar múltiples modelos simultáneos

## 8) Pasos concretos (diseño)
- [ ] Mapear ai_router.py + memory
- [ ] Elegir candidato inicial
- [ ] Diseñar script 	ools/aria-usb/scripts/train_auto.py (headless)
- [ ] Documentar límites Kaggle/Colab oct 2026
- [ ] Probar integración mínima

## 9) Dudas puntuales (máx 3)
1. ¿Preferir un modelo "todo-en-uno" (Qwen2.5-VL) vs mantener módulos separados?
2. ¿Permitir entrenar en Kaggle/Colab vía script automatizado (sin login manual)? Kaggle requiere login; Colab también. ¿Aceptable "semi-manual" solo login?
3. ¿Priorizar "uncensor" ligero (refusal removal) vs mejora funcional (visión)?

## Conclusión
Viable CPU-first. Unificar vía ModelManager + router. Entrenamiento LoRA automatizable en free tiers. Mantener fail-closed.
