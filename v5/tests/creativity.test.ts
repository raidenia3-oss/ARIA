import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  canCreateSkill,
  canForge,
  canProbe,
  effectiveScore,
  ideaStatusLabel,
  integrationKindLabel,
  originLabel,
  percent,
  sortIdeas,
  statusTone,
  weightTone,
} from '../src/lib/creativity.ts'
import type { CreativityIdea, CreativityIntegration } from '../src/lib/ariaBackend.ts'

function idea(overrides: Partial<CreativityIdea> = {}): CreativityIdea {
  return {
    id: 'idea_001',
    title: 'Idea',
    summary: 'resumen',
    detail: 'detalle',
    theme: 'voz',
    origin: 'idea',
    novelty: 0.5,
    feasibility: 0.5,
    impact: 0.5,
    score: 0.5,
    raw_score: 0.5,
    status: 'new',
    note: null,
    created_at: '2026-10-19T00:00:00Z',
    skill_id: null,
    ...overrides,
  }
}

function integration(overrides: Partial<CreativityIntegration> = {}): CreativityIntegration {
  return {
    id: 'int_001',
    name: 'nmap',
    kind: 'herramienta',
    target: 'nmap -sV',
    description: 'escanea puertos',
    enabled: true,
    created_at: '2026-10-19T00:00:00Z',
    calls: 0,
    ...overrides,
  }
}

test('el origen de una idea tiene etiqueta legible', () => {
  assert.equal(originLabel('solucion'), 'solución')
  assert.equal(originLabel('mejora'), 'mejora')
  assert.equal(originLabel('idea'), 'idea')
  assert.equal(originLabel('otro'), 'otro')
})

test('el tipo de integración tiene etiqueta legible', () => {
  assert.equal(integrationKindLabel('herramienta'), 'herramienta')
  assert.equal(integrationKindLabel('servicio'), 'servicio')
  assert.equal(integrationKindLabel('módulo'), 'módulo')
  assert.equal(integrationKindLabel(''), 'integración')
})

test('sólo los servicios HTTP se pueden probar', () => {
  assert.equal(canProbe(integration({ target: 'http://localhost:11434' })), true)
  assert.equal(canProbe(integration({ target: 'https://example.test/api' })), true)
  assert.equal(canProbe(integration({ target: 'nmap -sV' })), false)
  assert.equal(canProbe(integration({ target: '' })), false)
})

test('una skill necesita un objetivo con contenido', () => {
  assert.equal(canCreateSkill('resumir la voz'), true)
  assert.equal(canCreateSkill('   '), false)
  assert.equal(canCreateSkill(''), false)
})

test('una idea sólo se forja si está aceptada y sin skill', () => {
  assert.equal(canForge(idea({ status: 'accepted' })), true)
  assert.equal(canForge(idea({ status: 'new' })), false)
  assert.equal(canForge(idea({ status: 'accepted', skill_id: 'gen_001' })), false)
})

test('el tema aprendido manda en el orden de las ideas', () => {
  const first = idea({ id: 'a', title: 'A', score: 0.6, raw_score: 0.6 })
  const second = idea({ id: 'b', title: 'B', score: 0.6, raw_score: 0.6, theme: 'memoria' })
  const ordered = sortIdeas([first, second], [{ theme: 'voz', weight: 0.8 }])
  assert.equal(ordered[0].id, 'a')
})

test('el porcentaje nunca se sale del rango', () => {
  assert.equal(percent(0.5), 50)
  assert.equal(percent(1.5), 100)
  assert.equal(percent(-1), 0)
  assert.equal(percent(Number.NaN), 0)
})

test('sin puntuación del servidor, el sesgo del tema se aplica en cliente', () => {
  // El servidor manda `score` ya sesgado; si no llega, la UI lo calcula.
  const base = idea({ score: 0, raw_score: 0.5 })
  const withoutProfile = effectiveScore(base)
  const withProfile = effectiveScore(base, [{ theme: 'voz', weight: 0.5 }])
  assert.ok(withProfile > withoutProfile)
  assert.ok(withProfile <= 1)
})

test('la puntuación que trae el servidor se respeta tal cual', () => {
  const base = idea({ score: 0.72, raw_score: 0.5 })
  assert.equal(effectiveScore(base), 0.72)
})

test('los estados y los tonos tienen etiqueta', () => {
  assert.equal(ideaStatusLabel('accepted'), 'Aceptada')
  assert.equal(statusTone('rejected'), 'bad')
  assert.equal(statusTone('built'), 'good')
  assert.equal(weightTone(0.6), 'like')
  assert.equal(weightTone(-0.6), 'dislike')
  assert.equal(weightTone(0), 'neutral')
})
