=== REPORTE-KILO ===
FASE: 0 (REV4)

ESTADO POR SECCIÓN:
- PASO 1: HECHO (evidencia guardada)
- PASO 2: HECHO (corrección no destructiva aplicada; HEAD d8f604e)
- PASO 3: HECHO (llama.cpp descargado, SHA256 coincide)

RESUMEN:
- Corrección: archivos fuera tools/aria-usb en d9427f5 sacados del index sin tocar disco. Backup creado.
- llama.cpp b11552: zip descargado a .scratch/dl; publicado sha256 coincide con calculado; extraído a layout; llama-server --version OK; llama-bench disponible.
- Sin modelos accesibles sin auth; mediciones reales C1-C6 y AppContainer pendiente (revisor acepta NO HECHO).

EVIDENCIA:
- Paso 1: .scratch/out/rev4_paso1.txt
- Paso 2a: backup en .scratch/backup/...
- Paso 2b/c/d: HEAD d8f604e (D backend/agents/llm_cli/*; M backend/permissions/engine.py permanece staged? git status muestra M backend/permissions/engine.py staged? tras commit solo cambios del commit quedan)
- Paso 3: pub=sha256:c00741179811ff903b515eae28bdeef1f47af6e81c49920c4e68b62954e056d6 calc=C00741179811FF903B515EAE28BDEEF1F47AF6E81C49920C4E68B62954E056D6 COINCIDEN
- Versiones: llama-server 0.6.0-dev (build 11552, commit 23b0202a1)

ARCHIVOS Y COMMITS:
d8f604e (HEAD), 7bf08be, 2e77410, ac368b4, f5dd5ba, 55031f7, 037cd7d, 5a27c43, d9427f5, 187d290,...

=== FIN ===
