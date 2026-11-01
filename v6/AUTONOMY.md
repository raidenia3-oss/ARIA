# ARIA autónoma — cómo decide sola

Este documento explica de dónde sale el diseño del runtime autónomo de ARIA
(`v6/axum-poc/src/autonomy.rs`), cómo se usa y cómo se le conectan mundos
(Minecraft, VRChat, Discord, móvil).

## De dónde se copió la idea

Hay dos proyectos reales que llevan años haciendo esto bien, y se pueden
estudiar:

* **[Airi](https://github.com/moeru-ai/airi)** (`moeru-ai/airi`) — un
  compañero virtual con voz, cuerpo (VRM/Live2D) y memoria, que además
  juega a Minecraft y Factorio. Su arquitectura separa **Stage** (dónde se
  ve la personaje) de **Core** (quién es) y de **Server Runtime** (el
  websocket por el que hablan todos los escenarios). El personaje no está
  en el escritorio: está en el servidor, y el escritorio es uno más.
* **[Neuro-sama](https://www.youtube.com/@Neurosama)** — la referencia de
  siempre. Lo que la hace distinta a un bot de chat es que *decide*: tiene
  un estado interno (motivación, energía, curiosidad, sociabilidad), elige
  sola qué hacer cuando nadie le pregunta, y a veces **elige callarse**.

Lo que ARIA toma de los dos:

| Patrón | De dónde | Cómo está en ARIA |
|---|---|---|
| El personaje vive en el servidor, el escritorio es un escenario | Airi | El estado está en el backend Axum; `POST /api/autonomy/events` es la puerta de entrada de cualquier mundo |
| Estado interno con pulsiones | Neuro-sama | `curiosidad`, `energia`, `social`, `dominio`, `orden` |
| Intención propia: actuar o callarse | Neuro-sama | Cada *tick* ARIA decide; el modelo puede responder `SILENCIO` |
| Separar elegir de ejecutar | Airi | El modelo propone JSON; el runtime ejecuta con skills reales |
| Cuerpo: expresión y presencia | Airi (VRM/Live2D) | `Presence` + salida OSC a VRChat (`/chatbox/input`, `/avatar/Expression/*`) |
| Memoria por capas | Airi (MindMem) | Los episodios y los eventos se guardan; las skills forjadas se reescriben solas |

Lo que ARIA **no** copia: el modelo de negocio de los VTuber (donaciones,
clips, monetización). Eso es de otro producto.

## Cómo funciona

```
   escenarios                 runtime (backend)                capacidades
   ──────────                 ────────────────────            ───────────
   escritorio  ─┐
   Minecraft    ├─ POST /api/autonomy/events ─▶ pulsiones ─▶┐
   VRChat       │                                     │     ├─▶ laboratorio
   Discord      │                                     │     ├─▶ skills forjadas
   móvil        ┘                                     │     ├─▶ memoria
                                                    │     └─▶ OSC (VRChat)
        ◀── GET /api/autonomy/stream (SSE) ─────────┘
```

1. **Evento**: algo pasa en el mundo (un mensaje, una pregunta, un jugador
   que entra, un fallo). Entra por `POST /api/autonomy/events`.
2. **Pulsión**: el evento se traduce a estado interno. Un mensaje del
   usuario sube `social`; una pregunta sube `curiosidad`; un fallo sube
   `orden` y `dominio`.
3. **Decaimiento**: cada *tick* (30 s) todas las pulsiones bajan un poco.
   Esto es lo que hace que ARIA se calle: sin decaimiento actuaría siempre.
4. **Umbral**: si la pulsión más alta pasa de 0,55 y ha pasado el tiempo
   mínimo entre acciones, ARIA actúa sola.
5. **Decisión**: el modelo recibe el estado y elige una acción en JSON
   (`hablar`, `ideas`, `solucionar`, `mejorar`, `ejecutar`, `recordar`,
   `revisar`, `juego`, `descansar`). Si no hay modelo, hay una política
   local determinista por pulsión. Si el modelo inventa una acción, se
   descarta.
6. **Ejecución**: el runtime la lleva a cabo de verdad (laboratorio de
   creatividad, skills forjadas, memoria) y anota el episodio.
7. **Anuncio**: lo que ARIA dice sale como evento `habla` y llega a todos
   los escenarios por el flujo SSE. En VRChat, además, sale por OSC al
   chatbox del avatar.

### Reacción y iniciativa

Hay dos caminos distintos y es importante que no se mezclen:

* **Reacción**: alguien le pregunta algo → contesta enseguida, sin esperar
  al *tick*. Se dispara desde `ingest_event` cuando el evento trae una
  pregunta (`aria`, `?`, `¿`).
* **Iniciativa**: nadie le ha dicho nada → cuando una pulsión pasa el
  umbral, hace algo por su cuenta. Aquí es donde está la parte "viva".

Los dos comparten cooldown: no contesta dos veces lo mismo en 20 s ni se
pone a actuar sola cada minuto.

## API

| Método | Ruta | Qué hace |
|---|---|---|
| `GET` | `/api/autonomy/status` | Estado completo: persona, pulsiones, presencia, estadísticas, episodios, eventos |
| `GET` | `/api/autonomy/persona` | Lee la persona |
| `POST` | `/api/autonomy/persona` | Guarda la persona (tono, rarezas, valores, intereses) |
| `POST` | `/api/autonomy/mode` | Cambia el modo: `activa`, `tranquila`, `dormida` |
| `POST` | `/api/autonomy/toggle` | Enciende o apaga la autonomía |
| `GET` | `/api/autonomy/events?since=N` | Eventos del mundo |
| `POST` | `/api/autonomy/events` | **Un escenario informa de algo** |
| `POST` | `/api/autonomy/speak` | Que ARIA diga algo ahora |
| `POST` | `/api/autonomy/act` | Obliga a ARIA a hacer algo (`{"action":"ideas","topic":"..."}`) |
| `GET`/`POST` | `/api/autonomy/presence` | Dónde está y qué cara pone |
| `GET` | `/api/autonomy/stream` | Flujo SSE de lo que ARIA dice y hace |
| `POST` | `/api/autonomy/tick` | Fuerza una vuelta del runtime |

Todos piden token: `POST /api/auth/login` con
`{"username":"aria-control-center"}` devuelve el `token`, y va como
`Authorization: Bearer <token>`.

### Configuración

| Variable | Por defecto | Para qué |
|---|---|---|
| `ARIA_AUTONOMY_TICK_SECS` | `30` | Cada cuánto despierta el runtime |
| `ARIA_AUTONOMY_STATE_DIR` | `%LOCALAPPDATA%\ARIA` | Dónde se guarda el estado y la persona |

La persona se guarda en `persona.json` dentro de esa carpeta. Se puede
editar a mano o desde el panel **Presencia** del escritorio.

## Modos

| Modo | Qué hace |
|---|---|
| `tranquila` | Sólo contesta a lo que le dicen (es el modo por defecto) |
| `activa` | Actúa sola cuando una pulsión pasa el umbral |
| `dormida` | No hace nada hasta que la despierten |

## Escenarios (stages)

### Escritorio (v5)

`v5/src/components/Presence/PresencePanel.tsx` es el panel: pulsiones en
barras, lo que ha hecho, el feed en vivo y el editor de personalidad. El
chat recoge lo que ARIA dice por su cuenta (`useChat.pushAriaMessage`) y lo
que el usuario escribe se informa al runtime, para que ella se entere.

### Minecraft

`v6/services/minecraft/` — bot de `mineflayer` que:

* informa de cada mensaje de chat y de cada jugador que entra o sale;
* dice en el juego lo que ARIA dice en el escritorio;
* ejecuta las acciones que ARIA elige (`follow`, `come`, `stop`, `look`,
  `say`). La lista es cerrada: `Action::GAME_COMMANDS`.

```powershell
cd v6\services\minecraft
npm install
$env:ARIA_AUTH_TOKEN = "<token>"
npm start
```

### VRChat

El backend manda OSC a los puertos que VRChat escucha en `localhost`:

* `9000` — `/chatbox/input` con la frase que ARIA dice.
* `9001` — `/avatar/Expression/N` con la expresión (`1` alegre, `2`
  enfadada, `3` triste, `4` sorprendida, `5` curiosa).

El emisor está en `v6/axum-poc/src/osc.rs`, escrito a mano para no añadir
dependencias al crate.

### Cualquier otro

Un escenario nuevo sólo necesita dos cosas:

1. `POST /api/autonomy/events` para informar.
2. Escuchar `GET /api/autonomy/stream` (SSE) para obedecer.

`v6/services/minecraft/src/runtime.mjs` es una implementación de esas dos
cosas en 80 líneas, y sirve de plantilla.

## Lo que todavía no hace

- No hay columna vertebral de memoria a largo plazo: los episodios se
  guardan en el estado, pero no se recuperan por significado (el módulo de
  memoria del backend tiene la tabla `semantic_memory`, y la integración
  con el runtime está pendiente).
- El modelo decide **qué** hacer, no **cómo** se ejecuta en el mundo: los
  comandos de juego son una lista cerrada.
- La voz (STT/TTS) ya funciona, pero el runtime no la usa todavía: cuando
  ARIA habla sola, su frase llega al escritorio y a VRChat, pero no se
  vocaliza sola.
