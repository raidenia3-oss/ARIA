import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Activity, Zap, Database, Wind } from 'lucide-react'
import '../styles/ReactorMatrix.css'

export default function ReactorMatrix({ theme, telemetry }) {
  const [metrics, setMetrics] = useState(null)
  const [agents, setAgents] = useState([])
  const [network, setNetwork] = useState(null)
  const [loading, setLoading] = useState(true)

  const loadData = async () => {
    setLoading(true)
    try {
      const [telemetryRes, orchestratorRes] = await Promise.all([
        fetch('/api/system/telemetry').then((r) => (r.ok ? r.json() : null)).catch(() => null),
        fetch('/api/orchestrator').then((r) => (r.ok ? r.json() : null)).catch(() => null),
      ])

      if (telemetryRes) {
        setMetrics(telemetryRes)
      }
      if (orchestratorRes) {
        setAgents(Array.isArray(orchestratorRes.nodes) ? orchestratorRes.nodes : [])
        setNetwork(orchestratorRes.network || null)
      }
    } catch (e) {
      console.error('[reactor] load failed', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 5000)
    return () => clearInterval(interval)
  }, [])

  const systemMetrics = [
    {
      label: 'CPU',
      value: metrics?.cpu?.percent ?? metrics?.cpu_usage ?? 0,
      max: 100,
      unit: '%',
      icon: <Zap size={16} />,
      color: 'text-yellow-400',
    },
    {
      label: 'RAM',
      value: metrics?.memory?.percent ?? metrics?.ram_usage ?? 0,
      max: 100,
      unit: '%',
      icon: <Database size={16} />,
      color: 'text-blue-400',
    },
    {
      label: 'GPU',
      value: metrics?.gpu?.utilization ?? metrics?.gpu_usage ?? 0,
      max: 100,
      unit: '%',
      icon: <Activity size={16} />,
      color: 'text-cyan-400',
    },
    {
      label: 'AGENTS',
      value: metrics?.swarm?.active_agents ?? agents.length ?? 0,
      max: 16,
      unit: '/16',
      icon: <Activity size={16} />,
      color: 'text-green-400',
    },
  ]

  return (
    <div className="reactor-matrix">
      <div className="matrix-header">
        <h2>REACTOR MATRIX</h2>
        <span className="timestamp">{new Date().toLocaleTimeString()}</span>
      </div>

      {/* System Metrics Grid */}
      <div className="metrics-grid">
        {systemMetrics.map((metric, idx) => (
          <motion.div
            key={metric.label}
            className="metric-card glass"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.1 }}
            style={{ '--metric-color': theme }}
          >
            <div className="metric-header">
              <span className={`metric-icon ${metric.color}`}>{metric.icon}</span>
              <span className="metric-label">{metric.label}</span>
            </div>

            <div className="metric-display">
              <div className="metric-value">
                {typeof metric.value === 'number' ? metric.value.toFixed(1) : metric.value}
                <span className="metric-unit">{metric.unit}</span>
              </div>
              <div className="metric-max">{metric.max}</div>
            </div>

            <div className="metric-bar">
              <motion.div
                className="metric-fill"
                initial={{ width: 0 }}
                animate={{
                  width: `${(metric.value / metric.max) * 100}%`,
                }}
                transition={{ type: 'spring', damping: 20 }}
                style={{
                  background: `linear-gradient(90deg, ${theme}, rgba(99, 102, 241, 0.3))`,
                }}
              />
            </div>
          </motion.div>
        ))}
      </div>

      {/* Tactical Table */}
      <div className="tactical-table glass">
        <table>
          <thead>
            <tr>
              <th>AGENT ID</th>
              <th>STATUS</th>
              <th>LOAD</th>
              <th>MEMORY</th>
              <th>LATENCY</th>
              <th>TASKS</th>
            </tr>
          </thead>
          <tbody>
            {agents.map((agent, idx) => (
              <motion.tr
                key={agent.id || idx}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.1 }}
              >
                <td className="agent-id">{agent.id || `C-${String(idx + 1).padStart(2, '0')}`}</td>
                <td>
                  <span className={`status ${agent.status === 'active' || agent.status === 'online' ? 'active' : 'idle'}`}>
                    ● {agent.status ? agent.status.toUpperCase() : 'UNKNOWN'}
                  </span>
                </td>
                <td>
                  <div className="mini-bar">
                    <div
                      className="mini-fill"
                      style={{
                        width: `${Math.min((agent.load ?? agent.cpu ?? 0), 100)}%`,
                        background: theme,
                      }}
                    />
                  </div>
                </td>
                <td>{(agent.memory ?? agent.ram ?? 0).toFixed(0)} MB</td>
                <td>{(agent.latency ?? 0).toFixed(1)} ms</td>
                <td>{agent.tasks ?? agent.active_tasks ?? 0}</td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Network Stats */}
      <div className="network-stats">
        <div className="stat-item glass">
          <span className="stat-label">PACKETS/S</span>
          <span className="stat-value">
            {loading ? '...' : network?.packets_per_second ?? metrics?.network?.packets_per_second ?? '-'}
          </span>
        </div>
        <div className="stat-item glass">
          <span className="stat-label">BANDWIDTH</span>
          <span className="stat-value">
            {loading ? '...' : network?.bandwidth ?? metrics?.network?.bandwidth ?? '-'}
          </span>
        </div>
        <div className="stat-item glass">
          <span className="stat-label">LATENCY</span>
          <span className="stat-value">
            {loading ? '...' : network?.latency ?? metrics?.network?.latency ?? '-'}
          </span>
        </div>
        <div className="stat-item glass">
          <span className="stat-label">UPTIME</span>
          <span className="stat-value">
            {loading ? '...' : metrics?.system?.uptime ?? network?.uptime ?? '-'}
          </span>
        </div>
      </div>
    </div>
  )
}
