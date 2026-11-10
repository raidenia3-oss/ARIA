# Cuarentena — scripts muertos (regla v2)

Aquí se movieron scripts que arrancan servidores HTTP/localhost (prohibido por la
regla fija v2 de ARIA: sin servidores, sin localhost, sin puertos). NO se borran,
solo se aíslan para no confundir al arranque standalone (PyQt5, un solo proceso).

- `_start_server.py` / `_start_server2.py`: `uvicorn.run(app, host=..., port=8000)` — FastAPI servidor.
- `_uvicorn_aura.py`: `uvicorn.run(aura_runner.app, host="0.0.0.0", port=8000)` — servidor en todas las interfaces.
- `_test_webview.py`: `webview.create_window(url="http://localhost:8000")` — depende del backend FastAPI en localhost.
- `_test_import3.py`: importa `backend.app` (FastAPI) y hace `os.chdir` al repo.

Motivo: bajo la regla v2, ARIA es escritorio standalone (PyQt5, un proceso, sin HTTP).
El backend FastAPI vive en `backend/` como legado deprecated y no se arranca desde el
desktop. Estos scripts no son usados por `aria_main.py` ni `desktop_ui.py`.

Si se necesita recuperar: `git mv ARIA_APP/cuarentena/<archivo> ARIA_APP/<archivo>`.
