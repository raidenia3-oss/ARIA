# ARIA Raphael Core

HUD web del nucleo Raphael de ARIA. Sitio estatico: sin build, sin bundler, sin
dependencias npm. Se sirve desde cualquier hosting estatico o con un
`python -m http.server` de una linea.

## Inspiration y como se tradujo

| Referencia | Que se tomo | Donde esta aqui |
| --- | --- | --- |
| `brahma-evo.netlify.app` | Paleta `#00f0ff` sobre `#020306`, cajas de cristal con `backdrop-filter`, energy rail lateral con nodos y flicker, cursor con halo de tres capas, overlay de scanline, bloques `terminal`, scroll interno de app shell, pasos numerados con comandos, `energy-flicker` del circuit HUD | `assets/css/raphael.css`, markup de `.rail`, `.cursor-halo`, `body::after`, `.terminal`, `.step` |
| `brahma-evo` → `web_background/index.html` | Resonador de nucleo: `LOBES = 4`, `AMPLITUDE = 0.75`, `SPEED = 0.7`, `targetCameraZ = 46`, bloom `0.75 / 0.35 / 0.75`, tabla `STATE_COLORS` de tres paradas, y los seis builders de la escena | `GEOMETRY` y `NUCLEUS_STATES` en `assets/js/lore.js`, las seis capas en `assets/js/nucleus.js` |
| `brahma-evo` → API global del reactor | `setBrahmaState`, `setPointerNorm`, `setPageCamera`, `setCompactMode`, `accelerateReactor`, `triggerPulse`, `losePower`, `dissolveReactor`, `setReactorSpeed` | `NUCLEUS_CONTROLS` en `assets/js/lore.js`, `controls()` en `assets/js/nucleus.js`, `window.ARIA.nucleus` en `assets/js/app.js` |
| `buildonaut-yt.netlify.app` | Barra superior fija con navegacion, hero con display muy espaciado y titulo partido letra a letra, carrusel de "Latest Blueprints" con flechas y "View All", etiquetas micro-caps en mono, paleta en `oklch()`, radios de pastilla, `backdrop-filter: blur(16px)` | `.topbar`, `.title`, `.carousel`, `.blueprint__tag`, `[data-split]` |
| Tensura — Raphael, Rey de la Sabiduria | Nucleo central con element cores en orbita, cada elemento es un subsistema y su color es su estado | `ELEMENT_CORES` en `assets/js/nucleus.js` |
| Tensura — Gran Sabio, Raphael y Manas Ciel | Onda estacionaria de cuatro lobulos, nodos de destello, halo blanco-calido. **Solo la descripcion**: las busquedas solo devuelven capturas de terceros sin licencia redistribuible (Steam Workshop, Pixiv, Pinterest, ZEDGE, bancos de fondos), asi que no se incrusta ninguna. Todo el arte es canvas original | `drawStandingWave()`, `drawNodes()`, `drawNucleus()` |

### Las seis capas, y por qué esta linea

La segunda pasada por el bundle publicado del reactor leyo los nombres de sus
seis constructores, no se estimaron. Cada uno es ahora una capa:

| Builder del reactor | Capa aqui | Que dibuja |
| --- | --- | --- |
| `buildReferenceMoonBokeh` | `drawBokeh()` | cinco discos suaves fuera de foco, con tabla fija y profundidad |
| `buildAmbientDust` | `drawDust()` | polvo en tres capas de profundidad |
| `buildStandingWaveManifold` | `drawStandingWave()` | `r + 0.75*cos(4*theta)`: cuatro lobulos y cuatro sillas |
| `buildCentralVortexSingularity` | `drawTendrils()` | 36 tentaculos en espiral, ahora con `SPEED = 0.7` |
| `buildGyroscopicOrbitalRings` | `drawRings()` | cuatro anillos, cada uno con su `axis` y su `precess` |
| `buildStarburstNodes` | `drawNodes()` | ocho nodos, cada uno atado a un element core |

Cuatro lobulos no es decoracion: es la forma que dibuja la serie cuando la skill
toma el control, y es el numero que el propio reactor eligio. En movil lo que se
recorta son las **muestras**, nunca los lobulos.

## Manejar el nucleo desde fuera

La pagina expone `window.ARIA`, con la misma forma que el reactor de referencia:

```js
ARIA.nucleus.setState("online");   // "scanning" | "degraded" | "online" | "unavailable"
ARIA.nucleus.setVitality(0.83);    // 0..1
ARIA.nucleus.setCamera(0.5, -0.3); // dolly: acerca la camara y desplaza el nucleo
ARIA.nucleus.setSpeed(1.4);        // multiplica el reloj
ARIA.nucleus.accelerate(2);        // patada de velocidad que decae sola
ARIA.nucleus.triggerPulse(1);      // un latido extra
ARIA.nucleus.losePower();          // baja a 28% de carga
ARIA.nucleus.restorePower();
ARIA.nucleus.dissolve(true);       // dispersa la onda y la vuelve a armar
ARIA.nucleus.setCompactMode(true); // menos muestras
ARIA.state;                        // { nucleus, stage, base }
ARIA.refresh();                    // vuelve a lanzar las seis sondas
```

Regla: los controles mueven pixeles, nunca lecturas. Lo unico que puede cambiar lo
que el HUD afirma es `refresh()`, que vuelve a preguntar a los seis endpoints. Por
eso `window.ARIA.nucleus` no tiene ningun metodo que escriba en el DOM.

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

Hace falta un servidor estatico cualquiera: los ES modules no cargan desde
`file://` porque el navegador los bloquea por CORS (origen `null`).

```powershell
cd v6\raphael_core
python -m http.server 5173
# abrir http://127.0.0.1:5173/
```

Con el servidor levantado, el nucleo queda apagado hasta que le digas donde
esta el backend:

```
http://127.0.0.1:5173/?api=http://localhost:8000
```

Tambien se puede cambiar en caliente desde el propio HUD (campo de la seccion
CORE, boton `Sondear`). La URL se guarda en `localStorage`.

Accesibilidad: `prefers-reduced-motion` detiene la animacion y dibuja un solo
fotograma, y fija el nivel de vida del nucleo al valor medido en ese instante
para que no quede apagado por no tener animacion; en punteros gruesos se oculta
el cursor custom y se mantiene el del navegador.

## Ficheros

```
index.html               markup, sin build
assets/css/raphael.css   sistema visual completo
assets/js/nucleus.js     render del nucleo y las orbitas (canvas 2D)
assets/js/lore.js        nombres, kanji, estados y geometria: declara, no mide
assets/js/api.js         seis sondas, timeouts, clasificacion de estado
assets/js/app.js         navegacion, reveal, titulo partido, carrusel, copia, polling
netlify.toml             publicacion estatica
```