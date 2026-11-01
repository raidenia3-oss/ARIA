import { test } from 'node:test'
import assert from 'node:assert/strict'
import { classifyGesture, extendedFingers, handMotion, type HandPoint } from '../src/lib/gestures.ts'

/**
 * Construye una malla de mano de 21 puntos con la forma pedida.
 *
 * Las coordenadas son sintéticas pero respetan la anatomía que usa
 * `classifyGesture`: la muñeca en el centro, y cada dedo con su articulación
 * media (PIP) más cerca de la muñeca que su punta cuando está doblado.
 */
function hand(options: {
  index?: boolean
  middle?: boolean
  ring?: boolean
  pinky?: boolean
  thumbUp?: boolean
  thumbOut?: boolean
}): HandPoint[] {
  const points: HandPoint[] = new Array(21)
  const wrist = { x: 0.5, y: 0.9, z: 0 }
  points[0] = wrist
  // Pulgar: punta (4), IP (3), MCP (2).
  points[1] = { x: 0.42, y: 0.82, z: 0 }
  points[2] = { x: 0.38, y: 0.76, z: 0 }
  points[3] = options.thumbOut
    ? { x: 0.3, y: 0.68, z: 0 }
    : { x: 0.36, y: 0.7, z: 0 }
  points[4] = options.thumbUp
    ? { x: 0.44, y: 0.5, z: 0 }
    : options.thumbOut
      ? { x: 0.22, y: 0.62, z: 0 }
      : { x: 0.33, y: 0.66, z: 0 }

  const fingers: Array<[number, number, number, number]> = [
    [8, 7, 6, 5], // índice: punta, dip, pip, mcp
    [12, 11, 10, 9],
    [16, 15, 14, 13],
    [20, 19, 18, 17],
  ]
  const extended = [options.index, options.middle, options.ring, options.pinky]

  fingers.forEach(([tip, dip, pip, mcp], i) => {
    const x = 0.42 + i * 0.055
    const isUp = extended[i]
    // El nudillo está siempre a la misma altura; la punta sube si el dedo
    // está extendido y se queda cerca del nudillo si está doblado.
    const baseY = 0.78 - i * 0.02
    points[mcp] = { x, y: baseY, z: 0 }
    points[pip] = { x, y: isUp ? baseY - 0.14 : baseY - 0.03, z: 0 }
    points[dip] = { x, y: isUp ? baseY - 0.2 : baseY - 0.04, z: 0 }
    points[tip] = { x, y: isUp ? baseY - 0.26 : baseY - 0.05, z: 0 }
  })

  return points
}

test('una mano con los cinco dedos extendidos es palma abierta', () => {
  const points = hand({ index: true, middle: true, ring: true, pinky: true })
  assert.equal(classifyGesture(points), 'open_palm')
})

test('una mano con todos los dedos recogidos es puño', () => {
  const points = hand({})
  assert.equal(classifyGesture(points), 'fist')
})

test('sólo el índice extendido es el gesto índice', () => {
  const points = hand({ index: true })
  assert.equal(classifyGesture(points), 'index')
})

test('índice y medio extendidos es el gesto paz', () => {
  const points = hand({ index: true, middle: true })
  assert.equal(classifyGesture(points), 'peace')
})

test('pulgar arriba con los demás recogidos es pulgar arriba', () => {
  const points = hand({ thumbUp: true })
  assert.equal(classifyGesture(points), 'thumbs_up')
})

test('una malla incompleta no produce ningún gesto', () => {
  assert.equal(classifyGesture(null), 'none')
  assert.equal(classifyGesture(undefined), 'none')
  assert.equal(classifyGesture([{ x: 0, y: 0, z: 0 }]), 'none')
})

test('extendedFingers informa de cada dedo por separado', () => {
  const fingers = extendedFingers(hand({ index: true, middle: true }))
  assert.equal(fingers.length, 4)
  assert.equal(fingers[0], true, 'índice extendido')
  assert.equal(fingers[1], true, 'medio extendido')
  assert.equal(fingers[2], false, 'anular recogido')
  assert.equal(fingers[3], false, 'meñique recogido')
})

test('handMotion mide el desplazamiento y satura en 1 sin referencia', () => {
  const a = hand({ index: true })
  const b = a.map((p) => ({ ...p, x: p.x + 0.1 }))
  assert.ok(handMotion(a, b) > 0, 'hay movimiento')
  assert.equal(handMotion(null, b), 1, 'sin referencia el movimiento es máximo')
  assert.equal(handMotion(a, a), 0, 'sin movimiento')
})

test('la clasificación es determinista', () => {
  const points = hand({ index: true, middle: true })
  assert.equal(classifyGesture(points), classifyGesture(points))
})
