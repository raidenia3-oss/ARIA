# Adaptador de Minecraft para ARIA

Este servicio pone a ARIA dentro de un mundo de Minecraft: oye el chat,
sigue a los jugadores, habla cuando el runtime decide hablar y ejecuta las
acciones que ARIA elige sola.

Es el mismo patrón que usa [Airi](https://github.com/moeru-ai/airi) con su
servicio `services/minecraft`: el personaje vive en el runtime (el backend
Axum) y el juego es sólo un escenario más.

## Cómo funciona

```
   jugadores ──chat──▶  mineflayer  ──POST /api/autonomy/events──▶  ARIA
                                                                       │
   jugadores ◀──chat──  mineflayer  ◀──/api/autonomy/stream───────────┘
```

* **Hacia ARIA**: cada mensaje del chat, cada jugador que entra o sale, y
  la presencia del bot, se(info)rman como eventos del mundo.
* **Desde ARIA**: el flujo de eventos trae dos cosas: `habla` (la frase que
  ARIA dice, y que el bot repite en el chat) y `accion` (`follow`, `come`,
  `stop`, `look`, `say`).

## Puesta en marcha

```powershell
cd C:\Users\User\Downloads\AURA\v6\services\minecraft
npm install

# Token del backend: POST /api/auth/login -> {"username":"aria-control-center"}
$env:ARIA_AUTH_TOKEN = "<token>"
$env:MC_HOST = "localhost"
$env:MC_PORT = "25565"
$env:MC_VERSION = "1.20.4"
$env:MC_USERNAME = "ARIA"

npm start
```

## Variables

| Variable | Por defecto | Para qué |
|---|---|---|
| `ARIA_BACKEND_URL` | `http://127.0.0.1:8002` | Dónde vive el runtime |
| `ARIA_AUTH_TOKEN` | *(obligatorio)* | Token Bearer |
| `MC_HOST` | `localhost` | Servidor de Minecraft |
| `MC_PORT` | `25565` | Puerto del servidor |
| `MC_VERSION` | `1.20.4` | Versión del protocolo |
| `MC_USERNAME` | `ARIA` | Nombre del bot |
| `MC_FOLLOW` | `1` | Si ARIA sigue al jugador por su cuenta |

## Comandos que ARIA puede dar

| Comando | Qué hace |
|---|---|
| `follow` | Sigue al jugador más cercano |
| `come` | Va hasta él |
| `stop` | Se queda quieta |
| `look` | Lo mira |
| `say` | Dice un texto concreto |

La lista es cerrada: el runtime no acepta comandos inventados (ver
`Action::GAME_COMMANDS` en `v6/axum-poc/src/autonomy.rs`).

## Requisitos

* Node.js 20 o superior.
* Un servidor de Minecraft accesible (el bot entra en modo `offline`:
  sirve para pruebas locales, no para cuentas premium).
