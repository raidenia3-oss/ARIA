import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  emitGesture,
  emitGestureAction,
  onGestureAction,
  GESTURE_ACTION_BY_GESTURE,
} from '../src/lib/gestureActions.ts'

test('cada gesto conocido tiene una acción', () => {
  assert.equal(GESTURE_ACTION_BY_GESTURE.open_palm, 'pausar')
  assert.equal(GESTURE_ACTION_BY_GESTURE.peace, 'siguiente')
  assert.equal(GESTURE_ACTION_BY_GESTURE.thumbs_up, 'aprobar')
  assert.equal(GESTURE_ACTION_BY_GESTURE.fist, 'detener')
  assert.equal(GESTURE_ACTION_BY_GESTURE.index, 'ejecutar')
})

test('un suscriptor recibe la acción emitida', () => {
  const received: string[] = []
  const off = onGestureAction((event) => received.push(event.action))
  emitGestureAction('detener')
  off()
  emitGestureAction('detener')
  assert.deepEqual(received, ['detener'], 'tras cancelar la suscripción no debe llegar nada')
})

test('emitir un gesto traduce a su acción', () => {
  const received: string[] = []
  const off = onGestureAction((event) => received.push(event.action))
  assert.equal(emitGesture('index'), true)
  assert.equal(emitGesture('none'), false)
  off()
  assert.deepEqual(received, ['ejecutar'])
})

test('un suscriptor que falla no rompe a los demás', () => {
  const received: string[] = []
  const offBad = onGestureAction(() => {
    throw new Error('boom')
  })
  const offGood = onGestureAction((event) => received.push(event.action))
  emitGestureAction('siguiente')
  offBad()
  offGood()
  assert.deepEqual(received, ['siguiente'])
})
