import { motion } from 'framer-motion'
import type { ActiveView } from '../../App'

interface Tab {
  id: ActiveView
  label: string
  icon: string
  color: string
}

const TABS: Tab[] = [
  { id: 'chat', label: 'Chat', icon: '💬', color: '#38bdf8' },
  { id: 'brain', label: 'Neural Brain', icon: '◈', color: '#a78bfa' },
  { id: 'eye', label: "God's Eye", icon: '◎', color: '#ff6b4a' },
  { id: 'skills', label: 'Skills', icon: '◇', color: '#34d399' },
  { id: 'voice', label: 'Voice', icon: '🎙️', color: '#b066ff' },
]

export function TabBar({ activeView, onTabChange }: { activeView: ActiveView; onTabChange: (v: ActiveView) => void }) {
  return (
    <nav className="flex h-10 items-center gap-1 border-b border-white/10 px-3">
      {TABS.map((tab) => {
        const active = tab.id === activeView
        return (
          <motion.button
            key={tab.id}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => onTabChange(tab.id)}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] font-medium transition-colors ${
              active ? 'text-white' : 'text-text-tertiary hover:text-text-secondary'
            }`}
            style={active ? { color: tab.color } : undefined}
            aria-label={tab.label}
            aria-pressed={active}
          >
            <span style={active ? { color: tab.color } : undefined}>{tab.icon}</span>
            <span>{tab.label}</span>
            {active && (
              <motion.span
                layoutId="tab-indicator"
                className="ml-1 h-px w-6"
                style={{ background: tab.color }}
              />
            )}
          </motion.button>
        )
      })}
    </nav>
  )
}