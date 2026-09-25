import { motion } from 'framer-motion'
import type { OrbPhase } from '../../hooks/useOrbState'
import { orbStates } from '../../hooks/useOrbState'

interface HeaderProps {
  orbState: OrbPhase
  showSkills: boolean
  onSkillsToggle: () => void
  onControlClick: () => void
}

const buttonClass =
  'btn-glow no-drag flex h-7 w-7 items-center justify-center rounded-lg text-text-secondary hover:text-accent-cyan hover:bg-white/5'

export function Header({ orbState, showSkills, onSkillsToggle, onControlClick }: HeaderProps) {
  const status = orbStates[orbState]

  const minimize = () => window.electronAPI?.windowMinimize()
  const maximize = () => window.electronAPI?.windowMaximize()
  const close = () => window.electronAPI?.windowClose()

  return (
    <header className="drag-region header-bar relative z-30 flex h-11 shrink-0 items-center gap-3 px-3">
      <div className="flex items-center gap-2">
        <motion.span
          whileHover={{ rotate: 90, scale: 1.15 }}
          transition={{ duration: 0.2 }}
          className="flex h-5 w-5 items-center justify-center"
          style={{ color: status.primary, filter: `drop-shadow(0 0 6px ${status.glow})` }}
        >
          <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4">
            <path d="M12 2l3.2 6.8L22 12l-6.8 3.2L12 22l-3.2-6.8L2 12l6.8-3.2z" />
          </svg>
        </motion.span>
        <span className="text-[13px] font-semibold tracking-wide text-text-primary">
          ARIA OS <span className="font-normal text-text-tertiary">v5.0</span>
        </span>
      </div>

      <div className="flex items-center gap-2">
        <span
          className="status-dot"
          style={{ backgroundColor: status.primary, boxShadow: `0 0 10px ${status.glow}` }}
        />
        <span className="text-[11px] font-medium uppercase tracking-widest" style={{ color: status.primary }}>
          {status.label}
        </span>
      </div>

      <div className="mx-1 h-4 flex-1 header-divider" />

      <div className="flex items-center gap-1">
        <motion.button
          whileHover={{ scale: 1.08 }}
          whileTap={{ scale: 0.92 }}
          onClick={onSkillsToggle}
          className={buttonClass}
          style={showSkills ? { color: status.primary } : undefined}
          aria-label="Mostrar skills"
          title="Skills"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4">
            <path d="M12 2l9 5-9 5-9-5 9-5zM3 12l9 5 9-5M3 17l9 5 9-5" />
          </svg>
        </motion.button>

        <motion.button
          whileHover={{ scale: 1.08 }}
          whileTap={{ scale: 0.92 }}
          onClick={onControlClick}
          className={buttonClass}
          aria-label="Centro de control"
          title="Control"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4">
            <path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6" />
          </svg>
        </motion.button>

        <span className="no-drag mx-1 h-4 w-px bg-white/10" />

        <motion.button
          whileHover={{ scale: 1.08 }}
          whileTap={{ scale: 0.92 }}
          onClick={minimize}
          className={buttonClass}
          aria-label="Minimizar"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4">
            <path d="M5 12h14" />
          </svg>
        </motion.button>

        <motion.button
          whileHover={{ scale: 1.08 }}
          whileTap={{ scale: 0.92 }}
          onClick={maximize}
          className={buttonClass}
          aria-label="Maximizar"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4">
            <rect x="5" y="5" width="14" height="14" rx="2" />
          </svg>
        </motion.button>

        <motion.button
          whileHover={{ scale: 1.08 }}
          whileTap={{ scale: 0.92 }}
          onClick={close}
          className="btn-glow no-drag flex h-7 w-7 items-center justify-center rounded-lg text-text-secondary hover:bg-red-500/20 hover:text-red-400"
          aria-label="Cerrar"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4">
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </motion.button>
      </div>
    </header>
  )
}
