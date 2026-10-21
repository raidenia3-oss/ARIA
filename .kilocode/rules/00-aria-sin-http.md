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
