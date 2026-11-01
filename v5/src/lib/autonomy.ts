/**
 * Utilidades puras del runtime autónomo.
 *
 * Lo que se puede decidir sin servidor vive aquí: cómo se llama cada
 * pulsión, cómo se lee un evento, cuánto tiempo lleva ARIA sin actuar. Al
 * ser funciones puras se prueban sin navegador ni red.
 */

import type {
  AutonomyEvent,
  AutonomyEpisode,
  AutonomyInitiative,
  AutonomyLesson,
  PerceptionSnapshot,
  PerceptionWorld,
} from './ariaBackend'

/** Etiqueta legible de cada pulsión. */
export const DRIVE_LABELS: Record<string, string> = {
  curiosidad: 'Curiosidad',
  energia: 'Energía',
  social: 'Social',
  dominio: 'Dominio',
  orden: 'Orden',
}

/** Etiqueta de una pulsión, o la propia si no se conoce. */
export function driveLabel(name: string): string {
  return DRIVE_LABELS[name] ?? name
}

/** Descripción de para qué sirve cada pulsión. */
export const DRIVE_HINTS: Record<string, string> = {
  curiosidad: 'quiere entender algo nuevo',
  energia: 'necesita descansar',
  social: 'quiere hablar con alguien',
  dominio: 'quiere mejorar lo que sabe hacer',
  orden: 'quiere poner orden',
}

/** Etiqueta legible del modo de ARIA. */
export function modeLabel(mode: string): string {
  switch (mode) {
    case 'activa':
      return 'Activa'
    case 'tranquila':
      return 'Tranquila'
    case 'dormida':
      return 'Dormida'
    default:
      return mode
  }
}

/** Qué puede hacer ARIA en cada modo. */
export const MODE_HINTS: Record<string, string> = {
  activa: 'actúa sola cuando le hace falta',
  tranquila: 'sólo contesta a lo que le dicen',
  dormida: 'no hace nada hasta que la despierten',
}

/** Etiqueta legible de la expresión. */
export function expressionLabel(expression: string): string {
  switch (expression) {
    case 'alegre':
      return 'Alegre'
    case 'curiosa':
      return 'Curiosa'
    case 'concentrada':
      return 'Concentrada'
    case 'aburrida':
      return 'Aburrida'
    case 'neutra':
      return 'Neutra'
    default:
      return expression
  }
}

/** Etiqueta legible del origen de un evento. */
export function sourceLabel(source: string): string {
  switch (source) {
    case 'escritorio':
      return 'Escritorio'
    case 'minecraft':
      return 'Minecraft'
    case 'vrchat':
      return 'VRChat'
    case 'discord':
      return 'Discord'
    case 'telegram':
      return 'Telegram'
    case 'movil':
      return 'Móvil'
    case 'usb':
      return 'USB-ARIA'
    case 'autonomia':
      return 'ARIA'
    default:
      return source
  }
}

/** Icono del origen, para leer la lista de un vistazo. */
export function sourceIcon(source: string): string {
  switch (source) {
    case 'minecraft':
      return '⛏️'
    case 'vrchat':
      return '🎮'
    case 'discord':
      return '💬'
    case 'telegram':
      return '✈️'
    case 'movil':
      return '📱'
    case 'usb':
      return '🔌'
    case 'autonomia':
      return '🧠'
    default:
      return '🖥️'
  }
}

/** Una línea de resumen de un evento. */
export function eventLabel(event: AutonomyEvent): string {
  const kind =
    event.kind === 'habla'
      ? 'habla'
      : event.kind === 'juego'
        ? 'juego'
        : event.kind === 'voz'
          ? 'voz'
          : event.kind === 'presencia'
            ? 'presencia'
            : event.kind === 'sistema'
              ? 'sistema'
              : event.kind === 'accion'
                ? 'acción'
                : event.kind
  return `${sourceLabel(event.source)} · ${kind}`
}

