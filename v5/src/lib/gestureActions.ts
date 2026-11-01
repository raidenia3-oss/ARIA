/**
 * Bus de acciones por gesto.
 *
 * La cámara está en un componente (la consola de gestos) y lo que un gesto
 * debe cambiar vive en otros (el chat, la voz, la navegación). En vez de
 * atar uno con otro, los gestos emiten aquí y quien tiene la capacidad de
 * ejecutarla se suscribe.
 *
 * Sin dependencias: el bus es un `Set` de suscriptores en memoria.
 */

import type { Gesture } from './gestures'

/** Acciones que un gesto puede provocar. */
export type GestureActionId = 'pausar' | 'siguiente' | 'aprobar' | 'detener' | 'ejecutar'

/** Evento emitido cuando se confirma un gesto. */
export interface GestureActionEvent {
  action: GestureActionId
  /** Marca de tiempo del disparo. */
  at: number
}

export type GestureActionListener = (event: GestureActionEvent) => void

/** Gesto -> acción. Un gesto que no está aquí no hace nada. */
export const GESTURE_ACTION_BY_GESTURE: Partial<Record<Gesture, GestureActionId>> = {
  open_palm: 'pausar',
  peace: 'siguiente',
  thumbs_up: 'aprobar',
  fist: 'detener',
  index: 'ejecutar',
}

const listeners = new Set<GestureActionListener>()

/**
 * Se suscribe a las acciones por gesto.
 *
 * @returns La función para cancelar la suscripción.
 */
export function onGestureAction(listener: GestureActionListener): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/** Publica una acción. Los suscriptores se enteran en el acto. */
export function emitGestureAction(action: GestureActionId): void {
  const event: GestureActionEvent = { action, at: Date.now() }
  for (const listener of listeners) {
    try {
      listener(event)
    } catch (error) {
      console.error('[ARIA] fallo en un suscriptor de gestos', error)
    }
  }
}

/** Emite la acción que corresponde a un gesto, si la hay. */
export function emitGesture(gesture: Gesture): boolean {
  const action = GESTURE_ACTION_BY_GESTURE[gesture]
  if (!action) return false
  emitGestureAction(action)
  return true
}
