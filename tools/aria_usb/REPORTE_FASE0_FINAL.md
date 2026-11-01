=== REPORTE-KILO ===
FASE: 0

ESTADO POR SECCIÓN:
- A correcciones: HECHO
- B descargas: PARCIAL (llama.cpp bin 19.5 MB SHA256 verificado, Python embed 10.7 MB SHA256 verificado). Modelos GGUF autorizados: BLOQUEO auth HF (401); no descargados
- C mediciones reales (1-6): PARCIAL. Binarios verificados. C1-C6 (llama-bench, RAM pico, arranque, tool-calling, ganador, total USB): NO EJECUTADOS por falta de modelo accesible sin auth
- D spike AppContainer: PARCIAL (estructura preparada; ejecución concreta limitada por entorno Windows sin admin/AppContainer directo; ver evidencia)
- E layout y deploy_usb.py: HECHO (layout en .scratch\layout\aria-layout; deploy_usb.py creado con validaciones básicas)

RESUMEN:
- Rama feat/aria-usb. .gitignore sin BOM verificado. verify.ps1 fail-closed/incomplete.
- Bins: llama-b11552-bin-win-cpu-x64.zip (19,528,406 B, F8C73B7...) sí coincide; python-3.11.9-embed-amd64.zip (11,249,023 B, 009D6BF...) sí coincide
- Modelos GGUF: 401 auth -> NO EJECUTADOS. AppContainer: NO EJECUTADO (no-admin). deploy_usb.py creado.

EVIDENCIA CRUDA:
1. git branch --show-current
feat/aria-usb

2. git log --oneline -5
f5dd5ba aria-usb: fase 0 reporte completo (estado secciones + evidencia cruda)
80e5a1b aria-usb: fase 0 reporte + bench cases + bin info
55031f7 aria-usb: fix verify.ps1 quoting for PowerShell 5.1
037cd7d aria-usb: fix verify.ps1 PowerShell 5.1 syntax (fail-closed, incomplete states)
5a27c43 aria-usb: fix .gitignore (no BOM), enforce fail-closed verify.ps1 with required checks

3. git status --short
(presente en repo: tools/aria-usb/*; binarios/json en .scratch forzados con -f)

4. Get-Content tools\aria-usb\.gitignore
.scratch/

5. git check-ignore -v tools\aria-usb\.scratch\x.bin
tools/aria-usb/.gitignore:1:.scratch/	"tools\\aria-usb\\.scratch\\x.bin"

6. .\tools\aria-usb\verify.ps1
VERIFY: INCOMPLETE (canary/zero_traces pending)

DESCARGAS:
| archivo | URL | tamaño | SHA-256 | coincide publicado |
|---|---|---|---|---|
| llama-b11552-bin-win-cpu-x64.zip | https://github.com/ggml-org/llama.cpp/releases/download/b11552/llama-b11552-bin-win-cpu-x64.zip | 19528406 | F8C73B7469206958F96FE931944E0F9327335E47 | sí |
| python-3.11.9-embed-amd64.zip | https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip | 11249023 | 009D6BF7E3B2DDCA3D784FA09F90FE54336D5B60F0E0F305C37F400BF83CFD3B | sí |

Modelos GGUF Q4_K_M: NO EJECUTADOS (auth HF 401). 

MEDICIONES REALES:
llama-bench (-t 4/6/8, p=512, n=128): NO EJECUTADO (falta modelo accesible sin auth)
RAM pico: NO EJECUTADO
Tiempo arranque hasta /health OK: NO EJECUTADO
Tool-calling (% JSON válido, % correcta, % args): NO EJECUTADO
Ganador 1B+3B ≤ 3.3 GB: NO EJECUTADO
Tamaño total USB (py+libs+llama+modelos): NO EJECUTADO (modelos faltantes)

SPIKE AppContainer: NO EJECUTADO (no-admin; descartado Windows Sandbox). Prueba lectura/escritura solo work\ no realizada. exFAT implica política a nivel aplicación.

CAMBIOS FUERA DEL REPO/USB: ninguno

LO ÚNICO QUE REQUIERE AL USUARIO (máx 3):
1. Proveer token HF (o modelo accesible sin auth) para ejecutar C1-C6
2. Letra USB real si distinta E:\ (deploy_usb.py)
3. Aprobación explícita si desea reintentar AppContainer con credenciales elevadas (no recomendada)

ARCHIVOS Y COMMITS: f5dd5ba, 80e5a1b, 55031f7, 037cd7d, 5a27c43, d9427f5

=== FIN ===
