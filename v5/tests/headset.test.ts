import { test } from 'node:test'
import assert from 'node:assert/strict'
import { cleanDeviceLabel, looksLikeHeadset } from '../src/lib/headset.ts'

test('detecta audífonos por su etiqueta en inglés', () => {
  assert.equal(looksLikeHeadset('Headset Microphone (Jabra EVO)'), true)
  assert.equal(looksLikeHeadset('Headphones'), true)
  assert.equal(looksLikeHeadset('AirPods Pro'), true)
  assert.equal(looksLikeHeadset('Earbuds (Galaxy Buds)'), true)
})

test('detecta audífonos por su etiqueta en español', () => {
  assert.equal(looksLikeHeadset('Auriculares estéreo'), true)
  assert.equal(looksLikeHeadset('Auriculares (Jabra EVO)'), true)
  assert.equal(looksLikeHeadset('Micrófono de casco Gaming'), true)
})

test('no confunde el micrófono integrado con un auricular', () => {
  assert.equal(looksLikeHeadset('Microphone Array (Realtek)'), false)
  assert.equal(looksLikeHeadset('Micrófono integrado'), false)
  assert.equal(looksLikeHeadset('Digital Audio Interface'), false)
})

test('una etiqueta vacía no es un auricular', () => {
  assert.equal(looksLikeHeadset(''), false)
})

test('la limpieza quita el número de puerto de Windows', () => {
  assert.equal(cleanDeviceLabel('2- Headset Microphone'), 'Headset Microphone')
  assert.equal(cleanDeviceLabel('1- Micrófono integrado'), 'Micrófono integrado')
  assert.equal(cleanDeviceLabel('Auriculares'), 'Auriculares')
})
