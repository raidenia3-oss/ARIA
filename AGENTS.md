# REGLA FIJA DE ARIA (versión 2, reemplaza a la anterior)
ARIA es una aplicación de escritorio (PyQt5) en UN solo proceso. ARIA NO se construye sobre servidores ni servicios: todo lo que necesita para arrancar y pensar vive dentro de su propio proceso o en archivos locales.
ARIA SÍ puede usar internet (como una persona con un navegador): buscar, descargar, consultar páginas o APIs públicas. Eso es una CAPACIDAD (skill), no una dependencia.

NO (prohibido):
1. Abrir puertos o servidores: ARIA nunca "escucha" (bind/listen, http.server, socketserver, Flask, FastAPI, uvicorn, aiohttp.web, Axum, Tauri/Electron con servidor, servidor WebSocket).
2. Hablar con servicios de la propia PC para funcionar: nada de localhost / 127.0.0.1 / ::1 / 0.0.0.0 ni puertos 8000, 8002, 8080, 11434, 11500. Incluye Ollama, llama-server, LM Studio y cualquier endpoint "OpenAI-compatible" local.
3. Necesitar internet para arrancar o para lo básico: sin red, ARIA debe arrancar, mostrar su interfaz, usar su memoria, sus skills locales y su LLM local.
4. Interfaz en navegador o HTML servido. Procesos de fondo que abran puertos "para probar".
5. Dependencias nuevas sin aprobación: no instales paquetes por tu cuenta; repórtalo como "DEPENDENCIA PROPUESTA: <nombre> | motivo | alternativa stdlib".

SÍ (permitido y deseado):
- Salir a internet desde skills de red (buscar en la web, descargar un archivo, whois, consultar una API pública) usando solo la biblioteca estándar (urllib.request / http.client / ssl). Cada salida pasa por el PermissionEngine, queda en el log (dominio, motivo, resultado) y falla cerrado si no hay permiso.
- Ejecutar herramientas del sistema como subprocesos o pipes (nmap, whois, tor, tcpdump...), con permiso.
- LLM dentro del mismo proceso, o proceso hijo por stdin/stdout; datos en SQLite o archivos; llamadas directas entre módulos y señales de Qt.

SKILLS QUE ARIA CREE: solo biblioteca estándar. No instalan paquetes, no abren puertos, no hablan con localhost.
EJEMPLOS. BIEN: urllib.request.urlopen("https://ejemplo.com") dentro de una skill web_fetch. MAL: uvicorn.run(...), socket.listen(), http.server, urlopen("http://127.0.0.1:11434").
LEGADO (no extender, no arrancar, no borrar sin orden): backend/ (FastAPI), v5/, v6/axum-poc, packages/backend, aura-v5-tauri-webgpu.
VERIFICACIÓN: la guardia falla si ARIA escucha en un puerto o se conecta a loopback. NO falla por conexiones salientes a internet hechas desde skills de red.

# AURA OS v2.0 â€” Instrucciones de Desarrollo

## â›” REGLA CRÃTICA â€” Nunca terminar procesos del usuario

**Incidente del 2026-10-19**: ARIA ejecutÃ³ `taskkill /F /IM chrome.exe` para
intentar leer la base de cookies del navegador y **cerrÃ³ las ~28 ventanas de
Chrome que el usuario tenÃ­a abiertas**. TambiÃ©n cerrÃ³ procesos de Edge. Eso no
se repite ni por error ni por "optimizaciÃ³n".

Regla inviolable, para cualquier agente, script o skill de este repo:

1. **Nunca** uses `taskkill /IM`, `Stop-Process -Name`, `killall`, `pkill -f <lenguaje>`
   ni `wmic process ... delete`. Matar por nombre de imagen mata procesos que
   nadie eligiÃ³, incluyendo ventanas abiertas del usuario.
2. **Nunca** cierres navegadores, exploradores de archivos, editores, terminales
   ni aplicaciones del usuario (Chrome, Edge, Firefox, explorer.exe, Code,
   Notepad, cmd, WhatsApp, Discord, Spotify, Steam, â€¦).
3. Solo se terminan procesos **con PID explÃ­cito** y **verificando que ARIA los
   creÃ³** (descendiente del proceso de ARIA o registrado por ella).
4. Para inspeccionar sin tocar nada: `Get-Process`, `Get-CimInstance
   Win32_Process`, o la skill `process_list`.
5. Para cerrar: skill `process_terminate` con PID, o
   `ARIA_APP/backend/process_guard.py::safe_terminate()`.
6. Si una tarea parece requerir cerrar el navegador del usuario, **estÃ¡ mal
   planteada**: usa una vÃ­a no destructiva (perfil separado de Chrome con
   `--user-data-dir`, `yt-dlp --cookies-from-browser` sin matar nada, descarga
   directa, etc.).

