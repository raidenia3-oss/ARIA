# ARIA Control Center

Centro de control de ARIA OS: un dashboard de terminal, una API web y un CLI.
Las tres son el mismo sistema — el TUI es un cliente delgado de `/api/control/*`
sobre el backend Axum, así que cualquier cosa que la terminal puede hacer, también
la pueden la UI web y el marketplace.

```
aria_control/          cliente Python (dashboard Rich + CLI click)
v6/axum-poc/src/control.rs   API de control en Rust
```

---

## Arranque rápido

```powershell
# 1. El backend imprime su API key al arrancar; expóntala para el cliente.
$env:ARIA_API_KEY = "dev-control-center-key"
$env:ARIA_BACKEND_URL = "http://127.0.0.1:8002"

# 2. El dashboard
.venv\Scripts\python.exe -m aria_control status
.venv\Scripts\python.exe -m aria_control status --watch

# 3. O, instalado como comando
pip install -e .
aria status
```

Sin backend, `aria status` no revienta: muestra un panel rojo con el motivo del
fallo. El caso más común de uso es justo *antes* de que el backend esté arriba.

---

## API web

Todas las rutas viven bajo `/api/control/*` en el backend Axum (`:8002`).

| Método | Ruta | Qué hace |
|---|---|---|
| `GET` | `/api/control/status` | versión, canal, uptime, servicios, config, último chequeo de actualización |
| `GET` | `/api/control/services` | un registro por servicio con estado, PID y puerto |
| `GET` | `/api/control/logs?lines=50` | cola circular de logs (tope 1000) |
| `GET` (WS) | `/api/control/logs/stream` | logs en vivo; al conectar envía primero el backlog |
| `GET` | `/api/control/config` | todos los settings con valor, default y descripción |
| `POST` | `/api/control/config` | `{"key": "...", "value": "..."}` |
| `POST` | `/api/control/restart` | `202` + `job_id`; despacha un comando desacoplado |
| `POST` | `/api/control/upgrade` | `202` + `job_id`; aplica una actualización |
| `GET` | `/api/control/jobs/:id` | resultado de un job despachado |
| `GET` | `/api/control/plugins` | catálogo de plugins instalados |
| `POST` | `/api/control/plugins/:name/install` | `501` — el marketplace aún no existe |

### Autenticación

**Ninguna de estas rutas es pública.** Todas pasan por el middleware
`auth::guard` y exigen `Authorization: Bearer $ARIA_API_KEY` (o `X-API-Key`).

`/api/control/restart` reinicia la máquina, `/api/control/config` escribe
configuración y `/api/control/logs` expone lo que se registró. Un plano de control
abierto en `0.0.0.0:8002` sería un shell remoto. No añadas `/api/control` a
`PUBLIC_PATHS` en `auth.rs`; hay un test que lo verifica.

```powershell
curl.exe -H "Authorization: Bearer $env:ARIA_API_KEY" `
  http://127.0.0.1:8002/api/control/status
```

### Configuración: allowlist, no un diccionario libre

`POST /api/control/config` rechaza claves desconocidas con `400`. Un almacén
clave/valor abierto en una máquina que también guarda `ARIA_API_KEY` y el token
de Discord es una primitiva de escritura arbitraria. La única forma soportada de
añadir un setting es extender `CONFIG_SCHEMA` en `control.rs`.

| Clave | Default | Valores |
|---|---|---|
| `release-channel` | `stable` | `stable`, `testing` |
| `update-check-interval-seconds` | `21600` | 300 – 86400 |
| `update-check-enabled` | `true` | booleano |
| `autonomy-enabled` | `true` | booleano |
| `orb-autostart` | `false` | booleano |
| `log-level` | `info` | `error`, `warn`, `info`, `debug`, `trace` |
| `daemon-port` | `8002` | 1 – 65535 |

Los valores se persisten en `control.json` dentro de `ARIA_CONTROL_STATE_DIR`, y
por defecto en un directorio **por usuario** — `%LOCALAPPDATA%\ARIA` en Windows,
`$XDG_DATA_HOME/aria` o `~/.local/share/aria` en el resto. Nunca relativo al cwd:
el directorio de trabajo del servidor depende de cómo se arrancó, así que una
ruta relativa escribiría un config distinto según el método de arranque (y un
config que `cargo clean` borra no es un config).

Los valores se **revalidan al cargar**: un archivo editado a mano no puede
inyectar un valor fuera de esquema ni sobrevivir a un cambio de schema.

### Por qué `restart` y `upgrade` responden `202`

Ambos son largos y ambos pueden reiniciar el proceso que está sirviendo la
petición. Matarlo en línea dejaría la respuesta a medio camino en el socket.

Cada uno se despacha como un **job desacoplado**; la llamada devuelve
`202 Accepted` con un `job_id`, y el resultado se lee de
`GET /api/control/jobs/:id`. Un `202` que no se puede seguir es una mentira.

Los comandos son configurables y por defecto apuntan al updater que aún no está
construido:

| Variable | Default |
|---|---|
| `ARIA_RESTART_COMMAND` | `aria-updater.exe --restart-services` |
| `ARIA_UPGRADE_COMMAND` | `aria-updater.exe --apply` |
| `ARIA_UPGRADE_TIMEOUT_SECS` | `300` (tope 3600) |

El comando se parte por espacios, sin quoting ni expansión de shell: pasar un
valor de configuración a un shell es exactamente cómo ocurre una inyección de
argumentos. La salida se recorta a los últimos 4 KiB, nunca partiendo un
carácter UTF-8 a la mitad.

---

## Dashboard (Rich)

```
aria status              una pasada, determinista, apto para CI y pipes
aria status --watch      refresca en vivo hasta Ctrl+C
aria status --json       payload crudo
```

Los glyphs son ASCII-safe (`OK` / `DOWN` / `?`). ARIA corre sobre consolas
Windows donde los emoji se degradan a mojibake, y un dashboard ilegible es peor
que uno plano.

`--watch` usa `rich.live.Live` y sale con `Ctrl+C`. La navegación de una tecla
(`[s] [l] [p] [c] [q]`) que planteaba el spec original **no está implementada**:
requiere una capa de entrada consciente del terminal, y `textual` no está
instalado. Preferimos un `Ctrl+C` honesto a un `while True: sleep(1)` que no
termina nunca y no se puede testear.

---

## CLI

```
aria status [--watch] [--json] [--logs N]
aria logs [-n N] [-f] [--json]
aria config list [--json]
aria config get KEY [--json]
aria config set KEY VALUE [--json]
aria services [--json]
aria plugins  [--json]
aria restart  [-y] [--wait] [--json]
aria upgrade  [-y] [--wait] [--json]
aria job JOB_ID [--json]
```

Códigos de salida:

| Código | Significado |
|---|---|
| 0 | éxito |
| 2 | backend inaccesible |
| 3 | el plano de control respondió con error |
| 4 | no hay bearer token configurado |

`--json` está en todos los comandos de lectura: los scripts y la CI nunca
parsean ANSI. Los comandos que mutan (`restart`, `upgrade`) piden confirmación
salvo con `-y`.

### `aria logs -f`

Se conecta a `ws://…/api/control/logs/stream` mandando el token en las cabeceras
del handshake (Axum lo lee de `Authorization` o `x-api-key`). El buffer del
cliente está acotado a 500 entradas; los frames que no parsean se descartan en
silencio. Requiere el paquete `websockets`.

