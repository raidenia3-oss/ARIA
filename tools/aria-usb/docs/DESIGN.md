# ARIA-USB: Fase 0 – Diseño (ESPAÑOL)

## Objetivo
Termux propio para PC, 100% local, gratis, portátil en USB (E:\ARIA), zero-trazas fuera de USB. Complementa ARIA/AIRIS, nunca reemplaza. TUI hacker #0f172a/#38bdf8, tool-calling estricto, diff-first, aprobación humana, deny-by-default.

## 1) llama-server (CPU) – flags, salida estructurada, function calling
Hipótesis (medir en PC): usar llama-server (CPU-only) con --threads, --threads-batch, --context, --parallel, --mlock, --no-mmap según RAM/CPU. Para salida estructurada: preferir JSON schema vía response_format o grammar (GBNF) para forzar JSON válido. Function calling: mapear tools -> tool schema JSON; validar respuesta contra schema antes de ejecutar (fail-closed).

Preguntas abiertas:
- ¿Soporta llama-server function tools con modelos GGUF aquí? Verificar versión disponible.
- ¿GBNF + json_schema funcionan juntos?

Acciones medir: tok/s (pp/tg), tiempo primer token, carga RAM por modelo, con --threads = ~CPU físico/lógico (Ryzen 7 5700G).

## 2) Candidatos GGUF (uno rápido ~1B, otro 3–4B Q4)
Presupuesto objetivo: app+bin+models ~4.5GB USB. Candidatos típicos (gratis, CPU-viables): L3.2-1B/3B? SmolLM2-3.2B? Qwen2.5-3B-Instruct? L3.1-8B demasiado; priorizar chicos Q4.
Medir:
- RAM idle+cargado: target < 6–8GB usado por agente+server
- tok/s: mínimo aceptable para TUI interactiva
- tamaño disco GGUF Q4

## 3) Python portable (sin rastros)
Comparar: embeddable Python 3.11 (zip, sin instalador), WinPython (más grande), uv/standalone? Objetivo: copiar a E:\ARIA\py sin tocar registro/AppData. Verificar sys.path, pip --no-cache-dir, variables TEMP/TMP a USB.

## 4) Aislamiento SO (viable sin admin)
Explorar: cuenta estándar aparte, nivel integridad bajo (icacls/manifest), Job Objects (limitar CPU/mem), AppContainer (limitado sin admin), Windows Sandbox (comprobar disponibilidad edición). Máximo viable SIN admin preferido. Evaluar riesgo vs esfuerzo.

## 5) Rutas Windows + seguridad (TOCTOU, traversal, reparse, ADS)
Deny-by-default. Política central en core.run: validar ruta canónica (Resolve-Path relativo a root permitido? o Path.resolve + containment). Detectar "..", symlink/junction, \\?\ , UNC, unidad distinta, ADS (:stream), nombres reservados. TOCTOU: revalidar antes de abrir handle y tras obtenerlo cuando aplique. Glob/grep/list DEBEN filtrar por visibilidad.

## 6) Clasificador sensibilidad
Reglas iniciales:
- Ubicaciones sospechosas = none: C:\Users\<otro>\*, C:\Users\<yo>\AppData\*, C:\Users\<yo>\OneDrive\*, C:\ProgramData, C:\Windows, navegadores
- Medios (jpg,png,mp4,heic,raw,aac,m4a,avi) -> meta por defecto salvo regla explícita con media:true
- Secretos/ext: .key,.pem,.pfx,.env,.kdbx,.json con tokens -> none/meta
- Desconocido -> none

## 7) Prompt injection
Tratar todo contenido externo (archivo, OCR, web, respuesta) como DATO. Nunca mezclar con system prompt. Usar delimitadores, separate context windows? Marcar origen [FILE:...|OCR|WEB]. Prohibir tool execution desde datos no confiables.

## 8) Vault cifrado USB
scrypt (cost razonable) + Fernet (cryptography). Clave solo en RAM. Guardar blob cifrado en E:\ARIA\secrets\. Nunca log. Recuperación: passphrase única. VeraCrypt portátil: ¿requiere admin? Evaluar.

## 9) Visión por capas (ventanas permitidas)
Capas: UIA primero (pywinauto/pyuiautomation?) -> si insuficiente OCR local (RapidOCR) -> VLM chico opcional CPU-only. Captura: hwnd específico (GetWindowRect + BitBlt/Windows Graphics Capture?) NUNCA escritorio completo. Whitelist de ventanas por título/clase/proceso.

## 10) HF/Kaggle/Colab límites (oct 2026) + LoRA->GGUF
Ver límites vigentes gratuitos (rate/uploads). Pipeline posterior: dataset local filtrado -> LoRA (unsloth? pero GPU en Colab/Kaggle; entrenar ALLÍ, NO local) -> merge+quant GGUF. NO entrenar en PC compartido.

## Presupuesto USB 8GB
Estimado: llama.cpp bin ~20–60MB, py embeddable ~40–80MB, app ~10–30MB, modelos GGUF Q4 (1B+3–4B) ~2–3GB, work/tmp/cache/logs/secrets/browsers resto. Target total app+models ~4.5GB. Medir real.

## Supuestos a verificar
- llama-server disponible/build viable CPU
- Python embeddable funciona sin registro
- Zero-trazas: launch.bat define %TEMP%/%TMP% a USB
- Sin admin viable para aislamiento deseado
- Policy containment robusto Windows

## Máximo 5 preguntas abiertas
1. ¿Hay llama-server prebuilt x64 Windows o compilar? (tamaño)
2. ¿Windows Sandbox disponible en esta edición? (msinfo32/winver)
3. ¿Permite exFAT ejecutar binarios? (sí, pero Junctions limitados vs NTFS; USB exFAT)
4. ¿Cuenta aparte viable sin admin? (Usuarios)
5. ¿VeraCrypt portable requiere elevación?

## Entregables
docs/aria-usb/DESIGN.md + ADRs: policy-first, zero-trazas, deny-by-default, diff-first, git-add-por-path, fail-closed.

## Estado
Listo para Fase 0 ejecución: medir tok/s, RAM, disco, sandbox, aislamiento. NO escribir código producto aún. Esperar OK.
