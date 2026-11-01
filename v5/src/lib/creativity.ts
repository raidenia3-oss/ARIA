/**
 * Utilidades puras del laboratorio de creatividad.
 *
 * Todo lo que se puede decidir sin servidor vive aquí: el orden de las
 * ideas (que depende del peso aprendido por tema), las etiquetas de estado
 * y los tonos. Al ser funciones puras se prueban sin navegador ni red.
 */

import type {
  CreativityIdea,
  CreativityIntegration,
  CreativityThemeWeight,
} from './ariaBackend'

/**
 * Cuánto pesa el tema aprendido en el orden final de las ideas.
 *
 * El mismo valor que usa el backend (`THEME_RANK_BONUS` en creativity.rs):
 * si divergen, la UI y el servidor ordenarían distinto.
 */
export const THEME_RANK_BONUS = 0.15

/** Limita un número a un rango. */
export function clamp(value: number, min: number, max: number): number {
  if (Number.isNaN(value)) return min
  return Math.min(Math.max(value, min), max)
}

/**
 * Convierte una puntuación 0..1 en un porcentaje 0..100.
 *
 * Un valor fuera de rango (por ejemplo `NaN` si el servidor no lo manda)
 * se recorta: la barra nunca puede medir más del 100 % ni menos del 0 %.
 */
export function percent(value: number): number {
  return Math.round(clamp(value, 0, 1) * 100)
}

/** Peso aprendido de un tema concreto (0 si nunca se juzgó). */
export function themeWeight(
  profile: CreativityThemeWeight[] | undefined,
  theme: string,
): number {
  if (!profile) return 0
  const found = profile.find((entry) => entry.theme === theme)
  return found ? found.weight : 0
}

/**
 * Puntuación final de una idea: la cruda con el sesgo del tema encima.
 *
 * Si el servidor ya manda `score` (que es exactamente esta cuenta) se usa
 * ese; si no, se calcula aquí para que la UI no dependa del orden del
 * servidor.
 */
export function effectiveScore(
  idea: CreativityIdea,
  profile?: CreativityThemeWeight[],
): number {
  if (typeof idea.score === 'number' && idea.score > 0) {
    return clamp(idea.score, 0, 1)
  }
  const base = typeof idea.raw_score === 'number' && idea.raw_score > 0 ? idea.raw_score : 0
  return clamp(base + themeWeight(profile, idea.theme) * THEME_RANK_BONUS, 0, 1)
}

/** Ordena las ideas de mejor a peor según su puntuación final. */
export function sortIdeas(
  ideas: CreativityIdea[],
  profile?: CreativityThemeWeight[],
): CreativityIdea[] {
  return [...ideas].sort((a, b) => effectiveScore(b, profile) - effectiveScore(a, profile))
}

/** Etiqueta legible de un estado de idea. */
export function ideaStatusLabel(status: string): string {
  switch (status) {
    case 'new':
      return 'Nueva'
    case 'refining':
      return 'Por refinar'
    case 'accepted':
      return 'Aceptada'
    case 'rejected':
      return 'Rechazada'
    case 'built':
      return 'Forjada'
    default:
      return status
  }
}

/** Tono visual de un estado de idea. */
export function statusTone(status: string): 'new' | 'good' | 'bad' | 'working' {
  switch (status) {
    case 'accepted':
    case 'built':
      return 'good'
    case 'rejected':
      return 'bad'
    case 'refining':
      return 'working'
    default:
      return 'new'
  }
}

/**
 * ¿Se puede forjar esta idea?
 *
 * Sólo las ideas aceptadas y que no tienen skill: forjar dos veces la
 * misma idea dejaría dos skills haciendo lo mismo.
 */
export function canForge(idea: CreativityIdea): boolean {
  return idea.status === 'accepted' && !idea.skill_id
}

/** Tono del peso aprendido de un tema. */
export function weightTone(weight: number): 'like' | 'dislike' | 'neutral' {
  if (weight > 0.05) return 'like'
  if (weight < -0.05) return 'dislike'
  return 'neutral'
}

/** Resumen de una línea de una idea, para listados estrechos. */
export function ideaSummaryLine(idea: CreativityIdea): string {
  if (idea.summary) return idea.summary
  if (idea.detail) return idea.detail
  return idea.title
}

/** Etiqueta legible del origen de una idea. */
export function originLabel(origin: string): string {
  switch (origin) {
    case 'solucion':
      return 'solución'
    case 'mejora':
      return 'mejora'
    case 'idea':
      return 'idea'
    case 'manual':
      return 'manual'
    default:
      return origin
  }
}

/** Etiqueta legible del tipo de integración. */
export function integrationKindLabel(kind: string): string {
  switch (kind) {
    case 'herramienta':
      return 'herramienta'
    case 'servicio':
      return 'servicio'
    case 'modulo':
    case 'módulo':
      return 'módulo'
    default:
      return kind || 'integración'
  }
}

/**
 * ¿Se puede probar esta integración?
 *
 * Sólo los servicios HTTP: el servidor hace un `GET` con tiempo límite.
 * Un comando local no se prueba desde aquí.
 */
export function canProbe(integration: CreativityIntegration): boolean {
  const target = integration.target.trim().toLowerCase()
  return target.startsWith('http://') || target.startsWith('https://')
}

/** ¿Hay un objetivo suficiente para crear una skill? */
export function canCreateSkill(goal: string): boolean {
  return goal.trim().length > 0
}
