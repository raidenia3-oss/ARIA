import { useEffect, useState } from 'react'
import {
  ariaBackend,
  normalizeAgentStatus,
  type AgentStatusName,
  type SwarmAgentRow,
} from '../../lib/ariaBackend'

/**
 * Fila ya normalizada para el anillo.
 *
 * Solo contiene lo que el servidor MIDE. No hay `task_count`, `error_count` ni
 * `pipeline_ready` porque `GET /api/agents/status` no los emite nunca (la nota
 * `STATUS_NOTE` de agents.rs:32 lo dice); cada uno de esos campos se habría
 * fabricado un 0 permanente.
 */
export interface AgentNode {
  id: string
  name: string
  role: string
  status: AgentStatusName
  source: SwarmAgentRow['source'] | null
  /** `null` = no medido (clave omitida por `skip_serializing_if`). */
  current_task: string | null
  /** `null` = no medido; nunca `0`. */
  heartbeat_age_seconds: number | null
  /** `null` = no medido. */
  stale: boolean | null
}

export interface NeuralBrainState {
  agents: AgentNode[]
  /**
   * Pendientes MEDIDOS en `SharedState.task_queue`. Es el único agregado real
   * del endpoint y NO es un "total de tareas": `null` cuando no se pudo leer.
   */
  queue_depth: number | null
  /** Agentes cuyo estado normalizado es `busy` — recuento de datos reales. */
  busy_agents: number
  /** Agentes cuyo estado normalizado es `error` — recuento de datos reales. */
  error_agents: number
  /** `false` tras un fallo: no hay lectura válida que mostrar. */
  online: boolean
  last_updated: string
}

const AGENT_COLORS: Record<string, string> = {
  CodeAnalyzer: '#38bdf8',
  DocsWriter: '#a78bfa',
  Tester: '#34d399',
  ResearchAgent: '#f59e0b',
}

/** Etiqueta por estado normalizado. Presentación, no telemetría. */
const STATUS_LABEL: Record<AgentStatusName, string> = {
  idle: '○ IDLE',
  busy: '● BUSY',
  error: '✕ ERROR',
  stalled: '◐ STALLED',
  offline: '○ OFFLINE',
}

/** Estado de reposo honesto: sin lectura no hay ceros que mostrar. */
const UNAVAILABLE: NeuralBrainState = {
  agents: [],
  queue_depth: null,
  busy_agents: 0,
  error_agents: 0,
  online: false,
  last_updated: '',
}

function toNode(row: SwarmAgentRow): AgentNode {
  return {
    // `id`, `name`, `role` y `source` no llevan `skip_serializing_if`: el
    // servidor los emite siempre, así que se copian tal cual.
    id: row.id,
    name: row.name,
    role: row.role,
    status: normalizeAgentStatus(row.status, row.stale),
    source: row.source,
    current_task: row.current_task ?? null,
    heartbeat_age_seconds:
      typeof row.heartbeat_age_seconds === 'number' ? row.heartbeat_age_seconds : null,
    stale: typeof row.stale === 'boolean' ? row.stale : null,
  }
}

function useAgentStatus(poll_ms = 3000): NeuralBrainState {
  const [state, setState] = useState<NeuralBrainState>(UNAVAILABLE)

  useEffect(() => {
    let cancelled = false
    async function fetchStatus() {
      try {
        // Misma ruta que antes (`GET /api/agents/status` en 8002) pero a través
        // del cliente centralizado: esa ruta NO es pública (auth.rs:35 excluye
        // todo menos `/`, `/health`, `/ws`), así que un fetch desnudo recibía
        // 401 y el panel se quedaba permanentemente vacío.
        const data = await ariaBackend.agentsStatus()
        if (cancelled) return
        if (!data || !Array.isArray(data.agents)) {
          throw new Error('respuesta sin `agents` (unavailable)')
        }
        const agents = data.agents.map(toNode)
        setState({
          agents,
          queue_depth: typeof data.queue_depth === 'number' ? data.queue_depth : null,
          busy_agents: agents.filter((a) => a.status === 'busy').length,
          error_agents: agents.filter((a) => a.status === 'error').length,
          online: true,
          last_updated: new Date().toISOString(),
        })
      } catch {
        /* backend no disponible: se vacía para no pintar datos viejos como vivos */
        if (!cancelled) setState(UNAVAILABLE)
      }
    }
    fetchStatus()
    const id = setInterval(fetchStatus, poll_ms)
    return () => { cancelled = true; clearInterval(id) }
  }, [poll_ms])
  return state
}

