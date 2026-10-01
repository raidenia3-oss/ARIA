import { useEffect } from 'react'
import { motion, useSpring, useTransform } from 'framer-motion'
import { useProgressStream } from '../hooks/useProgressStream'

interface AnimatedCounterProps {
  value: number
  suffix?: string
  prefix?: string
  decimals?: number
  duration?: number
  className?: string
}

/**
 * Animated counter in the style of the EONVERSE video: "1,637 FOUND OF 1,297".
 *
 * The value interpolates through a framer-motion spring so the number ramps
 * with physical acceleration rather than a linear jump. Formatting uses the
 * en-US locale thousands separator, so 1297 renders as "1,297".
 */
export function AnimatedCounter({
  value,
  suffix = '',
  prefix = '',
  decimals = 0,
  duration = 1.2,
  className = '',
}: AnimatedCounterProps) {
  const spring = useSpring(0, { stiffness: 80, damping: 20, duration })
  const displayed = useTransform(spring, (v) => v.toFixed(decimals))
  const formatted = useTransform(displayed, (v) => {
    const num = Number(v)
    if (!Number.isFinite(num)) return '0'
    return num.toLocaleString('en-US')
  })

  useEffect(() => {
    spring.set(value)
  }, [value, spring])

  return (
    <span className={className}>
      {prefix}
      <motion.span>{formatted}</motion.span>
      {suffix}
    </span>
  )
}

interface FoundOfCounterProps {
  found: number
  total: number
  className?: string
}

/**
 * "1,637 FOUND OF 1,297" exactly as shown in the EONVERSE reference video.
 *
 * `total` is the target and `found` is what has been located so far. If found
 * exceeds total (the scan turned up more than expected) it is not clamped:
 * the video says "found of", not "found out of".
 */
export function FoundOfCounter({ found, total, className = '' }: FoundOfCounterProps) {
  const safeTotal = Math.max(0, total)
  const safeFound = Math.max(0, found)
  const percent = safeTotal > 0 ? Math.min(100, (safeFound / safeTotal) * 100) : 0

  return (
    <div className={`flex flex-col items-center ${className}`}>
      <div className="flex items-baseline gap-1 font-mono text-xl font-semibold text-cosmic-primary">
        <AnimatedCounter value={safeFound} prefix="" />
        <span className="ml-1 text-sm font-normal text-text-secondary">FOUND</span>
        <span className="text-text-muted">OF</span>
        <AnimatedCounter value={safeTotal} />
      </div>
      <div className="mt-1 h-1 w-40 overflow-hidden rounded-full bg-surface-1">
        <motion.div
          className="h-full bg-cosmic-primary"
          initial={{ width: 0 }}
          animate={{ width: `${percent}%` }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
        />
      </div>
    </div>
  )
}

/**
 * Live progress panel wired to the WebSocket stream.
 *
 * Renders the animated "FOUND OF" counter, a percentage bar and the current
 * step name. Falls back to HTTP polling when the socket is unavailable.
 */
export function ProgressDisplay() {
  const { phase, total, stepsDone, current, last, updatedAt, lagNotice, error, connected } =
    useProgressStream()

  const found = stepsDone ?? 0
  const safeTotal = total ?? 0
  const percent = safeTotal > 0 ? Math.min(100, (found / safeTotal) * 100) : null

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-panel rounded-xl p-3"
    >
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-accent-cyan">
          Scan Progress
        </span>
        <span
          className={`flex items-center gap-1 text-[10px] ${
            phase === 'running' ? 'text-cosmic-primary' :
            phase === 'ok' ? 'text-cosmic-success' :
            phase === 'failed' ? 'text-cosmic-error' : 'text-text-tertiary'
          }`}
        >
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              phase === 'running' ? 'bg-cosmic-primary animate-pulse' :
              phase === 'ok' ? 'bg-cosmic-success' :
              phase === 'failed' ? 'bg-cosmic-error' : 'bg-text-muted'
            }`}
          />
          {phase}
          {connected ? null : <span className="text-text-muted">· poll</span>}
        </span>
      </div>

      {lagNotice ? (
        <p className="mb-2 text-[10px] text-cosmic-warning">{lagNotice}</p>
      ) : null}
      {error ? <p className="mb-2 text-[10px] text-cosmic-error">{error}</p> : null}

      <FoundOfCounter found={found} total={safeTotal} className="mb-3" />

      {percent !== null ? (
        <div className="flex items-center gap-2">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-1">
            <div
              className={`h-full rounded-full transition-[width] duration-500 ease-out ${
                phase === 'running' ? 'bg-cosmic-primary animate-pulse' :
                phase === 'ok' ? 'bg-cosmic-success' : 'bg-cosmic-error'
              }`}
              style={{ width: `${percent}%` }}
            />
          </div>
          <span className="w-12 shrink-0 text-right font-mono text-[10px] text-text-secondary">
            {percent.toFixed(1)}%
          </span>
        </div>
      ) : null}

      {current ? (
        <div className="mt-1.5 flex items-center justify-between">
          <span className="truncate text-[10px] text-text-secondary">
            {current.name ?? '—'}
          </span>
          {current.tier ? (
            <span className="ml-2 shrink-0 font-mono text-[9px] text-text-muted">
              {current.tier}
            </span>
          ) : null}
        </div>
      ) : null}

      {last ? (
        <div className="mt-1.5 flex items-center justify-between border-t border-border/50 pt-1.5">
          <span className="truncate text-[10px] text-text-tertiary">
            Last: {last.name ?? '—'}
          </span>
          <span className="font-mono text-[9px] text-text-muted">
            {last.elapsed_s != null ? `${last.elapsed_s.toFixed(1)}s` : '—'}
          </span>
        </div>
      ) : null}

      <div className="mt-2 flex items-center justify-between border-t border-border/50 pt-2">
        <span className="text-[10px] text-text-tertiary">Updated</span>
        <span className="font-mono text-[10px] text-text-muted">
          {updatedAt ?? '—'}
        </span>
      </div>
    </motion.div>
  )
}

export default ProgressDisplay