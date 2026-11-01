import test from 'node:test'
import assert from 'node:assert/strict'

import {
  DRIVE_HINTS,
  driveLabel,
  driveLevel,
  episodeLabel,
  eventLabel,
  expressionLabel,
  initiativeStateIcon,
  initiativeStateLabel,
  lessonKindIcon,
  lessonKindLabel,
  modeLabel,
  pendingInitiatives,
  perceptionSummary,
  quirksToText,
  sourceIcon,
  sourceLabel,
  strongestDrive,
  textToQuirks,
  timeAgo,
  topInitiative,
  topLessons,
  urgencyLabel,
  worldSilenceLabel,
  worldStateLabel,
} from '../src/lib/autonomy.ts'
import type {
  AutonomyEpisode,
  AutonomyEvent,
  AutonomyInitiative,
  AutonomyLesson,
  PerceptionSnapshot,
  PerceptionWorld,
} from '../src/lib/ariaBackend.ts'

test('cada pulsión tiene su etiqueta y su explicación', () => {
  assert.equal(driveLabel('curiosidad'), 'Curiosidad')
  assert.equal(driveLabel('energia'), 'Energía')
  assert.equal(driveLabel('social'), 'Social')
  assert.equal(driveLabel('dominio'), 'Dominio')
  assert.equal(driveLabel('orden'), 'Orden')
  // Una pulsión que no se conoce se muestra tal cual: no se inventa.
  assert.equal(driveLabel('inventada'), 'inventada')
  assert.ok(DRIVE_HINTS.curiosidad.length > 0)
})

test('el nivel de una pulsión es 0 si no está', () => {
  assert.equal(driveLevel({ social: 0.4 }, 'social'), 0.4)
  assert.equal(driveLevel({ social: 0.4 }, 'energia'), 0)
  assert.equal(driveLevel(undefined, 'social'), 0)
  assert.equal(driveLevel({ social: Number.NaN }, 'social'), 0)
})

test('los modos tienen nombre legible y explicación', () => {
  assert.equal(modeLabel('activa'), 'Activa')
  assert.equal(modeLabel('tranquila'), 'Tranquila')
  assert.equal(modeLabel('dormida'), 'Dormida')
  assert.equal(modeLabel('raro'), 'raro')
})

test('la urgencia depende del umbral', () => {
  assert.equal(urgencyLabel(0.9, 0.55), 'impaciente')
  assert.equal(urgencyLabel(0.6, 0.55), 'lista para actuar')
  assert.equal(urgencyLabel(0.4, 0.55), 'inquieta')
  assert.equal(urgencyLabel(0.1, 0.55), 'tranquila')
  assert.equal(urgencyLabel(Number.NaN, 0.55), '—')
})

test('las expresiones tienen nombre legible', () => {
  assert.equal(expressionLabel('alegre'), 'Alegre')
  assert.equal(expressionLabel('curiosa'), 'Curiosa')
  assert.equal(expressionLabel('neutra'), 'Neutra')
  assert.equal(expressionLabel('confusa'), 'confusa')
})

test('los orígenes se distinguen de un vistazo', () => {
  assert.equal(sourceLabel('minecraft'), 'Minecraft')
  assert.equal(sourceLabel('vrchat'), 'VRChat')
  assert.equal(sourceLabel('autonomia'), 'ARIA')
  assert.equal(sourceIcon('minecraft'), '⛏️')
  assert.equal(sourceIcon('autonomia'), '🧠')
})

test('un evento se resume con su origen y su clase', () => {
  const event: AutonomyEvent = {
    id: 7,
    kind: 'juego',
    source: 'minecraft',
    text: 'encontré diamantes',
    payload: {},
    at: 0,
  }
  assert.equal(eventLabel(event), 'Minecraft · juego')
})

test('un episodio muestra si salió bien', () => {
  const episode: AutonomyEpisode = {
    id: 1,
    drive: 'curiosidad',
    goal: 'ideas: seguridad',
    action: 'ideas: seguridad',
    said: null,
    result: 'algo',
    ok: true,
    started_at: 0,
    ended_at: 0,
  }
  assert.equal(episodeLabel(episode), '✓ ideas: seguridad')
  assert.equal(episodeLabel({ ...episode, ok: false }), '✕ ideas: seguridad')
})

test('el tiempo transcurrido se lee en palabras', () => {
  const now = 1_700_000_000_000
  const nowSec = now / 1000
  assert.equal(timeAgo(nowSec - 5, now), 'hace 5 s')
  assert.equal(timeAgo(nowSec - 120, now), 'hace 2 min')
  assert.equal(timeAgo(nowSec - 7200, now), 'hace 2 h')
  // Un reloj sin sincronizar no puede inventar años.
  assert.equal(timeAgo(0, now), '')
  assert.equal(timeAgo(nowSec + 60, now), '')
})

test('las rarezas se editan como texto', () => {
  const quirks = ['dice lo que piensa', 'prefiere hacer que recomendar']
  assert.equal(quirksToText(quirks), 'dice lo que piensa\nprefiere hacer que recomendar')
  assert.deepEqual(textToQuirks('uno\n\n  dos  \n'), ['uno', 'dos'])
  assert.deepEqual(textToQuirks(''), [])
})

/* ── La agenda ──────────────────────────────────────────────────────── */

function initiative(over: Partial<AutonomyInitiative> = {}): AutonomyInitiative {
  return {
    id: 1,
    drive: 'orden',
    goal: 'revisar la red local',
    action: 'plan: revisar la red local',
    reason: 'porque alguien lo pidió',
    score: 0.8,
    created_at: 0,
    state: 'pendiente',
    attempts: 0,
    payload: {},
    ...over,
  }
}

