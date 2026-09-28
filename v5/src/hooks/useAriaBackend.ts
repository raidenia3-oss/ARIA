import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { OrbPhase } from './useOrbState'
import {
  ariaBackend,
  AriaBackendError,
  type BackendConnectionState,
  type HealthResponse,
  type HeartbeatResponse,
  type PcStateResponse,
} from '../lib/ariaBackend'

const AGENT_ID = 'aria-orb-visual'
const HEALTH_INTERVAL_MS = 15000
const HEARTBEAT_INTERVAL_MS = 10000
const PC_STATE_INTERVAL_MS = 20000
const RECONNECT_DELAY_MS = 3000

export interface AriaBackendStatus {
  connection: BackendConnectionState
  health: HealthResponse | null
  pcState: PcStateResponse | null
  heartbeat: HeartbeatResponse | null
  lastError: string | null
  /** Fase del orbe derivada del estado de la conexión con Axum. */
  connectionPhase: OrbPhase
  lastHeartbeatAt: number | null
}

export interface AriaBackendController extends AriaBackendStatus {
  refresh: () => void
  ping: () => void
}

/**
 * Conecta el HUD con el backend Axum en 127.0.0.1:8002.
 *
 * Sondea GET /health, envía POST /api/daemon/heartbeat y consulta
 * POST /api/pc/state. Traduce el estado de la conexión a una fase del orbe:
 *   - conectando  -> 'thinking'   (estableciendo enlace con el Cerebro)
 *   - online      -> 'idle'       (enlace vivo)
 *   - offline     -> 'listening'  (esperando que vuelva el Cerebro)
 *
 * No toca el renderizado: sólo expone la fase que `OrbVisual` recibe por props.
 */
export function useAriaBackend(enabled = true): AriaBackendController {
  const [connection, setConnection] = useState<BackendConnectionState>('connecting')
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [pcState, setPcState] = useState<PcStateResponse | null>(null)
  const [heartbeat, setHeartbeat] = useState<HeartbeatResponse | null>(null)
  const [lastError, setLastError] = useState<string | null>(null)
  const [lastHeartbeatAt, setLastHeartbeatAt] = useState<number | null>(null)
  const [nonce, setNonce] = useState(0)

  const mounted = useRef(true)
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  const reportError = useCallback((error: unknown) => {
    if (error instanceof AriaBackendError) {
      setLastError(error.message)
    } else {
      setLastError(error instanceof Error ? error.message : String(error))
    }
  }, [])

  // Sondeo de salud — determina si el enlace con Axum está vivo.
  useEffect(() => {
    if (!enabled) return

    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout> | null = null
    let stopped = false

    const poll = async () => {
      try {
        const payload = await ariaBackend.health(controller.signal)
        if (stopped || !mounted.current) return
        setHealth(payload)
        setLastError(null)
        setConnection('online')
      } catch (error) {
        if (stopped || !mounted.current) return
        if (controller.signal.aborted) return
        setConnection('offline')
        reportError(error)
      } finally {
        if (!stopped && mounted.current) {
          timer = setTimeout(poll, HEALTH_INTERVAL_MS)
        }
      }
    }

    void poll()

    return () => {
      stopped = true
      controller.abort()
      if (timer) clearTimeout(timer)
    }
  }, [enabled, nonce, reportError])

  // Latido del daemon — mantiene el agente registrado en `agent_registry`.
  useEffect(() => {
    if (!enabled) return

    const controller = new AbortController()
    let stopped = false

    const beat = async () => {
      try {
        const payload = await ariaBackend.heartbeat(
          { agent_id: AGENT_ID, status: 'alive' },
          controller.signal,
        )
        if (stopped || !mounted.current) return
        setHeartbeat(payload)
        setLastHeartbeatAt(Date.now())
      } catch (error) {
        if (stopped || !mounted.current || controller.signal.aborted) return
        reportError(error)
      } finally {
        if (!stopped && mounted.current) {
          setTimeout(beat, HEARTBEAT_INTERVAL_MS)
        }
      }
    }

    void beat()

    return () => {
      stopped = true
      controller.abort()
    }
  }, [enabled, reportError])

  // Estado de la PC — alimenta la reactividad del orbe.
  useEffect(() => {
    if (!enabled) return

    const controller = new AbortController()
    let stopped = false

    const poll = async () => {
      try {
        const payload = await ariaBackend.pcState(
          { agent_id: AGENT_ID, pc_state: null },
          controller.signal,
        )
        if (stopped || !mounted.current) return
        setPcState(payload)
      } catch (error) {
        if (stopped || !mounted.current || controller.signal.aborted) return
        reportError(error)
      } finally {
        if (!stopped && mounted.current) {
          setTimeout(poll, PC_STATE_INTERVAL_MS)
        }
      }
    }

    void poll()

    return () => {
      stopped = true
      controller.abort()
    }
  }, [enabled, reportError])

  // Reconexión rápida cuando el enlace cae, sin esperar al siguiente sondeo.
  useEffect(() => {
    if (!enabled || connection !== 'offline') return
    const timer = setTimeout(() => setNonce((value) => value + 1), RECONNECT_DELAY_MS)
    return () => clearTimeout(timer)
  }, [enabled, connection, lastError])

  const refresh = useCallback(() => setNonce((value) => value + 1), [])
  const ping = useCallback(() => {
    void ariaBackend
      .health()
      .then(() => setNonce((value) => value + 1))
      .catch(() => undefined)
  }, [])

  const connectionPhase = useMemo<OrbPhase>(() => {
    if (!enabled) return 'idle'
    if (connection === 'connecting') return 'thinking'
    if (connection === 'offline') return 'listening'
    return 'idle'
  }, [enabled, connection])

  return {
    connection,
    health,
    pcState,
    heartbeat,
    lastError,
    connectionPhase,
    lastHeartbeatAt,
    refresh,
    ping,
  }
}
