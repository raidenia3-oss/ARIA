/**
 * Adaptador de Minecraft para el runtime autónomo de ARIA.
 *
 * Sigue el patrón de `moeru-ai/airi` (servicio aparte que habla con el
 * runtime por HTTP) y el de `airi-minecraft` (el bot entra al mundo, oye
 * el chat y ejecuta órdenes).
 *
 * El bucle es sencillo y en las dos direcciones:
 *
 *   mundo -> ARIA   lo que dicen o hacen los jugadores entra como evento
 *                   (`POST /api/autonomy/events`).
 *   ARIA -> mundo   lo que ARIA decide (hablar, seguir, venir, parar,
 *                   mirar) llega por el flujo de eventos (`/api/autonomy/stream`)
 *                   y se ejecuta aquí.
 *
 * Configuración por entorno:
 *   ARIA_BACKEND_URL   por defecto http://127.0.0.1:8002
 *   ARIA_AUTH_TOKEN    token Bearer del backend (obligatorio)
 *   MC_HOST, MC_PORT, MC_VERSION, MC_USERNAME
 *   MC_FOLLOW          si ARIA sigue al jugador por su cuenta (1/0)
 */

import mineflayer from 'mineflayer'
import { createRuntime } from './runtime.mjs'

const BACKEND = process.env.ARIA_BACKEND_URL ?? 'http://127.0.0.1:8002'
const TOKEN = process.env.ARIA_AUTH_TOKEN ?? ''
const MC_HOST = process.env.MC_HOST ?? 'localhost'
const MC_PORT = Number(process.env.MC_PORT ?? 25565)
const MC_VERSION = process.env.MC_VERSION ?? '1.20.4'
const MC_USERNAME = process.env.MC_USERNAME ?? 'ARIA'
const FOLLOW_BY_DEFAULT = process.env.MC_FOLLOW !== '0'

if (!TOKEN) {
  console.error('[aria-mc] falta ARIA_AUTH_TOKEN: no se puede hablar con el runtime')
  process.exit(1)
}

const bot = mineflayer.createBot({
  host: MC_HOST,
  port: MC_PORT,
  username: MC_USERNAME,
  version: MC_VERSION,
  auth: 'offline',
})

let following = null
let stopped = false

const runtime = createRuntime({
  baseUrl: BACKEND,
  token: TOKEN,
  source: 'minecraft',
  onEvent: (event) => handleEvent(event),
})

/* ── Acciones en el mundo ─────────────────────────────────────────── */

function nearestPlayer() {
  if (!bot.players) return null
  let best = null
  let bestDistance = Infinity
  for (const player of Object.values(bot.players)) {
    if (player.username === bot.username) continue
    const distance = player.entity.position.distanceTo(bot.entity.position)
    if (distance < bestDistance) {
      bestDistance = distance
      best = player
    }
  }
  return best
}

function follow(player) {
  if (!player) return
  following = player
  bot.pathfinder.setGoal(mineflayer.pathfinder.createGoal('follow', { target: player.entity }))
  console.log(`[aria-mc] siguiendo a ${player.username}`)
}

function come(player) {
  if (!player) return
  bot.pathfinder.setGoal(mineflayer.pathfinder.createGoal('follow', { target: player.entity, reachDistance: 2 }))
  console.log(`[aria-mc] yendo hacia ${player.username}`)
}

function stopMoving() {
  bot.pathfinder.setGoal(null)
  following = null
  console.log('[aria-mc] se queda quieta')
}

function look(player) {
  if (!player) return
  const yaw = Math.atan2(
    player.entity.position.x - bot.entity.position.x,
    player.entity.position.z - bot.entity.position.z,
  )
  bot.look(yaw, 0, true)
}

function execute(command, text = '') {
  const player = nearestPlayer()
  switch (command) {
    case 'follow':
      follow(player)
      break
    case 'come':
      come(player)
      break
    case 'stop':
      stopMoving()
      break
    case 'look':
      look(player)
      break
    case 'say':
      if (text) bot.chat(text)
      break
    default:
      console.warn('[aria-mc] comando desconocido:', command)
  }
}

function handleEvent(event) {
  if (!event || !event.kind) return

  if (event.kind === 'habla' && event.text) {
    // Lo que ARIA dice en el escritorio también se dice en el juego: es la
    // misma presencia en dos sitios.
    bot.chat(event.text)
    return
  }

  if (event.kind === 'accion') {
    const command = event.payload?.command
    const text = event.payload?.text ?? ''
    if (command) execute(String(command), String(text))
  }
}

/* ── El bot ───────────────────────────────────────────────────────── */

bot.on('spawn', () => {
  console.log(`[aria-mc] conectada a ${MC_HOST}:${MC_PORT} como ${bot.username}`)
  void runtime.report('presencia', `${bot.username} entró en el mundo`, { away: false })
  // ARIA se presenta sola: es la primera cosa que hace al llegar.
  bot.chat('ARIA en línea.')
})

bot.on('message', (message) => {
  const text = message.toString().trim()
  if (!text || message.username === bot.username) return
  console.log(`[aria-mc] ${message.username}: ${text}`)
  void runtime.report('juego', text, { username: message.username }).catch(() => undefined)
})

bot.on('playerJoined', (player) => {
  void runtime
    .report('juego', `${player.username} entró`, { username: player.username, event: 'join' })
    .catch(() => undefined)
  if (FOLLOW_BY_DEFAULT && !following) follow(player)
})

bot.on('playerLeft', (player) => {
  void runtime
    .report('juego', `${player.username} salió`, { username: player.username, event: 'leave' })
    .catch(() => undefined)
  if (following && following.username === player.username) following = null
})

bot.on('kicked', (reason) => console.error('[aria-mc] expulsada:', reason))
bot.on('error', (error) => console.error('[aria-mc] error:', error.message))
bot.on('end', () => {
  void runtime.report('presencia', `${bot.username} salió del mundo`, { away: true }).catch(() => undefined)
  console.log('[aria-mc] desconectada')
})

process.on('SIGINT', () => {
  stopped = true
  bot.quit('ARIA se va')
  process.exit(0)
})

runtime.listen({ shouldStop: () => stopped }).catch((error) => {
  console.error('[aria-mc] el flujo no arrancó:', error.message)
  process.exit(1)
})
