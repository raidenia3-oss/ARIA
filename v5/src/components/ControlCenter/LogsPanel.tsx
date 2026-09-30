import { motion } from 'framer-motion'
import { useState, useEffect } from 'react'
import { useAriaBackend } from '../../hooks/useAriaBackend'

interface LogEntry {
  timestamp: string
  level: 'info' | 'success' | 'warning' | 'error'
  message: string
}

const levelConfig = {
  info: { icon: 'ℹ️', color: 'text-cosmic-primary' },
  success: { icon: '✅', color: 'text-accent-green' },
  warning: { icon: '⚠️', color: 'text-cosmic-warning' },
  error: { icon: '❌', color: 'text-cosmic-error' },
}

// Mock logs - in production, fetch from /api/control/logs
const mockLogs: LogEntry[] = [
  { timestamp: '12:34:56', level: 'success', message: 'Auto-improvement: +3 commits' },
  { timestamp: '12:10:23', level: 'info', message: 'Update check: no new version' },
  { timestamp: '11:58:45', level: 'info', message: 'USB device connected (Kilo v2)' },
  { timestamp: '11:45:12', level: 'success', message: 'Auto-restart: Axum recovered' },
  { timestamp: '11:32:08', level: 'info', message: 'Database checkpoint created (8.2MB)' },
]

export function LogsPanel() {
  const [logs, setLogs] = useState<LogEntry[]>(mockLogs)
  const { health } = useAriaBackend()

  // Simulate new log entries
  useEffect(() => {
    const interval = setInterval(() => {
      const newLog: LogEntry = {
        timestamp: new Date().toTimeString().split(' ')[0],
        level: ['info', 'success', 'warning'][Math.floor(Math.random() * 3)] as LogEntry['level'],
        message: [
          'Heartbeat OK',
          'Memory usage normal',
          'Background task completed',
          'Network latency: 12ms',
        ][Math.floor(Math.random() * 4)],
      }
      setLogs(prev => [newLog, ...prev.slice(0, 9)])
    }, 10000)

    return () => clearInterval(interval)
  }, [])

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-panel rounded-xl p-3"
    >
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-accent-green">
          Recent Activity
        </span>
        <span className="flex items-center gap-1">
          <span className="h-1.5 w-1.5 rounded-full bg-accent-green" />
          <span className="text-[10px] text-text-tertiary">Live</span>
        </span>
      </div>

      <div className="max-h-48 space-y-1 overflow-y-auto font-mono">
        {logs.map((log, i) => {
          const cfg = levelConfig[log.level]
          return (
            <motion.div
              key={`${log.timestamp}-${i}`}
              initial={{ opacity: 0, x: -4 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-start gap-2 rounded px-2 py-1 hover:bg-surface-0/50"
            >
              <span className="shrink-0 text-[10px] text-text-muted">{log.timestamp}</span>
              <span className={`shrink-0 text-[10px] ${cfg.color}`}>{cfg.icon}</span>
              <span className="text-[10px] text-text-secondary">{log.message}</span>
            </motion.div>
          )
        })}
      </div>
    </motion.div>
  )
}