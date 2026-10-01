import { useEffect, useRef, useState } from 'react'

/**
 * WebSocket de progreso en tiempo real. El navegador no puede enviar
 * cabeceras en el upgrade, asi que el socket se abre sin token y el
 * servidor acepta /api/control/progress/stream como ruta publica
 * (auth.rs PUBLIC_PATHS). El primer mensaje del server es el snapshot
 * actual, asi que un tardio suscriptor no pierde el estado previo.
 */
const PROGRESS_WS_URL = 'ws://127.0.0.1:8002/api/control/progress/stream'

export interface ProgressFrame {
  phase?: string
  run_id?: string
  total?: number | null
  steps_done?: number | null
  current?: { name?: string; tier?: string; index?: number } | null
  last?: { name?: string; tier?: string; index?: number; status?: string; message?: string; elapsed_s?: number } | null
  updated_at?: string
  message?: string
  level?: string
  target?: string
}

export interface ProgressDisplayState {
  phase: string
  total: number | null
  stepsDone: number | null
  current: ProgressFrame['current']
  last: ProgressFrame['last']
  updatedAt: string | null
  lagNotice: string | null
  error: string | null
  connected: boolean
}

const INITIAL: ProgressDisplayState = {
  phase: 'idle',
  total: null,
  stepsDone: null,
  current: null,
  last: null,
  updatedAt: null,
  lagNotice: null,
  error: null,
  connected: false,
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function nonEmptyString(value: unknown): string | null {
  return typeof value === 'string' && value.length > 0 ? value : null
}

/**
 * Suscribe al WebSocket de progreso en tiempo real.
 *
 * El sondeo HTTP (useScanProgress) es el transporte de respaldo; este hook
 * es el de baja latencia. Si el socket cierra o nunca se abre, el componente
 * que lo consume debe seguir usando el sondeo.
 */
export function useProgressStream(enabled: boolean = true): ProgressDisplayState {
  const [state, setState] = useState<ProgressDisplayState>({ ...INITIAL })
  const wsRef = useRef<WebSocket | null>(null)
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!enabled) return

    let stopped = false
    let ws: WebSocket | null = null

    const applyFrame = (frame: ProgressFrame) => {
      if (stopped) return
      setState((prev) => {
        const next: ProgressDisplayState = { ...prev }
        if (frame.phase !== undefined) next.phase = frame.phase
        if (frame.total !== undefined) next.total = isFiniteNumber(frame.total) ? frame.total : null
        if (frame.steps_done !== undefined) {
          next.stepsDone = isFiniteNumber(frame.steps_done) ? frame.steps_done : null
        }
        if (frame.current !== undefined) next.current = frame.current ?? null
        if (frame.last !== undefined) next.last = frame.last ?? null
        if (frame.updated_at !== undefined) next.updatedAt = nonEmptyString(frame.updated_at)
        next.lagNotice = null
        next.error = null
        return next
      })
    }

    const connect = () => {
      try {
        ws = new WebSocket(PROGRESS_WS_URL)
      } catch {
        scheduleFallback()
        return
      }

      ws.onopen = () => {
        if (stopped) return
        setState((prev) => ({ ...prev, connected: true, error: null }))
      }

      ws.onmessage = (event: MessageEvent) => {
        if (stopped) return
        let frame: ProgressFrame
        try {
          frame = JSON.parse(event.data) as ProgressFrame
        } catch {
          return
        }
        if (frame.message && frame.level === 'warn') {
          setState((prev) => ({ ...prev, lagNotice: frame.message ?? null }))
          return
        }
        applyFrame(frame)
      }

      ws.onclose = () => {
        if (stopped) return
        setState((prev) => ({ ...prev, connected: false }))
        scheduleFallback()
      }

      ws.onerror = () => {
        if (stopped) return
        setState((prev) => ({ ...prev, connected: false, error: 'WebSocket error' }))
      }
    }

    const PROGRESS_INTERVAL_MS = 2000
    const scheduleFallback = () => {
      if (stopped) return
      pollRef.current = setTimeout(() => {
        if (stopped) return
        void fetch('/api/control/progress').then((r) => r.json()).then((data) => {
          if (stopped) return
          const snap = data.progress
          if (snap) {
            setState((prev) => ({
              ...prev,
              phase: snap.phase,
              total: isFiniteNumber(snap.total) ? snap.total : null,
              stepsDone: isFiniteNumber(snap.steps_done) ? snap.steps_done : null,
              current: snap.current ?? null,
              last: snap.last ?? null,
              updatedAt: nonEmptyString(snap.updated_at),
            }))
          }
        }).catch(() => {})
        pollRef.current = setTimeout(connect, 5000)
      }, PROGRESS_INTERVAL_MS)
    }

    connect()
    wsRef.current = ws

    return () => {
      stopped = true
      if (ws) ws.close()
      if (pollRef.current) clearTimeout(pollRef.current)
    }
  }, [enabled])

  return state
}