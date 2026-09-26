# PLAN DE ACCIÓN: IA_CONFIG + COMFYUI + OSIRIS

## PASO 1: IA_CONFIG

- Detectar instalación de Ollama (`ollama --version`).
- Listar modelos locales (`ollama list`).
- Configurar `IA_CONFIG.md` con:
    - Endpoint local de Ollama (`http://localhost:11434`)
    - Modelos seleccionados: `qwen2.5-coder`, `deepseek-coder`.
    - Respaldo OpenRouter: `deepseek-chat`.

## PASO 2: COMFYUI

- Verificar ComfyUI en puerto 8188 (`curl http://localhost:8188`).
- Estructura:
    - `/entrada` (imágenes fuente).
    - `/salida` (imágenes procesadas).
    - `upscale_workflow.json` (workflow de upscaling).
- Dependencias Python en `comfy_requirements.txt`.

## PASO 3: OSIRIS

- Clonar repo oficial Osiris.
- Configurar puerto `3005`.
- Validar levantamiento de servidor.
- Extensión: script Node.js para subdominios + GeoIP sweep → `osint_results.json`.

## Nota

Debido al límite de tokens, la implementación completa requiere un breve reseteo de contexto antes de proceder.
