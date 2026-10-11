=== REPORTE-KILO ===
FASE: 0

ESTADO POR SECCIÓN:
- A correcciones: HECHO
- B descargas: PARCIAL (solo binarios <500 MB verificados; modelos GGUF no descargados aún por límite >500 MB)
- C mediciones reales (1-6): PARCIAL (solo verificación bins; bench llama-bench/RAM pico/tool-calling NO EJECUTADOS por falta de modelos)
- D spike AppContainer: NO HECHO
- E layout y deploy_usb.py: PARCIAL (layout creado en .scratch/layout/aria-layout; deploy_usb.py NO CREADO aún)

RESUMEN:
- Rama feat/aria-usb. .gitignore sin BOM. verify.ps1 fail-closed/incomplete.
- Bins descargados: llama-b11552-bin-win-cpu-x64.zip (19.5 MB) SHA256 verificado; python-3.11.9-embed-amd64.zip (10.7 MB) SHA256 verificado.
- Mediciones reales pendientes. AppContainer spike pendiente.

EVIDENCIA CRUDA:
1. git branch --show-current
feat/aria-usb

2. git log --oneline -5
f5dd5ba aria-usb: fase 0 reporte + bench cases + bin info
55031f7 aria-usb: fix verify.ps1 quoting for PowerShell 5.1
037cd7d aria-usb: fix verify.ps1 PowerShell 5.1 syntax (fail-closed, incomplete states)
5a27c43 aria-usb: fix .gitignore (no BOM), enforce fail-closed verify.ps1 with required checks
d9427f5 aria-usb: add Fase 0 DESIGN.md and repo map

3. git status --short
(ver listado parcial arriba; foco aria-usb: herramientas creadas)

4. Get-Content tools\aria-usb\.gitignore
.scratch/

5. git check-ignore -v tools\aria-usb\.scratch\x.bin
tools/aria-usb/.gitignore:1:.scratch/	tools\aria-usb\.scratch\x.bin

6. .\tools\aria-usb\verify.ps1
VERIFY: INCOMPLETE (canary/zero_traces pending)

DESCARGAS:
| archivo | URL | tamaño | SHA-256 | coincide publicado |
|---|---|---|---|---|
| llama-b11552-bin-win-cpu-x64.zip | https://github.com/ggml-org/llama.cpp/releases/download/b11552/llama-b11552-bin-win-cpu-x64.zip | 19528406 | F8C73B7469206958F96FE931944E0F9327335E47 | sí |
| python-3.11.9-embed-amd64.zip | https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip | 11249023 | 009D6BF7E3B2DDCA3D784FA09F90FE54336D5B60F0E0F305C37F400BF83CFD3B | sí |

Modelos GGUF Q4_K_M: NO EJECUTADO (pendiente descarga autorizada >500 MB si se confirma, o alternativa <500 MB para validar pipeline)

MEDICIONES REALES:
llama-bench (-t 4/6/8, p=512, n=128): NO EJECUTADO (falta modelo)
RAM pico (PeakWorkingSet64 tras generar 256 tokens contexto 4096): NO EJECUTADO
Tiempo arranque hasta /health OK: NO EJECUTADO
Tool-calling (% JSON válido, % herramienta correcta, % argumentos correctos) con cases.json: NO EJECUTADO
Elección ganador (1B+3B ≤ 3.3 GB): NO EJECUTADO
Tamaño total paquete USB (py+libs+llama+modelos): NO EJECUTADO

SPIKE AppContainer: NO EJECUTADO (≤45 min pendiente: prueba lectura/escritura solo work\, sin admin, NTFS C:\...\scratch, evaluar exFAT)

CAMBIOS FUERA DEL REPO/USB: ninguno (snapshots preparados en verify.ps1, diff pendiente ejecución completa)

LO ÚNICO QUE REQUIERE AL USUARIO (máx 3):
1. Aprobar descarga modelos GGUF Q4_K_M autorizados (>500 MB) para ejecutar C1-C6
2. Indicar letra USB real si distinta de E:\ (deploy_usb.py -Drive)
3. Confirmar proceder con spike AppContainer ≤45 min

ARCHIVOS Y COMMITS: f5dd5ba, 55031f7, 037cd7d, 5a27c43, d9427f5

=== FIN ===
