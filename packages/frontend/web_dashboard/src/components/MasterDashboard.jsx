import React, { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Activity, Cpu, Memory, Zap, Brain, Network, Shield, GitBranch, Play, Square, RefreshCw, Server, Database, Wifi } from 'lucide-react'

const BASE = '/api/orchestrator/master'

async function api(path, opts = {}) {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

function Stat({ icon: Icon, label, value, ok }) {
  return (
    <div className="master-stat">
      <div className="master-stat-icon" style={{ color: ok ? '#22c55e' : '#f59e0b' }}>
        <Icon size={16} />
      </div>
      <div className="master-stat-body">
        <span className="master-stat-label">{label}</span>
        <span className="master-stat-value">{value}</span>
      </div>
    </div>
  )
}

function ModuleRow({ m }) {
  return (
    <div className="master-module-row">
      <span className="master-dot" style={{ background: m.healthy ? '#22c55e' : '#ef4444' }}></span>
      <span className="master-module-name">{m.name}</span>
      <span className="master-module-status">{m.healthy ? 'OK' : m.error || 'ERR'}</span>
    </div>
  )
}

export default function MasterDashboard({ open, onClose, theme }) {
  const [status, setStatus] = useState(null)
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(false)
  const [pipelineSteps, setPipelineSteps] = useState([{ kind: 'noop' }])
  const [pipelineName, setPipelineName] = useState('mission-' + Date.now())
  const [healthInfo, setHealthInfo] = useState(null)

  const refresh = async () => {
    try {
      const [s, ev] = await Promise.all([
        api('/status'),
        api('/events?limit=20'),
      ])
      setStatus(s)
      setEvents(ev)
    } catch (e) {
      console.error('[master] refresh failed', e)
    }
  }

  useEffect(() => {
    if (!open) return
    refresh()
    const t = setInterval(refresh, 5000)
    return () => clearInterval(t)
  }, [open])

  const runCycle = async () => {
    setLoading(true)
    try {
      await api('/cycle', { method: 'POST' })
      await refresh()
    } finally {
      setLoading(false)
    }
  }

  const runPipeline = async () => {
    setLoading(true)
    try {
      await api('/pipeline', {
        method: 'POST',
        body: JSON.stringify({ name: pipelineName, steps: pipelineSteps }),
      })
      await refresh()
    } finally {
      setLoading(false)
    }
  }

  const emitTest = async () => {
    try {
      await api('/events', {
        method: 'POST',
        body: JSON.stringify({ source: 'dashboard', kind: 'manual', level: 'info' }),
      })
      await refresh()
    } catch (e) {
      console.error(e)
    }
  }

  const checkHealth = async () => {
    try {
      const res = await fetch('/health')
      const data = await res.json()
      setHealthInfo(data)
    } catch (e) {
      setHealthInfo({ status: 'error', detail: 'Not connected' })
    }
  }

  useEffect(() => {
    checkHealth()
    if (!open) return
    refresh()
    const t = setInterval(refresh, 5000)
    const h = setInterval(checkHealth, 10000)
    return () => { clearInterval(t); clearInterval(h) }
  }, [open])

  if (!open) return null

  const modules = status?.modules_registered || []
  const eventsByLevel = status?.events_by_level || {}
  const pipelines = status?.pipelines_total || 0
  const cycles = status?.cycles || 0

  return (
    <div className="master-overlay" onClick={onClose}>
      <motion.div
        className="master-panel"
        onClick={(e) => e.stopPropagation()}
        initial={{ x: '100%' }}
        animate={{ x: 0 }}
        exit={{ x: '100%' }}
        transition={{ type: 'spring', damping: 25, stiffness: 300 }}
      >
        <header className="master-header">
          <div className="master-title">
            <Activity size={18} style={{ color: theme }} />
            <span>MASTER CONTROL</span>
            <span className="master-badge">OFFLINE</span>
          </div>
          <button className="master-close" onClick={onClose}>
            <X size={18} />
          </button>
        </header>

        <div className="master-body">
          {/* Backend health */}
          <section className="master-section">
            <h4>BACKEND HEALTH</h4>
            <div className="master-stats">
              <Stat icon={Server} label="Status" value={healthInfo?.status || "?"} ok={healthInfo?.status === "ok"} />
              <Stat icon={Database} label="Ollama" value={healthInfo?.ollama ? "ON" : "OFF"} ok={healthInfo?.ollama} />
              <Stat icon={Wifi} label="Port" value={healthInfo?.port ? `:${healthInfo.port}` : "--"} ok />
              <Stat icon={Zap} label="Mode" value={healthInfo?.mode || "--"} ok />
            </div>
          </section>

          {/* Status overview */}
          <section className="master-section">
            <h4>ECOSYSTEM STATUS</h4>
            <div className="master-stats">
              <Stat icon={Cpu} label="Cycles" value={cycles} ok />
              <Stat icon={Network} label="Modules" value={modules.length} ok={modules.length > 0} />
              <Stat icon={Brain} label="Pipelines" value={pipelines} ok />
              <Stat icon={Shield} label="Events" value={status?.events_total || 0} ok />
            </div>
            <div className="master-levels">
              {Object.entries(eventsByLevel).map(([lvl, n]) => (
                <span key={lvl} className={`master-level master-level-${lvl}`}>
                  {lvl}: {n}
                </span>
              ))}
            </div>
          </section>

          {/* Modules */}
          <section className="master-section">
            <h4>REGISTERED MODULES</h4>
            <div className="master-modules">
              {modules.length === 0 ? (
                <span className="master-empty">No modules registered</span>
              ) : (
                modules.map((m) => <ModuleRow key={m} m={{ name: m, healthy: false, error: '' }} />)
              )}
            </div>
          </section>

          {/* Actions */}
          <section className="master-section">
            <h4>AUTONOMOUS CONTROL</h4>
            <div className="master-actions">
              <button className="master-btn" onClick={runCycle} disabled={loading}>
                <RefreshCw size={14} /> Run Cycle
              </button>
              <button className="master-btn" onClick={emitTest} disabled={loading}>
                <Zap size={14} /> Emit Event
              </button>
              <button className="master-btn" onClick={refresh} disabled={loading}>
                <Activity size={14} /> Refresh
              </button>
            </div>
          </section>

          {/* Pipeline builder */}
          <section className="master-section">
            <h4>MISSION PIPELINE</h4>
            <input
              className="master-input"
              value={pipelineName}
              onChange={(e) => setPipelineName(e.target.value)}
              placeholder="Pipeline name"
            />
            <div className="master-pipeline-steps">
              {pipelineSteps.map((s, i) => (
                <input
                  key={i}
                  className="master-input"
                  value={s.kind}
                  onChange={(e) => {
                    const next = [...pipelineSteps]
                    next[i].kind = e.target.value
                    setPipelineSteps(next)
                  }}
                  placeholder="step kind"
                />
              ))}
            </div>
            <div className="master-actions">
              <button className="master-btn primary" onClick={runPipeline} disabled={loading}>
                <Play size={14} /> Execute Pipeline
              </button>
              <button
                className="master-btn"
                onClick={() => setPipelineSteps([...pipelineSteps, { kind: 'noop' }])}
              >
                <Square size={14} /> Add Step
              </button>
            </div>
          </section>

          {/* Events stream */}
          <section className="master-section">
            <h4>EVENT STREAM</h4>
            <div className="master-events">
              {events.length === 0 ? (
                <span className="master-empty">No events</span>
              ) : (
                events.slice(0, 10).map((ev) => (
                  <div key={ev.event_id} className="master-event">
                    <span className={`master-level master-level-${ev.level}`}>{ev.level}</span>
                    <span className="master-event-src">{ev.source}</span>
                    <span className="master-event-kind">{ev.kind}</span>
                    <span className="master-event-dec">{ev.decision}</span>
                  </div>
                ))
              )}
            </div>
          </section>
        </div>
      </motion.div>
    </div>
  )
}