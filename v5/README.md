# ARIA OS v5.0 — Electron + React 19 + TypeScript + Three.js

Migración del HUD de PyQt5 (v4) a un stack web nativo de escritorio:

- **Renderer**: React 19 + TypeScript + Vite 5 + Tailwind 3 + Framer Motion + Three.js (r160)
- **Desktop**: Electron 31 + electron-builder 24 (NSIS + portable)
- **Backend**: el mismo FastAPI del v4 (`ARIA_APP/backend/app.py`) lanzado con `uvicorn` y consumido por IPC
- **Puente**: `contextIsolation: true`, `nodeIntegration: false`, `electronAPI` vía `contextBridge`

## Estructura

```
v5/
├─ electron/
│  ├─ main.ts            # ventana frameless, tray, IPC, spawn del backend
│  └─ preload.ts         # contextBridge → window.electronAPI
├─ src/
│  ├─ App.tsx            # layout HUD (header + skills + orbe + chat + control)
│  ├─ components/
│  │  ├─ OrbVisual/      # orbe Three.js (7 capas, partículas, anillos, bursts)
│  │  ├─ Header/         # logo ◆, estado, controles de ventana
│  │  ├─ Chat/           # ChatPanel (markdown + metadata + streaming) y ChatInput
│  │  ├─ Skills/         # sidebar con las skills reales del registry
│  │  └─ Controls/       # centro de control (visual, notificaciones, opacidad, tema)
│  ├─ hooks/             # useOrbState · useChat · useSettings
│  ├─ styles/globals.css # glassmorphism, animaciones, utilidades HUD
│  └─ vite-env.d.ts      # tipos de window.electronAPI
├─ assets/               # icon.ico + icon.png (generados con scripts/gen_icon.py)
└─ electron-builder.yml
```

## Orbe 3D (`src/components/OrbVisual/OrbVisual.tsx`)

- **7 capas**: núcleo + 6 halos con shader fresnel propio (`AdditiveBlending`)
- **12 partículas** en órbitas inclinadas (`THREE.Points` con textura radial en canvas)
- **2 anillos de pulso** que se expanden cada 2 s (desfasados 1 s)
- **Burst rays**: 28 rayos radiales al pasar a `thinking` / `responding` (se desvanecen en 0.85 s)
- **Respiración** de 1.5 s y transición de color suave entre estados
- Estados: `idle` `#38bdf8` · `thinking` `#f59e0b` · `responding` `#00d4ff` · `listening` `#b066ff`
- `dispose()` completo (geometrías, materiales, renderer, ResizeObserver) — sin fugas en remount

## Comandos

```powershell
cd C:\Users\User\Downloads\AURA\v5

npm install            # dependencias
npm run dev            # Vite + Electron (vite-plugin-electron arranca la app)
npm run typecheck      # tsc --noEmit
npm run build          # renderer → dist/ y main/preload → dist-electron/
npm run build:exe      # build + electron-builder --win (NSIS + portable → release/)
```

## Backend

`electron/main.ts` arranca `python -m uvicorn app:app --host 127.0.0.1 --port 8000`
con `cwd = ARIA_APP/backend` (en dev usa el intérprete de `.venv`). Los canales IPC son:

| Canal | Endpoint |
| --- | --- |
| `chat:send` | `POST /api/chat` |
| `skills:load` | `GET /api/skills` |
| `system:status` | `GET /api/system/status` |
| `settings:get` / `settings:set` | `userData/settings.json` (persistencia local) |
| `window:*` | minimizar, maximizar, cerrar, opacidad (`setOpacity`) |

Si el backend no responde, la UI sigue operativa (lista de skills local, mensaje de error en el chat).

## Artefactos

```
artifacts-final/ARIA OS v5.0 Setup 5.0.0.exe   # instalador NSIS (~83 MB)
artifacts-final/ARIA OS v5.0 5.0.0.exe         # portable (~83 MB)
artifacts-final/win-unpacked/                  # app sin empaquetar (app.asar + resources/backend)
```

En un entorno normal el directorio de salida es `release/` (ver `electron-builder.yml`).

## Limitaciones conocidas

1. **Runtime de Python**: el backend se copia a `resources/backend` (extraResources) pero el
   intérprete no está embebido; en modo empaquetado se usa el `python` del sistema. Para un
   standalone puro, colocar un runtime en `resources/python/python.exe` con `fastapi` + `uvicorn`.
2. **Icono del instalador/portable**: `electron-builder` aplica `assets/icon.ico` mediante `rcedit`
   (requiere permiso de creación de symlinks al descomprimir `winCodeSign`). En máquinas con
   *Modo desarrollador* activo funciona por defecto; en entornos restringidos usar
   `-c.win.signAndEditExecutable=false` (los EXE se generan con el icono por defecto de Electron).
   **No aplicar `rcedit` a posteriori sobre el portable/instalador**: trunca el payload SFX.
3. **Sandbox**: si el entorno define `ELECTRON_RUN_AS_NODE=1`, Electron arranca como Node puro y no
   abre ventanas; ejecutar con esa variable sin definir.
