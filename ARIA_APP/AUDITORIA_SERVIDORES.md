# Auditoria de servidores / localhost — ARIA desktop (regla v2)

Fecha: 2026-11-09
Rama: feat/aria-unified
Alcance: `ARIA_APP/` (desktop standalone PyQt5, un solo proceso).

## Resultado: SIN servidores activos, SIN localhost requerido para funcionar

### 1. Que NO hay (activo)
- `uvicorn.run`, `FastAPI(...)`, `http.server`, `socketserver`, `Flask`, `aiohttp.web` -> ausentes en el camino de arranque del desktop (`aria_main.py`, `desktop_ui.py`, `ui_shell.py`).
- `bind(` / `listen(` -> ausentes. ARIA nunca escucha puertos.
- Conexión a `127.0.0.1` / `localhost` / `::1` / `0.0.0.0` como dependencia de arranque -> ausente en el núcleo activo.

### 2. Referencias localhost encontradas (INACTIVAS / legado)
Estas existen en archivos pero NO se ejecutan ni son necesarias para que ARIA arranque y funcione:

| Archivo | Línea | Qué dice | Estado |
|---|---|---|---|
| `ai_providers.py` | 27, 51-52, 130, 139, 169, 278 | `http://localhost:11434` (ollama) | Config de proveedor inactivo; `local` (llama.cpp) es el disponible (prioridad 99). Ollama no se requiere. |
| `app_native.py` | 35 | `http://localhost:8000/health` | Launcher legado (pywebview) apuntando al backend FastAPI deprecated. No usado por `aria_main.py`. |
| `aria_browser.py` | 33, 78, 90 | `http://127.0.0.1:<PORT>` | Puerto de depuracion de Chrome (legacy). El navegador activo es `aria_browser_v2.py` (Playwright, sin puertos). |

### 3. Uso de `socket` (activo, permitido)
- `aria_va_core.py:2011` -> `import socket` usado en `_whois_lookup` (WHOIS saliente a `whois.iana.org:43`). Es una conexion saliente a internet (habilitada por regla v2 como skill de red), no un servidor ni localhost.

### 4. Legado deprecated
- `ARIA_APP/backend/` (FastAPI, 138 routes, websockets, puertos 8000/8002) -> **deprecated**, no se arranca desde el desktop standalone. Queda como legado sin extender (orden del proyecto).

### 5. Scripts muertos movidos a cuarentena
`_start_server.py`, `_start_server2.py`, `_uvicorn_aura.py`, `_test_webview.py`, `_test_import3.py` -> `ARIA_APP/cuarentena/` (commit 6d750c6).

## Verificacion
- `python -m py_compile ARIA_APP/aria_va_core.py` -> OK.
- `grep -R "uvicorn\|http.server\|FastAPI\|bind(" ARIA_APP/*.py` -> sin hits en el camino desktop activo.
