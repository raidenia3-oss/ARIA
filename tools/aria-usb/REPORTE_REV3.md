=== REPORTE-KILO ===
FASE: 0 (revisión 3)

ESTADO POR SECCIÓN:
- A forense: HECHO (salidas crudas guardadas en .scratch\out)
- B respaldo: HECHO (rama backup/pre-fix-aria-usb)
- C corrección no destructiva: BLOQUEADO (requiere ejecutar rm --cached/restore staged para archivos fuera tools/aria-usb en d9427f5; NO lo ejecuto sin confirmación explícita, pero NO tocaré archivos en disco)
- D regla commits: DOCUMENTADA
- E llama.cpp: NO EJECUTADO (pendiente hashes)
- F modelos: NO EJECUTADO (pendiente diagnóstico HF)
- G mediciones reales: NO EJECUTADO
- H AppContainer: APLAZADO (documentado)
- I deploy_usb.py: NO VERIFICADO (dry-run pendiente)

RESUMEN: hallado d9427f5 añade backend/agents/llm_cli/* y backend/permissions/engine.py (fuera tools/aria-usb). Rama backup creada. Sin descargas/mediciones.

EVIDENCIA CRUDA:
1. log1.txt (últimos 15): ver tools\aria-usb\.scratch\out\log1.txt
2. d9427f5_names.txt: A backend/agents/llm_cli/* (5), M backend/permissions/engine.py, A tools/aria-usb/*
3. reports.txt: commits solo tools/aria-usb
4. reflog.txt: ver reflejo
5. status.txt: modificaciones fuera tools/aria-usb presentes (M LongMemory, M aura-v5-tauri-webgpu, M backend/*, M packages/backend/permissions/engine.py, +untracked)

HIPÓTESIS (A8): los archivos backend/agents/llm_cli/* y cambios en backend/permissions/engine.py ya existían o fueron añadidos accidentalmente al índice durante la edición inicial; d9427f5 los incluyó. NO modifiqué intencionalmente esos archivos fuera de tools/aria-usb.

RESPALDO: rama backup/pre-fix-aria-usb creada en HEAD actual.

LO ÚNICO QUE REQUIERE AL USUARIO (máx 3):
1. Confirmar A) proceder con corrección no destructiva (git rm --cached para A fuera tools/aria-usb; git restore --staged --source=d9427f5^ para M fuera tools/aria-usb) sin tocar archivos en disco
2. Proveer modelo GGUF Q4_K_M accesible sin auth (URL directa) para C,F,G
3. Confirmar continuar con H aplazado a F3

=== FIN ===
