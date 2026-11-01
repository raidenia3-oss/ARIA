/**
 * Prueba del protocolo entre un escenario y el runtime de ARIA.
 *
 * Se habla con el backend de verdad: el evento que informa el escenario
 * tiene que aparecer en la lista de eventos, y lo que ARIA dice tiene que
 * llegar por el flujo en vivo.
 *
 * Uso:  node src/runtime.test.mjs
 * Requiere el backend en marcha y ARIA_AUTH_TOKEN en el entorno.
 */

import assert from 'node:assert/strict'
import test from 'node:test'
import { createRuntime } from './runtime.mjs'

const TOKEN = process.env.ARIA_AUTH_TOKEN ?? ''
const BASE_URL = process.env.ARIA_BACKEND_URL ?? 'http://127.0.0.1:8002'

test('el runtime existe y la autenticación vale', { skip: !TOKEN }, async () => {
  const runtime = createRuntime({ baseUrl: BASE_URL, token: TOKEN, source: 'prueba' })
  const health = await runtime.ariaFetch('/health')
  assert.equal(health.status, 'ok')
})

test('un evento del escenario llega al runtime', { skip: !TOKEN }, async () => {
  const runtime = createRuntime({ baseUrl: BASE_URL, token: TOKEN, source: 'prueba' })
  const marker = `evento de prueba ${Date.now()}`
  const response = await runtime.report('juego', marker, { username: 'prueba' })
  assert.equal(response.status, 'ok')
  assert.equal(response.event.text, marker)
  assert.equal(response.event.source, 'prueba')

  const events = await runtime.ariaFetch('/api/autonomy/events?limit=5')
  assert.ok(
    events.events.some((event) => event.text === marker),
    'el evento tiene que estar en la lista',
  )
})

test('lo que ARIA dice llega por el flujo en vivo', { skip: !TOKEN }, async () => {
  const received = []
  const runtime = createRuntime({
    baseUrl: BASE_URL,
    token: TOKEN,
    source: 'prueba',
    onEvent: (event) => received.push(event),
  })

  let stop = false
  const listening = runtime.listen({
    shouldStop: () => stop,
    retryMs: 500,
  })

  // Se espera a que el flujo esté de pie antes de hablar.
  await new Promise((resolve) => setTimeout(resolve, 600))
  await runtime.ariaFetch('/api/autonomy/speak', {
    method: 'POST',
    body: JSON.stringify({ topic: 'prueba del escenario' }),
  })

  const deadline = Date.now() + 60000
  while (Date.now() < deadline && received.length === 0) {
    await new Promise((resolve) => setTimeout(resolve, 250))
  }

  stop = true
  await listening.catch(() => undefined)

  assert.ok(received.length > 0, 'no llegó ningún evento por el flujo')
  assert.ok(
    received.some((event) => event.kind === 'habla' && event.text),
    'tiene que llegar lo que ARIA dice',
  )
})
