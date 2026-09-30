import { motion } from 'framer-motion'
import { useAriaBackend } from '../../hooks/useAriaBackend'
import { useState, useEffect } from 'react'

interface SystemMetrics {
  cpu_percent: number
  mem_percent: number
  disk_percent: number
  uptime: string
  load_average: number
}

function ProgressBar({ label, value, color }: { label: string; value: number; color: string }) {
  const blocks = Math.round(value / 10)
  const filled = '█'.repeat(Math.min(blocks, 10))
  const empty = '░'.repeat(Math.max(0, 10 - blocks))

  return (
    <div className="flex items-center gap-2">
      <span className="w-12 text-[10px] text-text-tertiary">{label}</span>
      <span className={`font-mono text-[10px] ${color}`}>
        {filled}<span className="text-text-muted">{empty}</span>
      </span>
      <span className="ml-auto text-[10px] text-text-secondary">{value.toFixed(0)}%</span>
    </div>
  )
}

export function StatusPanel() {
  const { health } = useAriaBackend()
  const [metrics, setMetrics] = useState<SystemMetrics>({
    cpu_percent: 0,
    mem_percent: 0,
    disk_percent: 0,
    uptime: 'unknown',
    load_average: 0,
  })

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const res = await fetch('http://127.0.0.1:8002/api/control/metrics')
        const data = await res.json()
        setMetrics(data)
      } catch {
        // Backend not available
      }
    }
    fetchMetrics()
    const interval = setInterval(fetchMetrics, 5000)
    return () => clearInterval(interval)
  }, [])

  const uptimeStr = health?.uptime_ms
    ? `${Math.floor(health.uptime_ms / 3600000)}h`
    : metrics.uptime

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-panel rounded-xl p-3"
    >
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-accent-cyan">
          System Status
        </span>
        <span className="flex items-center gap-1 text-[10px] text-accent-green">
          <span className="h-1.5 w-1.5 rounded-full bg-accent-green" />
          Online
        </span>
      </div>

      <div className="space-y-1.5">
        <ProgressBar label="CPU" value={metrics.cpu_percent} color="text-cosmic-primary" />
        <ProgressBar label="RAM" value={metrics.mem_percent} color="text-cosmic-accent" />
        <ProgressBar label="Disk" value={metrics.disk_percent} color="text-cosmic-warning" />
      </div>

      <div className="mt-2 flex items-center justify-between border-t border-border/50 pt-2">
        <span className="text-[10px] text-text-tertiary">Uptime</span>
        <span className="font-mono text-[10px] text-text-secondary">{uptimeStr}</span>
      </div>
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-text-tertiary">Load</span>
        <span className="font-mono text-[10px] text-text-secondary">{metrics.load_average.toFixed(2)}</span>
      </div>
    </motion.div>
  )
}