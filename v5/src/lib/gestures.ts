/**
 * Reconocimiento de gestos.
 *
 * Funciones puras y sin dependencias: la misma malla de mano produce siempre
 * el mismo gesto, y se pueden probar sin cámara ni navegador.
 */

/** Gestos que ARIA reconoce. */
export type Gesture =
  | 'none'
  | 'fist'
  | 'index'
  | 'peace'
  | 'open_palm'
  | 'thumbs_up'

/** Punto 2D/3D de un landmark de la mano. */
export interface HandPoint {
  x: number
  y: number
  z: number
}

/** Qué hace ARIA con cada gesto. */
export interface GestureAction {
  gesture: Gesture
  label: string
  description: string
  /** `true` si la acción no necesita identidad confirmada. */
  safeWithoutIdentity: boolean
}

/**
 * Mapa de gestos a acciones.
 *
 * Las acciones seguras (pausar, avanzar, aprobar) funcionan sin identidad
 * verificada. Las que tocan el sistema (ejecutar) exigen rostro reconocido:
 * un gesto de un desconocido no debe alcanzar el shell.
 */
export const GESTURE_ACTIONS: GestureAction[] = [
  {
    gesture: 'open_palm',
    label: 'Pausar',
    description: 'Detiene lo que ARIA esté haciendo ahora mismo.',
    safeWithoutIdentity: true,
  },
  {
    gesture: 'peace',
    label: 'Siguiente',
    description: 'Avanza a la siguiente sugerencia o resultado.',
    safeWithoutIdentity: true,
  },
  {
    gesture: 'thumbs_up',
    label: 'Aprobar',
    description: 'Confirma la sugerencia activa.',
    safeWithoutIdentity: true,
  },
  {
    gesture: 'fist',
    label: 'Detener',
    description: 'Corta la acción en curso.',
    safeWithoutIdentity: true,
  },
  {
    gesture: 'index',
    label: 'Ejecutar',
    description: 'Ejecuta la orden pendiente de ARIA.',
    safeWithoutIdentity: false,
  },
]

/** Glifo que representa cada gesto en la interfaz. */
export const GESTURE_GLYPH: Record<Gesture, string> = {
  none: '·',
  fist: '✊',
  index: '☝️',
  peace: '✌️',
  open_palm: '🖐️',
  thumbs_up: '👍',
}

/**
 * Dedo extendido: la punta está más lejos de la muñeca que la articulación.
 *
 * Comparar contra la articulación intermedia (y no contra la base) evita que
 * una mano en perspectiva se lea como cerrada.
 */
export function isFingerExtended(
  landmarks: HandPoint[],
  tip: number,
  pip: number,
  wrist = 0,
): boolean {
  const t = landmarks[tip]
  const p = landmarks[pip]
  const w = landmarks[wrist]
  if (!t || !p || !w) return false
  const tipDist = Math.hypot(t.x - w.x, t.y - w.y)
  const pipDist = Math.hypot(p.x - w.x, p.y - w.y)
  return tipDist > pipDist * 1.12
}

/** Dedos extendidos de una mano: índice, medio, anular y meñique. */
export function extendedFingers(landmarks: HandPoint[]): boolean[] {
  return [
    isFingerExtended(landmarks, 8, 6),
    isFingerExtended(landmarks, 12, 10),
    isFingerExtended(landmarks, 16, 14),
    isFingerExtended(landmarks, 20, 18),
  ]
}

/**
 * Clasifica el gesto de una mano a partir de sus 21 landmarks.
 *
 * Devuelve `'none'` si la malla es incompleta o si la forma no encaja en
 * ninguno de los gestos conocidos: es preferible no entender el gesto a
 * entenderlo mal.
 */
export function classifyGesture(landmarks: HandPoint[] | null | undefined): Gesture {
  if (!landmarks || landmarks.length < 21) return 'none'

  const [index, middle, ring, pinky] = extendedFingers(landmarks)

  // El pulgar no se extiende "hacia arriba" como los demás dedos: se mide
  // por su apartamiento lateral respecto de la articulation.
  const thumbTip = landmarks[4]
  const thumbIp = landmarks[3]
  const thumbMcp = landmarks[2]
  const wrist = landmarks[0]
  const thumbOut =
    thumbTip && thumbIp && wrist
      ? Math.abs(thumbTip.x - wrist.x) > Math.abs(thumbIp.x - wrist.x) * 1.1
      : false
  const thumbUp =
    thumbTip && thumbMcp && wrist
      ? thumbTip.y < thumbMcp.y && thumbTip.y < wrist.y - 0.02
      : false

  const count = [index, middle, ring, pinky].filter(Boolean).length

  if (count === 0) {
    // Puño cerrado. Si además el pulgar está hacia arriba, es "pulgar arriba".
    if (thumbUp && !thumbOut) return 'thumbs_up'
    return 'fist'
  }
  if (count === 4) return 'open_palm'
  if (count === 2 && index && middle) return 'peace'
  if (count === 1 && index) return 'index'
  if (count === 1 && thumbUp) return 'thumbs_up'
  return 'none'
}

/**
 * Distancia media entre dos conjuntos de landmarks, normalizada.
 *
 * Sirve para saber si la mano se ha quedado quieta: un gesto sólo cuenta
 * si la mano lleva varios frames sin moverse.
 */
export function handMotion(
  previous: HandPoint[] | null | undefined,
  current: HandPoint[],
): number {
  if (!previous || previous.length !== current.length) return 1
  let total = 0
  let counted = 0
  for (let i = 0; i < current.length; i++) {
    const a = previous[i]
    const b = current[i]
    // Una malla incompleta no es un motivo para romper el bucle de vídeo:
    // se salta el punto y se sigue con el resto.
    if (!a || !b) continue
    total += Math.hypot(b.x - a.x, b.y - a.y)
    counted++
  }
  if (counted === 0) return 1
  return total / counted
}
