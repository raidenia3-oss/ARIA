import { motion } from 'framer-motion'
import { useState, useEffect } from 'react'

interface ServiceStatus {
  name: string
  status: 'online' | 'degraded' | 'offline'
  port?: string
  latency?: number
  description: string
}

const statusConfig = {
  online: { icon: '✅', color: 'text-accent-green', label: 'Online' },
  degraded: { icon: '⚠️', color: 'text-cosmic-warning', label: 'Degraded' },
  offline: { icon: '❌', color: 'text-cosmic-error', label: 'Offline' },
}

export function ServicesPanel() {
  const [services, setServices] = useState<ServiceStatus[]>([])

  useEffect(() => {
    const fetchServices = async () => {
      try {
        const res = await fetch('http://127.0.0.1:8002/api/control/services')
        const data = await res.json()
        setServices(data.services || [])
      } catch {
        setServices([
          { name: 'Axum Backend', status: 'offline', description: 'ARIA v6.0 Axum server' },
          { name: 'Autonomous', status: 'offline', description: 'Self-improvement loop' },
          { name: 'Discord Bot', status: 'offline', description: 'Chat integration' },
          { name: 'WebSocket', status: 'offline', description: 'Real-time events' },
        ])
      }
    }
    fetchServices()
    const interval = setInterval(fetchServices, 10000)
    return () => clearInterval(interval)
  }, [])

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-panel rounded-xl p-3"
    >
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-accent-purple">
          Services
        </span>
        <span className="text-[10px] text-text-tertiary">
          {services.filter(s => s.status === 'online').length}/{services.length}
        </span>
      </div>

      <div className="space-y-2">
        {services.map((svc, i) => {
          const cfg = statusConfig[svc.status]
          return (
            <motion.div
              key={svc.name}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className="flex items-center gap-2 rounded-lg bg-surface-0/50 p-2"
            >
              <span className={`text-sm ${cfg.color}`}>{cfg.icon}</span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-[11px] font-medium text-text-primary">
                  {svc.name}
                </div>
                <div className="truncate text-[9px] text-text-tertiary">
                  {svc.description}
                </div>
              </div>
              {svc.port && (
                <span className="font-mono text-[9px] text-text-muted">{svc.port}</span>
              )}
              {svc.latency !== undefined && (
                <span className="font-mono text-[9px] text-accent-cyan">{svc.latency}ms</span>
              )}
            </motion.div>
          )
        })}
      </div>
    </motion.div>
  )
}