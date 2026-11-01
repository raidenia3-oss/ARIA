# DISEÑO COMPLETO: Híbrido (todo-en-uno + módulos) + Termux/AIRIS

## 1. Visión general
Híbrido: núcleo "todo-en-uno" (modelo multi-modal unificado) con módulos especializados desacoplados (Whisper, OCR, vision, video). 
Termux (Android) + bot local (llama.cpp) actúa como worker asíncrono cuando PC apagado. Comunicación móvil (AIRIS) para aprobaciones/dudas (human-in-the-loop).

## 2. Arquitectura híbrida (motor + cerebro)
- Núcleo unificado: Qwen2.5-VL GGUF (texto+visión base) como cerebro central
- Módulos separados: STT (Whisper.cpp), OCR (RapidOCR), Video (frame sampler+caption), TTS opcional
- ModelManager: carga núcleo uno-a-uno; módulos en RAM bajo demanda (lazy)
- Router (extiende backend/ai_router.py): decide ruta híbrida (núcleo vs módulo)
- Memoria compartida (backend/memory): working/short/long
- PermissionEngine: nunca se salta (fail-closed)

## 3. Asíncrono Termux + AIRIS (móvil)
- Termux (Android): llama-server local + FastAPI bot (tool-calling estricto, diff-first)
- Repo mirror ~/aura-work (worktree) independiente
- Comunicación: Telegram/HTTP hacia AIRIS (móvil). Cola de aprobaciones pendientes (task_id)
- Cuando PC apagado: avanza tareas batch, pide aprobaciones en móvil (AIRIS). Cuando PC encendido: sincroniza
- MCP (read-only+safe) + REST Bridge hacia AURA (acciones riesgo)

## 4. Entrenamiento no-manual + des-censura
- SFT+LoRA (prioritario). Pipeline automatizado headless: dataset prep → train (Kaggle/Colab T4, script) → merge → GGUF quant
- Dataset sintético local (reduce dependencia externa). Uncensor ligero (refusal removal) + mejora funcional
- Ejecución automática programable (cron/termux-job) sin intervención usuario

## 5. Integración AURA
Extiende ai_router.py (unified+modules), ModelManager, no toca PermissionEngine. Bridge reutiliza endpoints.

## 6. Viabilidad
Ryzen 5700G: núcleo 3B–4B Q4 + módulos bajo demanda OK (15.4GB). Termux ARM: modelos chicos.

## Conclusión
Híbrido combina estabilidad (módulos) + simplicidad (núcleo). Asíncrono móvil cumple requisito "avance sin mí, comunique con AIRIS".