test('la agenda sólo muestra lo que ARIA sigue de verdad', () => {
  const agenda = [
    initiative({ id: 1, state: 'pendiente' }),
    initiative({ id: 2, state: 'ejecutada' }),
    initiative({ id: 3, state: 'descartada' }),
  ]
  const pending = pendingInitiatives(agenda)
  assert.equal(pending.length, 1)
  assert.equal(pending[0].id, 1)
})

test('la iniciativa más urgente gana, y a igualdad la más reciente', () => {
  const agenda = [
    initiative({ id: 1, score: 0.4, created_at: 100 }),
    initiative({ id: 2, score: 0.9, created_at: 50 }),
    initiative({ id: 3, score: 0.9, created_at: 200 }),
  ]
  const top = topInitiative(agenda)
  assert.equal(top?.id, 3)
  assert.equal(topInitiative([]), null)
  assert.equal(topInitiative([initiative({ state: 'hecha' })]), null)
})

test('el estado de la iniciativa tiene nombre legible', () => {
  assert.equal(initiativeStateLabel('pendiente'), 'Pendiente')
  assert.equal(initiativeStateLabel('ejecutada'), 'Hecha')
  assert.equal(initiativeStateLabel('descartada'), 'Soltada')
  assert.equal(initiativeStateLabel('raro'), 'raro')
  assert.equal(initiativeStateIcon('pendiente'), '◔')
  assert.equal(initiativeStateIcon('ejecutada'), '✓')
})

/* ── Lecciones ──────────────────────────────────────────────────────── */

function lesson(over: Partial<AutonomyLesson> = {}): AutonomyLesson {
  return {
    id: 1,
    kind: 'fallo',
    text: 'Falló «x»: timeout',
    weight: 0.9,
    source: 'episodio',
    uses: 1,
    suppressed: false,
    created_at: 0,
    ...over,
  }
}

test('las lecciones tienen tipo legible', () => {
  assert.equal(lessonKindLabel('regla'), 'Regla')
  assert.equal(lessonKindLabel('exito'), 'Acierto')
  assert.equal(lessonKindLabel('fallo'), 'Fallo')
  assert.equal(lessonKindLabel('raro'), 'raro')
  assert.equal(lessonKindIcon('fallo'), '✕')
})

test('las lecciones que pesan son las no silenciadas y las más fuertes', () => {
  const lessons = [
    lesson({ id: 1, weight: 0.9 }),
    lesson({ id: 2, weight: 0.8, suppressed: true }),
    lesson({ id: 3, weight: 0.5 }),
  ]
  const top = topLessons(lessons)
  assert.equal(top.length, 2)
  assert.equal(top[0].id, 1)
  assert.ok(!top.some((entry) => entry.id === 2))
})

/* ── Percepción ─────────────────────────────────────────────────────── */

function world(over: Partial<PerceptionWorld> = {}): PerceptionWorld {
  return {
    id: 'minecraft',
    label: 'Minecraft',
    kind: 'juego',
    connected: true,
    status: 'conectado',
    capabilities: ['move', 'say'],
    context: { salud: 20 },
    context_age_secs: 0,
    pending: 0,
    ...over,
  }
}

function perception(over: Partial<PerceptionSnapshot> = {}): PerceptionSnapshot {
  return {
    at: 0,
    worlds: [],
    audience: null,
    skills: [],
    drives: {},
    presence: {
      expression: 'neutra',
      mood: 0.5,
      talking: false,
      channel: 'escritorio',
      place: 'en el escritorio',
      updated_at: 0,
    },
    affect: { emotions: {}, dominant: 'neutra', expression: 'neutra', mood: 0.5, updated_at: 0 },
    events: [],
    agenda: [],
    lessons: [],
    persona: {
      name: 'ARIA',
      role: 'asistente',
      language: 'es',
      tone: 'directa',
      quirks: [],
      values: [],
      interests: [],
      greeting: 'hola',
    },
    ...over,
  }
}

test('el resumen de percepción dice dónde está y quién espera', () => {
  const summary = perceptionSummary(
    perception({
      worlds: [world()],
      audience: {
        channel: 'discord:general',
        kind: 'mensaje',
        author: 'user',
        text: 'hola',
        at: 0,
      },
      drives: { curiosidad: 0.7, social: 0.2 },
    }),
  )
  assert.ok(summary.includes('Minecraft'))
  assert.ok(summary.includes('user'))
  assert.ok(summary.includes('discord:general'))
  assert.ok(summary.includes('curiosidad') || summary.includes('Curiosidad'))
})

test('sin percepción el resumen no inventa nada', () => {
  assert.equal(perceptionSummary(null), 'Sin percepción todavía.')
})

test('sin mundos el resumen lo dice', () => {
  const summary = perceptionSummary(perception())
  assert.ok(summary.includes('Sin mundos'))
  assert.ok(summary.includes('nadie esperando'))
})

test('la pulsión más fuerte se elige bien', () => {
  assert.equal(strongestDrive({ social: 0.2, curiosidad: 0.8 })?.name, 'curiosidad')
  assert.equal(strongestDrive({})?.name, undefined)
  assert.equal(strongestDrive(undefined), null)
})

test('el estado de un mundo es legible y el silencio se cuenta', () => {
  assert.equal(worldStateLabel(world()), 'Conectado')
  assert.equal(worldStateLabel(world({ connected: false, status: 'sin abrir' })), 'Sin abrir')
  assert.ok(worldSilenceLabel(world({ context_age_secs: 30 })).includes('s'))
  assert.ok(worldSilenceLabel(world({ context_age_secs: 600 })).includes('min'))
  assert.equal(worldSilenceLabel(world({ context_age_secs: 0 })), 'sin publicar nada')
})
