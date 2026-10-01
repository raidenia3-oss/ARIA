import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import './AgentStatusDashboard.css'

interface AgentStatus {
  id: string
  role: string
  name: string
  status: 'idle' | 'busy' | 'error'
  color: string
  icon: string
  current_task?: string | null
  tasks_completed: number
  tasks_attempted: number
  error_count: number
  uptime_seconds: number
  last_heartbeat?: string | null
  last_execution?: string | null
}

interface OrbitAgent {
  status: AgentStatus
  angle: number
  distance: number
}

const POLL_INTERVAL_MS = 2000
const AXUM_ORIGIN = 'http://127.0.0.1:8002'

/**
 * APEX-style agent status dashboard: a central golden NEXUS with 12 color-coded
 * agent nodes orbiting it, plus a 4-column detail grid underneath.
 *
 * Data comes from `GET /api/swarm/agents/status` (Axum 8002). The component is
 * defensive: a refused backend yields an empty orbit and an error row, never
 * a crash or a fabricated zero.
 */
export function AgentStatusDashboard() {
  const [agents, setAgents] = useState<AgentStatus[]>([])
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout> | null = null

    const fetchAgents = async () => {
      try {
        const response = await fetch(`${AXUM_ORIGIN}/api/swarm/agents/status`, {
          signal: controller.signal,
        })
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }
        const data = await response.json()
        if (cancelled) return
        const list: AgentStatus[] = Array.isArray(data.agents) ? data.agents : []
        setAgents(list)
        setError(null)
      } catch (caught) {
        if (cancelled || controller.signal.aborted) return
        setError(
          caught instanceof Error ? caught.message : String(caught),
        )
      } finally {
        if (!cancelled) {
          setIsLoading(false)
          timer = setTimeout(fetchAgents, POLL_INTERVAL_MS)
        }
      }
    }

    void fetchAgents()

    return () => {
      cancelled = true
      controller.abort()
      if (timer) clearTimeout(timer)
    }
  }, [])

  // Place every agent on the orbit circle. The angle is evenly distributed so
  // the visual matches the APEX reference: N nodes around a central nucleus.
  const orbitAgents: OrbitAgent[] = agents.map((agent, idx) => {
    const total = Math.max(agents.length, 1)
    const angle = (idx / total) * 360
    return { status: agent, angle, distance: 150 }
  })

  const renderOrbit = () => {
    if (agents.length === 0) {
      return (
        <div className="flex h-[500px] items-center justify-center text-text-tertiary">
          {isLoading ? 'Loading agents…' : 'No agents registered'}
        </div>
      )
    }

    return (
      <div className="nucleus-container">
        <svg className="orbit-svg" viewBox="0 0 400 400">
          <circle
            cx="200"
            cy="200"
            r="150"
            fill="none"
            stroke="#38bdf8"
            strokeWidth="1"
            opacity="0.3"
          />

          {orbitAgents.map((orbit) => {
            const rad = (orbit.angle * Math.PI) / 180
            const x = 200 + orbit.distance * Math.cos(rad)
            const y = 200 + orbit.distance * Math.sin(rad)
            const isBusy = orbit.status.status === 'busy'

            return (
              <g key={orbit.status.id}>
                <line
                  x1="200"
                  y1="200"
                  x2={x}
                  y2={y}
                  stroke="#38bdf8"
                  opacity="0.2"
                />

                <circle
                  cx={x}
                  cy={y}
                  r="20"
                  fill={orbit.status.color}
                  opacity={isBusy ? 1 : 0.5}
                  className="agent-node"
                />

                {isBusy && (
                  <circle
                    cx={x}
                    cy={y}
                    r="20"
                    fill="none"
                    stroke="#38bdf8"
                    strokeWidth="2"
                    className="busy-pulse"
                  />
                )}
              </g>
            )
          })}
        </svg>

        <div className="nucleus-center">
          <span className="nucleus-icon">🧠</span>
          <span className="nucleus-label">NEXUS</span>
        </div>
      </div>
    )
  }

  const renderCards = () => {
    if (agents.length === 0) {
      return null
    }

    return (
      <div className="agents-grid">
        {agents.map((agent) => (
          <div
            key={agent.id}
            className="agent-card"
            style={{ borderColor: agent.color }}
          >
            <div className="agent-header">
              <span className="agent-icon">{agent.icon}</span>
              <div>
                <div className="agent-name">{agent.name}</div>
                <div className="agent-role">{agent.role}</div>
              </div>
            </div>

            <div className="agent-status">
              <span className={`status-badge ${agent.status}`}>{agent.status}</span>
            </div>

            {agent.current_task && (
              <div className="current-task">Working on: {agent.current_task}</div>
            )}

            <div className="agent-metrics">
              <div>Tasks: {agent.tasks_completed}</div>
              <div>Errors: {agent.error_count}</div>
              <div>Uptime: {Math.floor(agent.uptime_seconds / 60)}m</div>
            </div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="apex-dashboard"
    >
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-text-primary">
          Agent Status Dashboard
        </h2>
        <span className="text-[10px] text-text-tertiary">
          {agents.length} agents · {orbitAgents.filter((o) => o.status.status === 'busy').length} busy
        </span>
      </div>

      {error ? (
        <p className="mb-2 break-words rounded-lg border border-cosmic-error/40 bg-cosmic-error/10 p-2 text-[10px] leading-relaxed text-cosmic-error">
          {error}
        </p>
      ) : null}

      {renderOrbit()}
      {renderCards()}
    </motion.div>
  )
}

export default AgentStatusDashboard