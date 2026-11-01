import { test } from 'node:test'
import assert from 'node:assert/strict'
import { VoiceGate, pickVoice, DEFAULT_VOICE_GATE } from '../src/lib/voiceGate.ts'

test('una frase empieza cuando el nivel cruza el umbral de voz', () => {
  const gate = new VoiceGate()
  assert.equal(gate.update(0.01, 0), null)
  const event = gate.update(0.2, 100)
  assert.deepEqual(event, { type: 'speech-start' })
  assert.equal(gate.isSpeaking, true)
})

test('la frase se cierra tras el silencio suficiente', () => {
  const gate = new VoiceGate()
  gate.update(0.3, 0)
  assert.equal(gate.update(0.3, 400), null)
  assert.deepEqual(gate.update(0, 400 + DEFAULT_VOICE_GATE.silenceMs), {
    type: 'speech-end',
    reason: 'silence',
  })
  assert.equal(gate.isSpeaking, false)
})

test('un chasquido demasiado corto no cuenta como frase', () => {
  const gate = new VoiceGate()
  gate.update(0.3, 0)
  // 100 ms de voz y luego silencio: la frase es demasiado corta.
  assert.equal(gate.update(0, 100), null)
  const event = gate.update(0, 100 + DEFAULT_VOICE_GATE.silenceMs)
  assert.deepEqual(event, { type: 'speech-end', reason: 'too-short' })
})

test('la frase se corta si se pasa del máximo', () => {
  const gate = new VoiceGate({ maxUtteranceMs: 1000 })
  gate.update(0.3, 0)
  const event = gate.update(0.3, 1200)
  assert.deepEqual(event, { type: 'speech-end', reason: 'max-duration' })
})

test('la voz reciente mantiene la frase abierta', () => {
  const gate = new VoiceGate()
  gate.update(0.3, 0)
  // Habla a ratos: cada ráfaga renueva el reloj de silencio.
  gate.update(0.3, 500)
  gate.update(0, 1000)
  assert.equal(gate.update(0.3, 1100), null, 'la frase no debe cerrarse')
  assert.equal(gate.isSpeaking, true)
})

test('reset corta la frase en curso', () => {
  const gate = new VoiceGate()
  gate.update(0.3, 0)
  gate.reset()
  assert.equal(gate.isSpeaking, false)
  // Tras el reset, la voz siguiente abre una frase nueva.
  assert.deepEqual(gate.update(0.3, 100), { type: 'speech-start' })
})

test('el umbral de silencio es más bajo que el de voz', () => {
  const gate = new VoiceGate()
  // Un nivel entre los dos umbrales no cierra la frase: es histéresis.
  gate.update(0.3, 0)
  assert.equal(gate.update(0.03, 100), null)
  assert.equal(gate.isSpeaking, true)
})

test('la voz de síntesis se elige por idioma exacto o por prefijo', () => {
  const voices = [
    { lang: 'en-US', name: 'Alex' },
    { lang: 'es-ES', name: 'Monica' },
    { lang: 'es-MX', name: 'Paulina' },
  ]
  assert.equal(pickVoice(voices, 'es-ES')?.name, 'Monica')
  assert.equal(pickVoice(voices, 'es-AR')?.name, 'Monica')
  assert.equal(pickVoice([{ lang: 'en-US', name: 'Alex' }], 'es-ES')?.name, 'Alex')
  assert.equal(pickVoice([], 'es-ES'), null)
})
