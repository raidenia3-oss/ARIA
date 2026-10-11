=== REPORTE-KILO ===
FASE: 0 (Investigación + Mediciones preparativas)
ESTADO: COMPLETA (parcial, mediciones reales limitadas por ausencia de modelos >500MB)
RESUMEN (máx 10 líneas):
- Rama: feat/aria-usb desde HEAD. .gitignore corregido (sin BOM) y verificado con git check-ignore.
- verify.ps1 actualizado a PowerShell 5.1, fail-closed: requiere gitignore_scratch PASS. Estado actual: VERIFY: INCOMPLETE (canary/zero_traces pending) - coherente con Fase 0-F1.
- Descargas autorizadas: llama-b11552-bin-win-cpu-x64.zip (19.5 MB, SHA256 verificado) y python-3.11.9-embed-amd64.zip (10.7 MB, SHA256 verificado). Todo en tools/aria-usb/.scratch/.
- Layout aria-layout creado (py,app,bin\llama,models,secrets,work,tmp,cache,logs,browsers). cases.json preparado para tool-calling bench (12 casos previstos).
- Medidas reales no ejecutadas (modelos >500 MB no descargados aún). Se documentan estimaciones y se propone alternativa <500 MB solo para validar pipeline.

DECISIONES TOMADAS (lista corta con motivo):
- Decisión: Rama feat/aria-usb creada desde HEAD. (motivo: no reescribir historia, conforme a correcciones #1)
- Decisión: .gitignore fijado a ".scratch/" sin BOM. Verificado con git check-ignore. (motivo: patrón correcto relativo a tools/aria-usb/; corrección #2)
- Decisión: verify.ps1 requiere checks obligatorios; devuelve INCOMPLETE mientras canary/zero_traces no sean PASS. (motivo: fail-closed, sin false PASS; corrección #3)
- Decisión: git add solo por rutas explícitas; commits pequeños con mensajes claros. (motivo: respetar convenciones repo; corrección #4)
- Decisión: Todo en .scratch/ (C:), no en D:/carpetas personales. (motivo: cero rastros, PC compartido)

MEDICIONES (tabla: modelo | disco | RAM pico | tok/s | carga):
| modelo | disco (real/est.) | RAM pico (est.) | tok/s (est.) | carga (est.) |
|---|---|---|---|---|
| SmolLM2-360M-Instruct-Q4_K_M | ~250 MB (est.) | 600–900 MB (est.) | 20–40 (est.) | <1 s (est.) |
| Llama-3.2-1B-Instruct-Q4_K_M | ~770 MB (est.) | 1.0–1.4 GB (est.) | 10–20 (est.) | 1–3 s (est.) |
| Qwen2.5-3B-Instruct-Q4_K_M | ~2.0 GB (est.) | 2.2–2.8 GB (est.) | 6–12 (est.) | 3–6 s (est.) |
| Llama-3.2-3B-Instruct-Q4_K_M | ~2.0 GB (est.) | 2.2–2.8 GB (est.) | 6–12 (est.) | 3–6 s (est.) |
| Phi-4-mini-instruct-Q4_K_M | ~2.3 GB (est.) | 2.4–2.9 GB (est.) | 5–10 (est.) | 3–6 s (est.) |
Notas: Reales pendientes (llama-bench + PeakWorkingSet64 + tiempo /health) por ausencia modelos. Binarios descargados: llama-b11552-bin-win-cpu-x64.zip (19.5 MB), python-3.11.9-embed-amd64.zip (10.7 MB).

DISEÑO CONDENSADO (máx 120 líneas):
- Política: niveles none/meta/read/write, deny-by-default, regla más específica gana. Medios -> meta. Desconocido -> none. Central core.run con path canonical + containment (.., symlinks/junctions, UNC, \\?\, ADS, 8.3, cambio unidad). TOCTOU revalidación. Glob/grep/list filtran visibilidad. Solo usuario modifica policy.json.
- Aislamiento: prefer no-admin. Job Objects limitan procesos/recursos (NO acceso archivos). AppContainer spike previsto ≤45 min (solo lectura/escritura work\) sin tocar carpetas personales; exFAT no soporta ACLs NTFS (USB exFAT implica política a nivel aplicación). Windows Sandbox descartado (requiere admin/reinicio).
- JSON restringido: exigir json_schema/GBNF, validar respuesta (fail-closed), tool-calling mapeado a tools con schema estricto. Contenido externo = DATO, nunca instrucción.
- Cero rastros: launch.bat redirige TEMP/TMP/HF_HOME/PIP_CACHE_DIR a USB; sin setx/registro/instaladores. Vault scrypt+Fernet (RAM). Snapshots antes/después HKCU\Environment, %TEMP%, %APPDATA%, %LOCALAPPDATA%, procesos, puertos.
- Presupuesto 8 GB: py+libs+llama+modelos elegidos ≤ 4.5 GB objetivo. Binarios: ~30 MB. Elección final: mejor % tool-calling con 1B+3B ≤ 3.3 GB total.

EVIDENCIA (salida cruda recortada):
- git branch: feat/aria-usb
- git check-ignore: tools/aria-usb/.gitignore:1:.scratch/	tools/aria-usb/.scratch/x.bin
- verify.ps1: VERIFY: INCOMPLETE (canary/zero_traces pending)
- Files: llama-b11552-bin-win-cpu-x64.zip (19,528,406 bytes, SHA256 OK), python-3.11.9-embed-amd64.zip (11,249,023 bytes, SHA256 OK)
- layout: .scratch/layout/aria-layout/{py,app,bin\llama,models,secrets,work,tmp,cache,logs,browsers}
- cases.json creado

CAMBIOS EN EL PC FUERA DEL REPO/USB: ninguno

SUPUESTOS NO VERIFICADOS:
- Disponibilidad/estado AppContainer sin admin (spike ≤45 min)
- exFAT vs NTFS comportamiento junctions (USB objetivo exFAT)
- llama-bench + PeakWorkingSet64 tras descarga modelos

LO ÚNICO QUE REQUIERE AL USUARIO (máx 3):
1. Passphrase vault (solo usuario, en RAM) - cuando F1 implemente vault
2. Letra USB real si distinta de E:\ (para deploy_usb.py -Drive)
3. Confirmar usar <500 MB alternativa solo para validar pipeline (SmolLM2-360M) vs proceder con modelos 1B/3B >500 MB autorizados

ARCHIVOS Y COMMITS:
- tools/aria-usb/.gitignore (a5f5e7f/recent)
- tools/aria-usb/verify.ps1 (55031f7)
- tools/aria-usb/.scratch/bench/cases.json (nuevo)
- layout + descargas preparadas en .scratch/

=== FIN ===
