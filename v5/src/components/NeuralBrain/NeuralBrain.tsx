import { useEffect, useState } from 'react'

export interface AgentNode {
  name: string
  role: string
  status: 'idle' | 'working' | 'error'
  task_count: number
  error_count: number
  pipeline_ready?: boolean
}

export interface NeuralBrainState {
  agents: AgentNode[]
  total_tasks: number
  active_agents: number
  error_agents: number
  last_updated: string
}

const AGENT_COLORS: Record<string, string> = {
  CodeAnalyzer: '#38bdf8',
  DocsWriter: '#a78bfa',
  Tester: '#34d399',
  ResearchAgent: '#f59e0b',
}

function useAgentStatus(poll_ms = 3000): NeuralBrainState {
  const [state, setState] = useState<NeuralBrainState>({
    agents: [],
    total_tasks: 0,
    active_agents: 0,
    error_agents: 0,
    last_updated: '',
  })

  useEffect(() => {
    let cancelled = false
    async function fetchStatus() {
      try {
        const res = await fetch('/api/agents/status')
        const data = await res.json()
        if (cancelled) return
        const agents: AgentNode[] = (data.agent_list || []).map((a: Record<string, unknown>) => ({
          name: String(a.name || 'unknown'),
          role: String(a.role || ''),
          status: (a.status as AgentNode['status']) || 'idle',
          task_count: Number(a.task_count || 0),
          error_count: Number(a.error_count || 0),
          pipeline_ready: Boolean(a.pipeline_ready),
        }))
        setState({
          agents,
          total_tasks: agents.reduce((s, a) => s + a.task_count, 0),
          active_agents: agents.filter((a) => a.status === 'working').length,
          error_agents: agents.filter((a) => a.status === 'error').length,
          last_updated: new Date().toISOString(),
        })
      } catch {
        /* backend no disponible */
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
          const angle = (i / state.agents.length) * Math.PI * 2 - Math.PI / 2
          const ax = centerX + Math.cos(angle) * radius * 0.72
          const ay = centerY + Math.sin(angle) * radius * 0.72
          const color = AGENT_COLORS[agent.name] || '#64748b'
          return (
            <g key={agent.name}>
              <line x1={centerX} y1={centerY} x2={ax} y2={ay}
                stroke={color} strokeOpacity="0.25" strokeWidth="1"
                strokeDasharray="4 4" />
              <circle cx={ax} cy={ay} r={14} fill="#0f172a" stroke={color} strokeWidth="1.5"
                filter="url(#glow)" />
              <circle cx={ax} cy={ay} r={4} fill={color}>
                {agent.status === 'working' && (
                  <animate attributeName="r" values="4;8;4" dur="1.5s" repeatCount="indefinite" />
                )}
              </circle>
              <text x={ax} y={ay + 30} textAnchor="middle"
                fill={color} fontSize="11" fontFamily="monospace">
                {agent.name.replace('Agent', '')}
              </text>
              <text x={ax} y={ay + 44} textAnchor="middle"
                fill={agent.status === 'working' ? color : '#64748b'}
                fontSize="9" fontFamily="monospace">
                {agent.status === 'working' ? '● WORKING' :
                 agent.status === 'error' ? '✕ ERROR' : '○ IDLE'}
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
            {state.active_agents} active · {state.total_tasks} tasks
          </text>
        </g>
      </svg>

      {/* Stats overlay */}
      <div className="absolute bottom-0 left-0 right-0 flex justify-center gap-4 text-[10px] font-mono">
        <span className="text-cyan-400">● {state.active_agents} active</span>
        <span className="text-green-400">✓ {state.total_tasks} tasks</span>
        <span className="text-red-400">✕ {state.error_agents} errors</span>
      </div>
    </div>
  )
}