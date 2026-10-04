# ARIA Raphael Core

HUD web del nucleo Raphael de ARIA. Sitio estatico: sin build, sin bundler, sin
dependencias npm. Se abre con doble clic o se sirve desde cualquier hosting
estatico.

## Inspiration y como se tradujo

| Referencia | Que se tomo | Donde esta aqui |
| --- | --- | --- |
| `brahma-evo.netlify.app` | Paleta `#00f0ff` sobre `#020306`, cajas de cristal con `backdrop-filter`, energy rail lateral con nodos y flicker, cursor con halo, overlay de scanline, bloques `terminal`, stack Outfit/Inter/Courier | `assets/css/raphael.css`, markup de `.rail`, `.cursor-halo`, `body::after`, `.terminal` |
| `brahma-evo` → `web_background/index.html` | Resonador de nucleo: manifold de ondas en pie de 92 lineas y 4 lobulos con bloom | `drawLattice()` y `drawNucleus()` en `assets/js/nucleus.js` |
| `buildonaut-yt.netlify.app` | Barra superior fija con navegacion, hero con display muy espaciado, carrusel de "Latest Blueprints" con flechas, etiquetas micro-caps en mono | `.topbar`, `.title`, `.carousel`, `.blueprint__tag` |
| Tensura — Raphael, Rey de la Sabiduria | Nucleo central con element cores en orbita, cada elemento es un subsistema y su color es su estado | `ELEMENT_CORES` en `assets/js/nucleus.js` |

## Arquitectura de Raphael, mapeada a ARIA

Cada element core esta enlazado a un endpoint que existe en este repositorio.
El nucleo no enciende un color propio: lo enciende la respuesta.

| Core | Subsistema de ARIA | Endpoint | Handler |
| --- | --- | --- | --- |
| FUEGO | El proceso vive | `GET /health` | `backend/main.py` |
| AGUA | Dependencias (DB, Redis, modelo local) | `GET /health/detailed` | `backend/main.py` |
| TIERRA | Enjambre de agentes | `GET /api/swarm/agents/status` | `backend/swarm_routes.py` |
| VIENTO | Contadores de despacho | `GET /api/swarm/metrics` | `backend/swarm_routes.py` |
| LUZ | Catalogo de 12 roles APEX | `GET /api/swarm/roles` | `backend/swarm_routes.py` |
| SOMBRA | Estado del enjambre | `GET /api/swarm/status` | `backend/swarm_routes.py` |

### `/api/swarm/status` tiene dos handlers

`backend/swarm_routes.py` registra dos veces la misma ruta: la de la linea 95
(`swarm.get_status()`) y la unificada de la linea 327 (`swarm`,
`orchestrator`, `self_healing`, `process_monitor`). Starlette resuelve por orden
de registro, asi que la unificada es inalcanzable y la que responde devuelve
contadores del enjambre (`agents_by_role`, `agents_total`, `queue`,
`task_status_counts`, `tasks_total`, `plans_total`, `bus_messages`,
`execution_history_count`, `timestamp`).

Comprobado con `TestClient` sobre `backend.main:app`, no de memoria. Por eso el
HUD recorre ese payload tal cual, sin asumir la forma que el handler unificado
promete. Es el mismo tipo de sombreado que se corrigio en `/health` durante la
Ola 5: un endpoint inalcanzable debe declararse, no fingirse.

## Honestidad de los datos

Es la misma regla que imposed al backend, llevada hasta el DOM:

- Una sonda que no responde produce `unavailable` y el motivo (`sin red o
  bloqueado por CORS`, `sin respuesta en 2500 ms`, `respuesta 503`). Nunca un
  cero de relleno.
- `/health` ya devuelve `data_source: "unavailable"` con su `detail`, porque ese
  endpoint no sondea nada. El HUD lo enseña tal cual en vez de Dressingarlo
  como salud.
- Un campo que el backend no expone no se inventa: los contadores de
  `/api/swarm/metrics` y las capas de `/api/swarm/status` se recorren tal cual
  vienen, sin asumir nombres de campo.
- La seccion BLUEPRINTS cita rutas del arbol verificadas. Si un modulo no
  existe, no aparece: `backend/llm/smart_router.py` se descarto precisamente
  por eso.

## CORS: por que puede verse todo apagado

La pagina corre en un origen distinto al backend, asi que el navegador exige
CORS. `backend/main.py` lo resuelve con una lista explicita en
`AURA_CORS_ORIGINS` (separada por comas), que por defecto solo incluye
`localhost:3000`, `localhost:8000`, `127.0.0.1:8000` y `frontend:3000`.

```powershell
$env:AURA_CORS_ORIGINS="http://localhost:8000,http://localhost:3000,http://localhost:5173,https://tu-sitio.netlify.app"
```

Sin ese paso, el HUD no miente: muestra las seis sondas en `unavailable` con el
motivo. La URL del backend se cambia en el propio HUD (campo `Sondear`) o por
query: `index.html?api=http://localhost:8002`. La eleccion se guarda en
`localStorage` bajo `aria.raphael.apiBase`.

## Uso

```powershell
# Abrir sin servidor
start v6\raphael_core\index.html

# O servirlo
cd v6\raphael_core
python -m http.server 5173
```

Accesibilidad: `prefers-reduced-motion` detiene la animacion y dibuja un solo
fotograma; en punteros gruesos se oculta el cursor custom y se mantiene el del
navegador.

## Ficheros

```
index.html               markup, sin build
assets/css/raphael.css   sistema visual completo
assets/js/nucleus.js     render del nucleo y las orbitas (canvas 2D)
assets/js/api.js         seis sondas, timeouts, clasificacion de estado
assets/js/app.js         navegacion, reveal, carrusel, copia, polling
netlify.toml             publicacion estatica
```