---

## Servicios y liveness

| Servicio | Señal | Sin señal |
|---|---|---|
| `axum-backend` | este proceso, siempre activo | — |
| `fastapi-legacy` | TCP `:8001` | — |
| `ollama` | TCP `:11434` | — |
| `autonomous-controller` | — | `ARIA_AUTONOMOUS_PID` |
| `usb-aria-agent` | — | `ARIA_USB_PID` |
| `discord-bot` | — | `ARIA_DISCORD_PID` |

Los servicios con puerto se sondean de verdad (connect TCP con 400 ms de
timeout). Los que no lo tienen **no se verifican**: se reporta el PID que
`ARIA_*_PID` declare, y `unknown` cuando no hay variable. Enumerar procesos
requeriría una dependencia que este crate no toma, y adivinar el estado de un
proceso es peor que admitir que no se sabe.

---

## Logs

La cola circular (`LOG_RING_CAPACITY = 500`) la alimenta una capa de `tracing`
(`ControlLogLayer`) instalada en `main.rs`, así que captura todo evento
`tracing` que emite el servicio: fallos de auth, rechazos por rate limit,
actividad del daemon. Un consumidor WebSocket lento recibe un aviso `lagged` en
lugar de perder líneas en silencio.

**Limitación conocida:** los `println!` legacy de los módulos más antiguos no
pasan por `tracing` y **no** aparecen en `/api/control/logs`. Convertirlos todos
es un trabajo aparte; la alternativa sería enrutar stdout a un fichero y
tail-earlo.

El buffer es acotado a propósito: un buffer sin límite detrás de un endpoint que
cualquiera puede leer es una primitiva de agotamiento de memoria. `?lines=` se
acota a 1000.

---

## Verificación

```powershell
# Rust: 25 tests unitarios (config, uptime, cola, servicios, jobs, comandos)
cd v6\axum-poc; cargo test --offline --lib

# Python: 37 tests (cliente, dashboard, CLI, contrato del repo)
.venv\Scripts\python.exe -m pytest tests\test_control_center.py -q
```

Los tests de Python no tocan la red: `StaticTransport` implementa el protocolo
`Transport` y una suite de centro de control que necesita un backend vivo en
`:8002` solo pasa en la máquina de quien la escribió.

---

## Qué NO está (y por qué)

| Falta | Motivo |
|---|---|
| Navegación TUI por teclas | requiere `textual`, no instalado; `Ctrl+C` es la salida honesta |
| `POST /plugins/{name}/install` real | necesita el marketplace firmado (entry-point, verificación de firma, resolución de dependencias). Devuelve `501` en vez de un `200` falso: un stub que dice "instalado" cuando no pasó nada es peor que un `501` |
| `aria-updater` | el backend despacha el comando configurado; hoy el binario no existe y el job lo reporta honestamente como `failed: program not found` |
| Replicar en la UI React de v5 | los endpoints ya están; el frontend es trabajo aparte |

## Orden de trabajo siguiente

1. `aria-updater` real (PR-0g) — hoy `restart`/`upgrade` despachan a un binario inexistente.
2. Marketplace firmado (PR-0h) — habilita `POST /plugins/{name}/install`.
3. React: panel de control en `v5/` consumiendo estos endpoints.
4. `textual` — navegación por teclas en el dashboard.

Ver también `docs/VERSIONING.md` (fuente única de versión) y
`docs/ROLLING_RELEASE_RESEARCH.md` (layout versionado + TUF para el updater).
