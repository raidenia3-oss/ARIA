# ARIA OS Nativo — Arquitectura sin servidor, sin puertos, sin navegador

> ARIA OS corre como **aplicación de escritorio nativa**. No abre puertos TCP, no corre FastAPI, no necesita uvicorn, no usa navegador ni webview. Todo corre en un solo proceso local.

---

## Arquitectura

```
ARIA OS Nativa (proceso único)
├── UI (PyQt5) — ventana nativa del SO
│   ├── Orb visual (estado: idle / listening / talking / thinking / error)
│   ├── Chat (usuaria ↔ ARIA)
│   ├── Panel de habilidades
│   └── Centro de control (estado, ping, habilidades)
├── Logic Engine (mismo proceso, llamada directa)
│   ├── chat — conversación con IA
│   ├── skill — ejecución de habilidades (drive, system, etc.)
│   ├── tool — ejecución de herramientas
│   ├── list_skills / status / ping — introspección
│   └── IA Provider: Ollama (localhost:11434) → fallback local rule-based
└── Almacenamiento local (SQLite, Chroma, JSON en disco)
```

**Nunca se abre un puerto.** No hay servidor HTTP. No hay red necesaria salvo para consultar Ollama (opcional; si no está, usa modo local).

---

## Archivos clave

| Archivo | Propósito |
|---------|-----------|
| `ARIA_APP/aria_native.py` | Entry point. Carga `.env`, importa `native_core`, llama `main()`. |
| `ARIA_APP/native_core.py` | Núcleo todo-en-uno: `NativeAIProvider` + `NativeLogicEngine` + `MainWindow` (PyQt5). |
| `ARIA_APP/aria_logic_engine.py` | Motor de lógica original (IPC stdin/stdout), mantenido para compatibilidad. |
| `ARIA_APP/desktop_ui.py` | UI original con `_LogicBridge` / `IPCClient` (subproceso), mantenida para compatibilidad. |
| `ARIA_APP/.env` | Configuración: `ARIA_OLLAMA_URL`, `ARIA_OLLAMA_MODEL`, `ARIA_SYSTEM_PROMPT`, etc. |

---

## Ejecución (desarrollo)

```powershell
cd C:\Users\User\Downloads\AURA
.venv\Scripts\python.exe ARIA_APP\aria_native.py
```

La ventana "ARIA OS v4.0 — Nativo" aparece directamente en el escritorio. No hay `localhost:8000`. No hay navegador.

---

## Build (ejecutable standalone, un solo archivo)

```powershell
cd C:\Users\User\Downloads\AURA
.venv\Scripts\python.exe -m PyInstaller --onefile --windowed ^
  --name "ARIA OS" ^
  --add-data "ARIA_APP\.env;ARIA_APP" ^
  --hidden-import native_core ^
  --hidden-import PyQt5 --hidden-import PyQt5.QtWidgets ^
  --hidden-import PyQt5.QtCore --hidden-import PyQt5.QtGui ^
  --noconfirm ARIA_APP\aria_native.py
```

Resultado: `dist/ARIA OS.exe` — doble clic y ARIA arranca como app nativa de Windows.

---

## Diferencia con la arquitectura anterior (FastAPI :8000)

| Aspecto | Antes (FastAPI) | Ahora (ARIA OS Nativo) |
|---------|----------------|------------------------|
| Servidor | FastAPI + uvicorn en :8000 | Ninguno (proceso único) |
| Puertos TCP | 8000 (HTTP) | Cero |
| UI | Navegador / webview / dashboard HTML | Ventana PyQt5 nativa |
| Lógica | Subproceso vía pipes JSON | Llamada directa en mismo proceso |
| IA | Ollama via HTTP (router multi-proveedor) | Ollama directa o fallback local |
| Red requerida | Sí (localhost) | Opcional (solo Ollama) |
| Distribución | 337MB con dependencias web | Un .exe autocontenido |

---

## Habilidades nativas incluidas

- `status` — estado del sistema (uptime, proveedor IA, modo nativo)
- `skills` — listar habilidades disponibles
- `ping` — prueba interna de respuesta
- `time` — hora y fecha actual
- `drive` — visión autónoma de Google Drive (ARIA Eyes, modelo local `granite3.2-vision:2b`)

---

## Extensibilidad

Se pueden añadir habilidades nuevas registrando entradas en `NativeLogicEngine._skills` e implementando sus handlers en `_handle_skill`. No se requiere tocar la UI ni crear endpoints HTTP.
