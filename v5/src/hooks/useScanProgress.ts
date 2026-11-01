import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ariaBackend,
  AriaBackendError,
  type ProgressLastStep,
  type ProgressPhase,
  type ProgressStep,
} from '../lib/ariaBackend'

/**
 * `PROGRESS_POLL_INTERVAL_SECS` en el servidor es 2 (control.rs:84) y el
 * rate limit es de 100 req/min por IP (`RATE_LIMIT_MAX`, state.rs:20).
 *
 * Sondear a 1000ms duplicaría el presupuesto de la app sin ganar nada
 * (el snapshot sólo cambia cuando el hijo emite un frame), así que el suelo
 * es 2000ms y nunca menos.
 */
const PROGRESS_INTERVAL_MS = 2000

export interface ScanProgressOptions {
  enabled?: boolean
}

export interface ScanProgressState {
  /**
   * Phase reportada por el servidor. Se tipa como unión abierta porque el
   * backend puede añadir fases (el aviso de lag del WebSocket ya introduce
   * valores fuera del conjunto `idle|running|ok|failed`): cualquier `string`
   * debe poder renderizarse sin romperse.
   */
  phase: ProgressPhase | (string & {})
  /** `null` cuando el servidor omite el campo, NUNCA 0. */
  total: number | null
  /** `null` cuando el servidor omite el campo, NUNCA 0. */
  stepsDone: number | null
  current: ProgressStep | null
  last: ProgressLastStep | null
  /** RFC3339 del servidor, o `null` si aún no hubo respuesta válida. */
  updatedAt: string | null
  error: string | null
  /** `true` en HTTP 401: las credenciales no sirvieron. */
  authError: boolean
  isLoading: boolean
  refresh: () => void
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function nonEmptyString(value: unknown): string | null {
  return typeof value === 'string' && value.length > 0 ? value : null
}

/**
 * Sondea `GET /api/control/progress` y expone el progreso real del run de
 * setup del backend ARIA.
 *
 * Patrón de sondeo idéntico al de `useAriaBackend`: `setTimeout` recursivo
 * (nunca `setInterval`, para que una respuesta lenta no apile llamadas),
 * `AbortController`, ref `mounted` y bandera `stopped`.
 *
 * Añado un token de petición monótono: si una respuesta lenta llegara
 * después de una más nueva, se descarta en lugar de sobrescribir estado más
 * fresco. Sin esto, un snapshot viejo puede "rebobinar" la barra.
 *
 * Los campos ausentes se traducen a `null`. El servers los OMITE cuando
 * los desconoce (`skip_serializing_if`), así que `0` sería una mentira.
 */
export function useScanProgress({ enabled = true }: ScanProgressOptions = {}): ScanProgressState {
  const [phase, setPhase] = useState<string>('idle')
  const [total, setTotal] = useState<number | null>(null)
  const [stepsDone, setStepsDone] = useState<number | null>(null)
  const [current, setCurrent] = useState<ProgressStep | null>(null)
  const [last, setLast] = useState<ProgressLastStep | null>(null)
  const [updatedAt, setUpdatedAt] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [authError, setAuthError] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [nonce, setNonce] = useState(0)

  const mounted = useRef(true)
  const requestToken = useRef(0)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  const refresh = useCallback(() => setNonce((value) => value + 1), [])

  useEffect(() => {
    if (!enabled) return

    const controller = new AbortController()
    let stopped = false
    let timer: ReturnType<typeof setTimeout> | null = null

    const poll = async () => {
      requestToken.current += 1
      const token = requestToken.current
      if (mounted.current) setIsLoading(true)

      try {
        const snapshot = await ariaBackend.progress(controller.signal)
        if (stopped || !mounted.current) return
        // Respuesta obsoleta: una petición más nueva ya está en vuelo.
        if (token !== requestToken.current) return

        const rawPhase = nonEmptyString(snapshot.phase)
        setPhase(rawPhase ?? 'idle')
        setTotal(isFiniteNumber(snapshot.total) ? snapshot.total : null)
        setStepsDone(isFiniteNumber(snapshot.steps_done) ? snapshot.steps_done : null)
        setCurrent(snapshot.current ?? null)
        setLast(snapshot.last ?? null)
        setUpdatedAt(nonEmptyString(snapshot.updated_at))
        setError(null)
        setAuthError(false)
      } catch (caught) {
        if (stopped || !mounted.current) return
        if (controller.signal.aborted) return
        if (token !== requestToken.current) return

        if (caught instanceof AriaBackendError && caught.status === 401) {
          // Una barra congelada en 0% para siempre es PEOR que un error
          // honesto: el usuario no puede distinguir "no ha empezado" de
          // "no estamos mirando".
          setAuthError(true)
          setError(
            'ARIA backend rechazó las credenciales (HTTP 401). Define VITE_ARIA_API_KEY o fija ARIA_API_KEY en el servidor.',
          )
        } else {
          setAuthError(false)
          setError(
            caught instanceof AriaBackendError
              ? caught.message
              : caught instanceof Error
                ? caught.message
                : String(caught),
          )
        }
      } finally {
        if (mounted.current) setIsLoading(false)
        if (!stopped && mounted.current) {
          timer = setTimeout(poll, PROGRESS_INTERVAL_MS)
        }
      }
    }

    void poll()

    return () => {
      stopped = true
      controller.abort()
      if (timer) clearTimeout(timer)
    }
  }, [enabled, nonce])

  return {
    phase,
    total,
    stepsDone,
    current,
    last,
    updatedAt,
    error,
    authError,
    isLoading,
    refresh,
  }
}