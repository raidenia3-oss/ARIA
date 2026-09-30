import { motion } from 'framer-motion'
import { StatusPanel } from './StatusPanel'
import { ServicesPanel } from './ServicesPanel'
import { LogsPanel } from './LogsPanel'

export function ControlDashboard() {
  return (
    <div className="flex h-full flex-col gap-3 p-3">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="flex items-center justify-between"
      >
        <h2 className="text-sm font-semibold text-text-primary">
          ARIA Control Center
        </h2>
        <span className="text-[10px] text-text-tertiary">v6.0.0</span>
      </motion.div>

      <div className="grid grid-cols-2 gap-3">
        <StatusPanel />
        <ServicesPanel />
      </div>

      <div className="flex-1">
        <LogsPanel />
      </div>
    </div>
  )
}