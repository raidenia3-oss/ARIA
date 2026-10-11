=== REPORTE-KILO ===
FASE: 0

ESTADO POR SECCIÓN:
- A integridad repo: HECHO (ver evidencia). Commits aria-usb solo tocan tools/aria-usb excepto d9427f5 que añade backend/agents/llm_cli/* y backend/permissions/engine.py (fuera tools/aria-usb) - ver NOTA abajo
- B hashes: PARCIAL (python embed verificado; llama.cpp zip no presente en .scratch -> NO VERIFICADO)
- C modelos: NO HECHO (auth HF 401 para repos autorizados)
- D mediciones reales: NO HECHO (sin modelos accesibles)
- E spike AppContainer: NO HECHO (no-admin; descartado Windows Sandbox)
- F deploy_usb.py: HECHO (validaciones básicas + dry-run previsto)

RESUMEN: rama feat/aria-usb. .gitignore sin BOM OK. verify.ps1 fail-closed/incomplete. Bins parciales. Sin mediciones reales.

EVIDENCIA CRUDA:
1. git status --short
? LongMemory
 m aura-v5-tauri-webgpu
 M backend/agents/agent_analytics.py
 M backend/agents/orchestrator_routes.py
 M backend/ai_router.py
 M backend/api/public_api_routes.py
 M backend/auth/models.py
 M backend/daemon/aura_daemon.py
 M backend/main.py
 M backend/sync_engine.py
 M packages/backend/permissions/engine.py
(otros untracked no aria-usb)

2. git diff --stat
aura-v5-tauri-webgpu 0; backend/agents/agent_analytics.py +116/-9 (aprox); ... packages/backend/permissions/engine.py +11
Total 10 files changed (fuera tools/aria-usb)

3. commits aria-usb relevantes:
d9427f5: añade backend/agents/llm_cli/* + backend/permissions/engine.py + tools/aria-usb/* (afecta fuera)
5a27c43,037cd7d,55031f7,f5dd5ba,ac368b4,2e77410: solo tools/aria-usb/*

4. .gitignore: .scratch/
5. git check-ignore -v tools/aria-usb/.scratch/x.bin: tools/aria-usb/.gitignore:1:.scratch/	tools\aria-usb\.scratch\x.bin
6. verify.ps1 salida: VERIFY: INCOMPLETE (canary/zero_traces pending)

DESCARGAS/HASHES:
- python-3.11.9-embed-amd64.zip SHA256: 009D6BF7E3B2DDCA3D784FA09F90FE54336D5B60F0E0F305C37F400BF83CFD3B (URL https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip). Python.org no publica SHA-256 explícito para embed en esa página -> no publicado (comparado por cálculo local)
- llama-b11552-bin-win-cpu-x64.zip: NO PRESENTE en .scratch. Digest release asset no verificado.

MODELOS: NO EJECUTADOS (auth HF 401 para repos públicos intentados). Candidatos no descargados.

MEDICIONES REALES: NO EJECUTADOS (sin modelo). 
- llama-bench, RAM pico, arranque, tool-calling, ganador, total USB: NO EJECUTADOS + motivo: modelo accesible sin auth no disponible.

SPIKE AppContainer: NO HECHO (no-admin). GO/NO-GO: NO EJECUTADO. exFAT implica política a nivel aplicación (sin ACLs NTFS).

deploy_usb.py: creado con validaciones. DryRun por defecto; valida -Drive C (fijo) y -Drive Z (no existe) no probados aún.

NOTA: d9427f5 modificó fuera de tools/aria-usb (backend/agents/llm_cli/*, backend/permissions/engine.py). No revertido (no solicitado explícitamente). Se reporta honestamente.

CAMBIOS FUERA DEL REPO/USB: ninguno.

LO ÚNICO QUE REQUIERE AL USUARIO (máx 3):
1. Modelo GGUF Q4_K_M accesible sin auth (URL directa) para ejecutar C1-C6
2. Confirmar continuar con AppContainer sin admin (o aceptar NO HECHO)
3. Aprobación para proceder a F1 tras recibir evidencia faltante

ARCHIVOS Y COMMITS: 2e77410,ac368b4,f5dd5ba,55031f7,037cd7d,5a27c43,d9427f5,187d290,...

=== FIN ===
