import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  channelAudience,
  channelIsListening,
  channelKindIcon,
  channelKindLabel,
  emotionLabel,
  emotionStrength,
  formatTraitChange,
  messageIsAddressed,
  messageIsAnswered,
  traitChangeIsVisible,
  traitLabel,
  worldCapabilityCount,
  worldKindIcon,
  worldKindLabel,
  worldStatusLabel,
} from '../src/lib/embodiment.ts'

test('cada tipo de mundo tiene su etiqueta y su icono', () => {
  assert.equal(worldKindLabel('escritorio'), 'Escritorio')
  assert.equal(worldKindLabel('avatar'), 'Avatar')
  assert.equal(worldKindLabel('inventado'), 'inventado')
  assert.notEqual(worldKindIcon('juego'), worldKindIcon('chat'))
})

test('el estado de un mundo se lee sin backend', () => {
  assert.equal(worldStatusLabel({ connected: true, status: 'conectado' }), 'Conectado')
  assert.equal(worldStatusLabel({ connected: false, status: 'listo' }), 'Preparado')
  assert.equal(worldStatusLabel({ connected: false, status: 'esperando puente' }), 'esperando puente')
})

test('las capacidades de un mundo se cuentan', () => {
  assert.equal(worldCapabilityCount({ capabilities: ['chat.say', 'move'] }), 2)
  assert.equal(worldCapabilityCount({}), 0)
})

test('los canales se identifican por su plataforma', () => {
  assert.equal(channelKindLabel('twitch'), 'Twitch')
  assert.equal(channelKindLabel('discord'), 'Discord')
  assert.equal(channelKindLabel('rara'), 'rara')
  assert.notEqual(channelKindIcon('twitch'), channelKindIcon('youtube'))
})

test('la audiencia se cuenta en mensajes', () => {
  assert.equal(channelAudience({ messages: 0 }), 'nadie ha hablado todavía')
  assert.equal(channelAudience({ messages: 1 }), '1 mensaje')
  assert.equal(channelAudience({ messages: 12 }), '12 mensajes')
})

test('un canal sólo escucha si está encendido y conectado', () => {
  assert.equal(channelIsListening({ enabled: true, connected: true }), true)
  assert.equal(channelIsListening({ enabled: true, connected: false }), false)
  assert.equal(channelIsListening({ enabled: false, connected: true }), false)
})

test('las emociones tienen etiqueta y fuerza legible', () => {
  assert.equal(emotionLabel('alegria'), 'Alegría')
  assert.equal(emotionLabel('determinacion'), 'Determinación')
  assert.equal(emotionStrength(0.8), 'muy marcada')
  assert.equal(emotionStrength(0.4), 'notable')
  assert.equal(emotionStrength(0.2), 'sutil')
  assert.equal(emotionStrength(0.05), 'apenas')
  assert.equal(emotionStrength(Number.NaN), '—')
})

test('los rasgos se nombran y sus cambios se formatean con signo', () => {
  assert.equal(traitLabel('calidez'), 'Calidez')
  assert.equal(traitLabel('raro'), 'raro')
  assert.equal(formatTraitChange(0.05), '+0.05')
  assert.equal(formatTraitChange(-0.12), '-0.12')
  assert.equal(formatTraitChange(Number.NaN), '—')
})

test('los cambios de rasgo invisibles no se enseñan', () => {
  assert.equal(traitChangeIsVisible(0.05), true)
  assert.equal(traitChangeIsVisible(-0.12), true)
  assert.equal(traitChangeIsVisible(0.001), false)
  assert.equal(traitChangeIsVisible(Number.NaN), false)
})

test('se distingue lo que va dirigido a ARIA de lo que ya contestó', () => {
  assert.equal(messageIsAddressed({ addressed: true }), true)
  assert.equal(messageIsAddressed({ addressed: false }), false)
  assert.equal(messageIsAnswered({ replied: true }), true)
  assert.equal(messageIsAnswered({ replied: false }), false)
})