/** Texto corto de un episodio: lo que hizo y si salió bien. */
export function episodeLabel(episode: AutonomyEpisode): string {
  const mark = episode.ok ? '✓' : '✕'
  return `${mark} ${episode.goal}`
}

/**
 * Cuánto tiempo hace, en palabras.
 *
 * `timestamp` viene en segundos epoch. Si el valor no es razonable (0, o un
 * reloj desincronizado), se devuelve `''` en vez de "hace 56 años".
 */
export function timeAgo(timestamp: number, nowMs: number = Date.now()): string {
  if (!timestamp || timestamp <= 0) return ''
  const seconds = Math.floor(nowMs / 1000 - timestamp)
  if (seconds < 0) return ''
  if (seconds < 60) return `hace ${seconds} s`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `hace ${minutes} min`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `hace ${hours} h`
  return `hace ${Math.floor(hours / 24)} d`
}

/** Nivel de una pulsión (0 si no está). */
export function driveLevel(drives: Record<string, number> | undefined, name: string): number {
  if (!drives) return 0
  const value = drives[name]
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

/**
 * Qué tan urgente está ARIA para actuar.
 *
 * Por encima del umbral decide ella; por debajo sólo contesta.
 */
export function urgencyLabel(urge: number, threshold: number): string {
  if (!Number.isFinite(urge)) return '—'
  if (urge >= threshold * 1.4) return 'impaciente'
  if (urge >= threshold) return 'lista para actuar'
  if (urge >= threshold * 0.6) return 'inquieta'
  return 'tranquila'
}

/**
 * Convierte una lista de rarezas en texto editable.
 *
 * El editor de la persona trabaja con una textarea: una rareza por línea.
 */
export function quirksToText(quirks: string[]): string {
  return quirks.join('\n')
}

/** Y de vuelta: cada línea no vacía es una rareza. */
export function textToQuirks(text: string): string[] {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
}

/* ------------------------------------------------------------------ *
 * La agenda: lo que ARIA tiene entre manos
 * ------------------------------------------------------------------ */

/** Etiqueta legible del estado de una iniciativa. */
export function initiativeStateLabel(state: string): string {
  switch (state) {
    case 'pendiente':
      return 'Pendiente'
    case 'ejecutada':
      return 'Hecha'
    case 'descartada':
      return 'Soltada'
    default:
      return state
  }
}

/** Icono del estado de una iniciativa. */
export function initiativeStateIcon(state: string): string {
  switch (state) {
    case 'pendiente':
      return '◔'
    case 'ejecutada':
      return '✓'
    case 'descartada':
      return '✕'
    default:
      return '•'
  }
}

/**
 * Sólo las iniciativas que ARIA sigue de verdad.
 *
 * "Soltada" y "Hecha" son historia: enseñarlas en la lista de lo que tiene
 * entre manos sería mentira.
 */
export function pendingInitiatives(agenda: AutonomyInitiative[]): AutonomyInitiative[] {
  return agenda.filter((initiative) => initiative.state === 'pendiente')
}

/**
 * La iniciativa más urgente: la de mayor peso.
 *
 * Empates se rompen con la más reciente, que es la que se acaba de crear.
 */
export function topInitiative(agenda: AutonomyInitiative[]): AutonomyInitiative | null {
  const pending = pendingInitiatives(agenda)
  if (pending.length === 0) return null
  return pending.reduce((best, current) => {
    if (current.score !== best.score) return current.score > best.score ? current : best
    return current.created_at > best.created_at ? current : best
  })
}

/* ------------------------------------------------------------------ *
 * Lecciones: lo que ARIA ha aprendido
 * ------------------------------------------------------------------ */

/** Etiqueta legible del tipo de lección. */
export function lessonKindLabel(kind: string): string {
  switch (kind) {
    case 'regla':
      return 'Regla'
    case 'exito':
      return 'Acierto'
    case 'fallo':
      return 'Fallo'
    default:
      return kind
  }
}

/** Icono del tipo de lección. */
export function lessonKindIcon(kind: string): string {
  switch (kind) {
    case 'regla':
      return '📌'
    case 'exito':
      return '✓'
    case 'fallo':
      return '✕'
    default:
      return '•'
  }
}

/**
 * Las lecciones que pesan: las que de verdad gobiernan sus decisiones.
 *
 * Se ordena por peso y se corta: el prompt sólo lleva unas pocas, y
 *archicalmente todas parecidas no aportan nada.
 */
export function topLessons(lessons: AutonomyLesson[], count = 5): AutonomyLesson[] {
  return [...lessons]
    .filter((lesson) => !lesson.suppressed)
    .sort((a, b) => b.weight - a.weight || b.uses - a.uses)
    .slice(0, count)
}

/* ------------------------------------------------------------------ *
 * Percepción: lo que ARIA ve ahora mismo
 * ------------------------------------------------------------------ */

/** Etiqueta legible del estado de un mundo. */
export function worldStateLabel(world: PerceptionWorld): string {
  if (world.connected) return 'Conectado'
  switch (world.status) {
    case 'sin abrir':
      return 'Sin abrir'
    case 'esperando puente':
      return 'Esperando puente'
    default:
      return world.status || 'Desconocido'
  }
}

/** Icono según el tipo de mundo. */
export function worldIcon(world: PerceptionWorld): string {
  switch (world.kind) {
    case 'juego':
      return world.id.includes('minecraft') ? '⛏️' : '🎮'
    case 'social':
      return '💬'
    case 'escritorio':
      return '🖥️'
    case 'simulador':
      return '🧪'
    default:
      return '🌐'
  }
}

/**
 * Una línea que resume lo que ARIA está perceiving ahora mismo.
 *
 * Es la misma idea que el prompt de decisión: primero el mundo, luego la
 * gente, luego las ganas. Si no hay nada, lo dice: un "todo tranquilo"
 * inventado es peor que un silencio honesto.
 */
export function perceptionSummary(perception: PerceptionSnapshot | null): string {
  if (!perception) return 'Sin percepción todavía.'

  const connected = perception.worlds.filter((world) => world.connected)
  const parts: string[] = []

  if (connected.length > 0) {
    parts.push(`En ${connected.map((world) => world.label).join(', ')}`)
  } else if (perception.worlds.length > 0) {
    parts.push('Ningún mundo conectado')
  } else {
    parts.push('Sin mundos')
  }

  if (perception.audience) {
    parts.push(`${perception.audience.author} esperando en ${perception.audience.channel}`)
  } else {
    parts.push('nadie esperando')
  }

  const strongest = strongestDrive(perception.drives)
  if (strongest) {
    parts.push(`gana ${driveLabel(strongest.name)} (${strongest.level.toFixed(2)})`)
  }

  return `${parts.join(' · ')}.`
}

/** La pulsión más fuerte, o `null` si no hay ninguna. */
export function strongestDrive(
  drives: Record<string, number> | undefined,
): { name: string; level: number } | null {
  if (!drives) return null
  const entries = Object.entries(drives).filter(([, level]) => Number.isFinite(level))
  if (entries.length === 0) return null
  const [name, level] = entries.reduce((best, current) =>
    current[1] > best[1] ? current : best,
  )
  return { name, level }
}

/**
 * Cuánto lleva un mundo sin decir nada.
 *
 * Un mundo que lleva mucho tiempo callado puede estar muerto: la UI lo
 * avisa en vez de fingir que todo va bien.
 */
export function worldSilenceLabel(world: PerceptionWorld): string {
  const age = world.context_age_secs
  if (!age) return 'sin publicar nada'
  if (age < 60) return `hace ${Math.max(1, Math.floor(age))} s`
  if (age < 3600) return `hace ${Math.floor(age / 60)} min`
  return `hace ${Math.floor(age / 3600)} h`
}