El guard vive en `ARIA_APP/backend/process_guard.py` y estÃ¡ verificado por el
gate `tests/gates/test_process_guard.py` (falla si alguien reintroduce un kill
por nombre). El filtro de shell `ARIA_APP/backend/safety_filter.py` bloquea los
comandos de kill masivo antes de ejecutarlos.

## Build (Windows â€” PowerShell)
```powershell
cd C:\Users\User\Downloads\AURA
# ARIA OS v4.0 â€” Desktop Standalone (sin HTTP, sin servidores)
.venv\Scripts\python.exe -m PyInstaller --onefile --windowed --name "AURA OS" ^
  --add-data "AURA_APP\frontend;frontend" ^
  --add-data "ai_providers.py;." ^
  --hidden-import ai_providers ^
  --hidden-import backend.skills --hidden-import backend.skills.registry ^
  --hidden-import backend.skills.system ^
  --hidden-import backend.skills.system.status --hidden-import backend.skills.system.time ^
  --hidden-import backend.skills.system.ping --hidden-import backend.skills.system.scan ^
  --hidden-import backend.skills.system.whois --hidden-import backend.skills.system.open ^
  --hidden-import backend.skills.system.volume --hidden-import backend.skills.system.lock ^
  --hidden-import backend.skills.system.apps --hidden-import backend.skills.system.screenshot ^
  --hidden-import backend.skills.system.memory ^
  --hidden-import backend.skills.web --hidden-import backend.skills.web.search ^
  --hidden-import backend.skills.web.weather ^
  --hidden-import backend.skills.files --hidden-import backend.skills.files.list ^
  --hidden-import backend.skills.files.read --hidden-import backend.skills.files.write ^
  --hidden-import backend.memory --hidden-import backend.memory.working ^
  --hidden-import backend.memory.short_term --hidden-import backend.memory.long_term ^
  --hidden-import backend.proactive.engine --hidden-import backend.evolution.engine ^
  --hidden-import backend.learning.compound --hidden-import backend.api.compat ^
  --hidden-import AURA_APP.desktop_ui ^
  --hidden-import AURA_APP.aria_logic_engine ^
  --hidden-import desktop_tray ^
  --hidden-import auto_start ^
  --hidden-import PyQt5 --hidden-import PyQt5.QtWidgets ^
  --hidden-import PyQt5.QtCore ^
  --hidden-import PyQt5.QtGui ^
  --collect-all fastapi --collect-all uvicorn --collect-all pywebview ^
  --noconfirm AURA_APP\aria_main.py
```

### EjecuciÃ³n v4.0 (Standalone Desktop)
```powershell
# Sin servidor HTTP â€” desktop nativo con IPC interna
.venv\Scripts\python.exe AURA_APP\aria_main.py
```

## Start / Stop / Status
```powershell
.\aura-os\scripts\start-aura-app.ps1 -Exe      # Lanza dist\AURA OS.exe
.\aura-os\scripts\start-aura-app.ps1            # Lanza con python (dev)
.\aura-os\scripts\start-aura-app.ps1 -Stop
.\aura-os\scripts\start-aura-app.ps1 -Status
```

## ValidaciÃ³n rÃ¡pida
```powershell
curl.exe -s http://localhost:8000/health
curl.exe -s http://localhost:8000/api/system/status
curl.exe -s http://localhost:8000/chat/tools | ConvertFrom-Json | Measure-Object
```

## ARIA OS v5.0 (Electron + React + Three.js) â€” en `v5/`
```powershell
cd C:\Users\User\Downloads\AURA\v5
npm install            # deps (React 19, Three, Electron 31, framer-motion, zustand)
npm run dev            # Vite + Electron (auto-start del backend FastAPI v4 en :8000)
npm run typecheck      # tsc --noEmit
npm run build          # dist/ (renderer) + dist-electron/ (main + preload)
npm run build:exe      # electron-builder --win â†’ release/ (NSIS + portable)
```
- Backend: `ARIA_APP/backend/app.py` vÃ­a `uvicorn app:app --port 8000` (spawn del main process).
- IPC: `chat:send`, `skills:load`, `system:status`, `settings:get|set` (userData/settings.json), `window:*`.
- HUD: header glass + orb 3D (7 capas/12 partÃ­culas/anillos/bursts) + chat markdown + skills sidebar + centro de control.
- Detalles y limitaciones: `v5/README.md`.

## Estructura clave
- `AURA_APP/frontend/index.html` â€” HUD glassmorphic (25 skills, 10 tools)
- `AURA_APP/backend/` â€” FastAPI backend, skills registry (imports estÃ¡ticos)
- `AURA_APP/frontend/index.html` â€” HUD glassmorphic
- `dist/AURA OS.exe` â€” ejecutable standalone (337MB)

