import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  averageDescriptors,
  cosineSimilarity,
  faceDescriptor,
  identityVerdict,
  IDENTITY_THRESHOLD,
  type FacePoint,
} from '../src/lib/identity.ts'

/** Malla facial sintética de 468 puntos, con la forma de una cara. */
function faceMesh(scale = 1, offsetX = 0): FacePoint[] {
  const points: FacePoint[] = new Array(468)
  for (let i = 0; i < 468; i++) {
    const angle = (i / 468) * Math.PI * 2
    points[i] = {
      x: 0.5 + Math.cos(angle) * 0.2 * scale + offsetX,
      y: 0.5 + Math.sin(angle) * 0.28 * scale,
      z: Math.sin(angle * 3) * 0.05 * scale,
    }
  }
  // Las comisuras de los ojos mandan en la normalización.
  points[33] = { x: 0.42 * scale + offsetX + 0.5, y: 0.46, z: 0 }
  points[263] = { x: 0.58 * scale + offsetX + 0.5, y: 0.46, z: 0 }
  return points
}

test('el descriptor tiene longitud de unidad', () => {
  const descriptor = faceDescriptor(faceMesh())
  assert.ok(descriptor, 'el descriptor se construye')
  const norm = Math.sqrt(descriptor.reduce((acc, v) => acc + v * v, 0))
  assert.ok(Math.abs(norm - 1) < 1e-6, `norma = ${norm}`)
})

test('una malla demasiado corta no produce descriptor', () => {
  assert.equal(faceDescriptor([{ x: 0, y: 0, z: 0 }]), null)
  assert.equal(faceDescriptor([]), null)
})

test('una malla colapsada no produce descriptor', () => {
  const flat = new Array(468).fill(0).map(() => ({ x: 0.5, y: 0.5, z: 0 }))
  assert.equal(faceDescriptor(flat), null)
})

test('el descriptor es invariante a la escala y al desplazamiento', () => {
  const a = faceDescriptor(faceMesh(1, 0))
  const b = faceDescriptor(faceMesh(2, 0.1))
  assert.ok(a && b)
  assert.ok(
    cosineSimilarity(a, b) > 0.999,
    `similitud = ${cosineSimilarity(a, b)}`,
  )
})

test('el mismo rostro da similitud 1', () => {
  const a = faceDescriptor(faceMesh())
  const b = faceDescriptor(faceMesh())
  assert.ok(a && b)
  assert.ok(cosineSimilarity(a, b) > 0.999)
})

test('rostros con distinta forma tienen menos similitud', () => {
  const a = faceDescriptor(faceMesh(1, 0))
  const different = faceMesh(1, 0).map((p, i) => ({
    x: p.x + (i % 7 === 0 ? 0.12 : 0),
    y: p.y + (i % 5 === 0 ? 0.1 : 0),
    z: p.z,
  }))
  const b = faceDescriptor(different)
  assert.ok(a && b)
  assert.ok(cosineSimilarity(a, b) < 0.999, 'no son idénticos')
})

test('descriptores de distinta longitud no se comparan', () => {
  assert.equal(cosineSimilarity([1, 0], [1, 0, 0]), 0)
  assert.equal(cosineSimilarity([], []), 0)
})

test('el promedio de descriptores similar es el mismo descriptor', () => {
  const a = faceDescriptor(faceMesh())
  const b = faceDescriptor(faceMesh())
  assert.ok(a && b)
  const averaged = averageDescriptors([a, b])
  assert.ok(averaged)
  assert.ok(cosineSimilarity(averaged, a) > 0.999)
})

test('el promedio ignora descriptores de distinta longitud', () => {
  const a = faceDescriptor(faceMesh())
  assert.ok(a)
  assert.equal(averageDescriptors([a, [1, 2, 3]]), null)
  assert.equal(averageDescriptors([]), null)
})

test('el veredicto distingue desconocido, probable y confirmado', () => {
  assert.equal(identityVerdict(0.1), 'desconocido')
  assert.equal(identityVerdict(IDENTITY_THRESHOLD), 'probable')
  assert.equal(identityVerdict(0.95), 'confirmado')
})
