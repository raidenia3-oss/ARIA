#!/usr/bin/env node
/**
 * Puente de Minecraft de ARIA (mineflayer).
 *
 * Es el otro lado del protocolo de mundos del backend: se conecta a un
 * servidor de Minecraft, publica el estado del jugador (dónde está, cómo
 * está, qué lleva, qué tiene cerca) y ejecuta las acciones que ARIA le
 * pide (moverse, mirar, hablar, cavar, fabricar).
 *
 * Habla con `scripts/aria_world_bridge.py` por stdin/stdout con líneas
 * JSON:
 *
 *   salida: {"context": {...}}         -> estado del mundo
 *   entrada: {"action": "move", "args": {...}}
 *
 * Instalación:
 *
 *   npm install mineflayer
 *
 * Configuración (entorno o argumentos):
 *
 *   ARIA_MC_HOST=127.0.0.1 ARIA_MC_PORT=25565 ARIA_MC_USER=ARIA
 *   ARIA_MC_VERSION=1.20.4 node scripts/minecraft_bridge.mjs
 *
 * Si no hay `mineflayer` instalado, el script lo dice y sale: el puente de
 * Python seguirá funcionando con el resto de mundos.
 */

import process from 'node:process'

const HOST = process.env.ARIA_MC_HOST || '127.0.0.1'
const PORT = Number(process.env.ARIA_MC_PORT || 25565)
const USERNAME = process.env.ARIA_MC_USER || 'ARIA'
const VERSION = process.env.ARIA_MC_VERSION || '1.20.4'

let mineflayer = null
try {
  mineflayer = (await import('mineflayer')).default
} catch (error) {
  process.stdout.write(
    JSON.stringify({
      log: 'mineflayer no está instalado: ejecuta "npm install mineflayer" en la raíz del repo',
    }) + '\n'
  )
  process.exit(0)
}

const bot = mineflayer.createBot({
  host: HOST,
  port: PORT,
  username: USERNAME,
  version: VERSION,
  auth: 'offline',
})

function nearbyBlocks() {
  const found = []
  if (!bot.blockAt) return found
  const position = bot.entity?.position
  if (!position) return found
  const radius = 3
  for (let dx = -radius; dx <= radius; dx += 1) {
    for (let dy = -radius; dy <= radius; dy += 1) {
      for (let dz = -radius; dz <= radius; dz += 1) {
        const block = bot.blockAt(
          Math.floor(position.x) + dx,
          Math.floor(position.y) + dy,
          Math.floor(position.z) + dz
        )
        if (block && block.name && !found.includes(block.name)) {
          found.push(block.name)
        }
      }
    }
  }
  return found.slice(0, 12)
}

function context() {
  const entity = bot.entity
  const position = entity?.position
  const health = entity?.health
  const inventory = bot.inventory
    ? bot.inventory.items().map((item) => item.name).slice(0, 12)
    : []
  return {
    pos: position
      ? {
          x: Math.round(position.x),
          y: Math.round(position.y),
          z: Math.round(position.z),
        }
      : null,
    vida: typeof health === 'number' ? health : null,
    comida: typeof entity?.food === 'number' ? entity.food : null,
    inventario: inventory,
    bloques_cercanos: nearbyBlocks(),
    jugadores_vivos: bot.players ? Object.keys(bot.players).length : 0,
    en_juego: true,
  }
}

function publish() {
  process.stdout.write(JSON.stringify({ context: context() }) + '\n')
}

bot.on('spawn', () => {
  process.stdout.write(JSON.stringify({ log: 'conectado al servidor de Minecraft' }) + '\n')
  publish()
})

bot.on('end', (reason) => {
  process.stdout.write(JSON.stringify({ log: `desconectado: ${reason}` }) + '\n')
})

bot.on('error', (error) => {
  process.stdout.write(JSON.stringify({ log: `error: ${error.message}` }) + '\n')
})

bot.on('chat', (username, message) => {
  process.stdout.write(
    JSON.stringify({ evento: { tipo: 'chat', autor: username, texto: message } }) + '\n'
  )
})

bot.on('message', (message) => {
  process.stdout.write(
    JSON.stringify({ evento: { tipo: 'mensaje', texto: String(message) } }) + '\n'
  )
})

let timer = setInterval(publish, 2000)

function act(action, args) {
  switch (action) {
    case 'chat.say':
    case 'say':
      bot.chat(String(args.text || ''))
      return 'escrito en el chat'
    case 'move': {
      const x = Number(args.x)
      const y = Number(args.y)
      const z = Number(args.z)
      if ([x, y, z].some((value) => Number.isNaN(value))) return 'coordenadas inválidas'
      bot.setControlState('forward', false)
      bot.setControlState('back', false)
      bot.setControlState('left', false)
      bot.setControlState('right', false)
      bot.setControlState('sprint', false)
      bot.setControlState('jump', false)
      bot.setControlState('forward', true)
      bot.setControlState('jump', true)
      bot.look(y - bot.entity.position.y, 0, true)
      return 'andando hacia el punto'
    }
    case 'look': {
      const x = Number(args.x)
      const y = Number(args.y)
      const z = Number(args.z)
      if ([x, y, z].some((value) => Number.isNaN(value))) return 'coordenadas inválidas'
      const position = bot.entity.position
      bot.look(y - position.y, x - position.x, true)
      return 'mirando'
    }
    case 'dig': {
      const block = bot.blockAt(bot.entity.position.offset(0, -1, 0))
      if (!block) return 'no hay bloque debajo'
      try {
        bot.dig(block)
        return `cavando ${block.name}`
      } catch (error) {
        return `no se pudo excavar: ${error.message}`
      }
    }
    case 'craft': {
      const item = String(args.item || '')
      if (!item) return 'falta el objeto'
      const itemDef = bot.registry?.items?.[item]
      if (!itemDef) return `no conozco el objeto ${item}`
      try {
        bot.recipesFor(itemDef.id, null, 1, bot.inventory).forEach((recipe) => {
          bot.craft(recipe, 1, itemDef.id)
        })
        return `fabricando ${item}`
      } catch (error) {
        return `no se pudo fabricar: ${error.message}`
      }
    }
    case 'observe':
      publish()
      return 'mirando alrededor'
    default:
      return `acción no soportada: ${action}`
  }
}

// Entrada: una acción por línea.
let buffer = ''
process.stdin.setEncoding('utf8')
process.stdin.on('data', (chunk) => {
  buffer += chunk
  let index = buffer.indexOf('\n')
  while (index !== -1) {
    const line = buffer.slice(0, index).trim()
    buffer = buffer.slice(index + 1)
    if (line) {
      try {
        const payload = JSON.parse(line)
        const outcome = act(String(payload.action || ''), payload.args || {})
        process.stdout.write(JSON.stringify({ resultado: outcome }) + '\n')
      } catch (error) {
        process.stdout.write(JSON.stringify({ resultado: `error: ${error.message}` }) + '\n')
      }
    }
    index = buffer.indexOf('\n')
  }
})

process.on('SIGINT', () => {
  clearInterval(timer)
  bot.quit()
  process.exit(0)
})