export function NeuralBrain() {
  const state = useAgentStatus()

  const radius = 180
  const centerX = 200
  const centerY = 200

  return (
    <div className="relative h-[420px] w-full">
      <svg viewBox="0 0 400 400" className="h-full w-full">
        <defs>
          <radialGradient id="brainBg" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#0f172a" stopOpacity="0.9" />
            <stop offset="100%" stopColor="#020617" stopOpacity="0.4" />
          </radialGradient>
          <filter id="glow">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <circle cx={centerX} cy={centerY} r={radius} fill="url(#brainBg)" stroke="#1e293b" strokeWidth="1" />

        {/* Conexiones entre agentes y centro */}
        {state.agents.map((agent, i) => {
          // Sin este `Math.max`, `agents.length === 0` daba `0/0 = NaN`.
          const slots = Math.max(state.agents.length, 1)
          const angle = (i / slots) * Math.PI * 2 - Math.PI / 2
          const ax = centerX + Math.cos(angle) * radius * 0.72
          const ay = centerY + Math.sin(angle) * radius * 0.72
          const color = AGENT_COLORS[agent.name] || '#64748b'
          const isBusy = agent.status === 'busy'
          const isAlert = agent.status === 'error'
          return (
            <g key={agent.id || agent.name}>
              <line x1={centerX} y1={centerY} x2={ax} y2={ay}
                stroke={color} strokeOpacity="0.25" strokeWidth="1"
                strokeDasharray="4 4" />
              <circle cx={ax} cy={ay} r={14} fill="#0f172a" stroke={color} strokeWidth="1.5"
                filter="url(#glow)" />
              <circle cx={ax} cy={ay} r={4} fill={color}>
                {isBusy && (
                  <animate attributeName="r" values="4;8;4" dur="1.5s" repeatCount="indefinite" />
                )}
              </circle>
              <text x={ax} y={ay + 30} textAnchor="middle"
                fill={color} fontSize="11" fontFamily="monospace">
                {(agent.name || '—').replace('Agent', '')}
              </text>
              <text x={ax} y={ay + 44} textAnchor="middle"
                fill={isBusy || isAlert ? color : '#64748b'}
                fontSize="9" fontFamily="monospace">
                {STATUS_LABEL[agent.status]}
              </text>
            </g>
          )
        })}

        {/* Centro: ARIA nucleus */}
        <g>
          <circle cx={centerX} cy={centerY} r={28} fill="#0f172a"
            stroke="#38bdf8" strokeOpacity="0.6" strokeWidth="1" />
          <circle cx={centerX} cy={centerY} r={16} fill="#38bdf8" fillOpacity="0.3">
            <animate attributeName="r" values="16;20;16" dur="2s" repeatCount="indefinite" />
          </circle>
          <circle cx={centerX} cy={centerY} r={6} fill="#38bdf8" />
          <text x={centerX} y={centerY - 22} textAnchor="middle"
            fill="#38bdf8" fontSize="10" fontFamily="monospace" fontWeight="bold">
            ARIA
          </text>
          <text x={centerX} y={centerY + 36} textAnchor="middle"
            fill="#64748b" fontSize="9" fontFamily="monospace">
            {state.online ? `${state.busy_agents} busy · queue ${state.queue_depth ?? '—'}` : 'unavailable'}
          </text>
        </g>
      </svg>

      {/* Stats overlay */}
      <div className="absolute bottom-0 left-0 right-0 flex justify-center gap-4 text-[10px] font-mono">
        <span className="text-cyan-400">● {state.online ? `${state.busy_agents} busy` : '—'}</span>
        <span className="text-green-400">✓ {state.online ? `${state.queue_depth ?? '—'} queued` : '—'}</span>
        {/* El servidor NO registra errores por agente (agents.rs:32): se dice
            que no se mide, en vez de pintar un 0 siempre verde. */}
        <span className="text-text-tertiary">errors: not tracked</span>
      </div>
    </div>
  )
}