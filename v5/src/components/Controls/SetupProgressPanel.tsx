import { motion } from 'framer-motion'
import { useScanProgress } from '../../hooks/useScanProgress'

interface PhaseStyle {
  label: string
  dot: string
  bar: string
  text: string
}

/**
 * Indexado por `string`, NO por la unión `ProgressPhase`.
 *
 * Es exactamente la clase de bug que rompió `ServicesPanel`: una tabla
 * indexada por unión hace que `table[valorDesconocido]` sea `undefined` en
 * tiempo de ejecución aunque TypeScript compile. Aquí la fase la decide el
 * servidor, así que el acceso va por `string` y siempre hay un respaldo.
 */
const PHASE_STYLES: Record<string, PhaseStyle> = {
  idle: {
    label: 'Idle',
    dot: 'bg-text-muted',
    bar: 'bg-border-bright',
    text: 'text-text-tertiary',
  },
  running: {
    label: 'Running',
    dot: 'bg-cosmic-primary',
    bar: 'bg-cosmic-primary',
    text: 'text-cosmic-primary',
  },
  ok: {
    label: 'Completed',
    dot: 'bg-cosmic-success',
    bar: 'bg-cosmic-success',
    text: 'text-cosmic-success',
  },
  failed: {
    label: 'Failed',
    dot: 'bg-cosmic-error',
    bar: 'bg-cosmic-error',
    text: 'text-cosmic-error',
  },
}

const FALLBACK_PHASE_STYLE: PhaseStyle = {
  label: 'Unknown',
  dot: 'bg-cosmic-warning',
  bar: 'bg-cosmic-warning',
  text: 'text-cosmic-warning',
}

function phaseStyle(phase: string): PhaseStyle {
  const known = PHASE_STYLES[phase]
  if (known) return known
  // Fase no reconocida: se muestra la fase cruda, nunca `undefined`.
  return { ...FALLBACK_PHASE_STYLE, label: phase.length > 0 ? phase : FALLBACK_PHASE_STYLE.label }
}

/** Igual de deliberado: `status` viene de un subproceso, no de una unión. */
const STEP_STATUS_STYLES: Record<string, string> = {
  ok: 'text-cosmic-success',
  success: 'text-cosmic-success',
  pass: 'text-cosmic-success',
  passed: 'text-cosmic-success',
  done: 'text-cosmic-success',
  completed: 'text-cosmic-success',
  fail: 'text-cosmic-error',
  failed: 'text-cosmic-error',
  error: 'text-cosmic-error',
  warn: 'text-cosmic-warning',
  warning: 'text-cosmic-warning',
  skip: 'text-text-tertiary',
  skipped: 'text-text-tertiary',
}

const FALLBACK_STATUS_STYLE = 'text-text-secondary'

function stepStatusStyle(status: string): string {
  return STEP_STATUS_STYLES[status.toLowerCase()] ?? FALLBACK_STATUS_STYLE
}

/**
 * Porcentaje calculable o `null`.
 *
 * `total` puede venir AUSENTE (el servidor lo omite si el hijo nunca dijo
 * cuántos pasos hay) y nunca debe dividir por cero ni imprimir `NaN`: la
 * respuesta es `null` y la UI muestra "—".
 */
function computePercent(stepsDone: number | null, total: number | null): number | null {
  if (stepsDone === null || total === null) return null
  if (!Number.isFinite(stepsDone) || !Number.isFinite(total)) return null
  if (total <= 0) return null
  const ratio = (stepsDone / total) * 100
  if (!Number.isFinite(ratio)) return null
  return Math.max(0, Math.min(100, Math.round(ratio)))
}

function formatElapsed(elapsed: number | undefined): string {
  if (typeof elapsed !== 'number' || !Number.isFinite(elapsed)) return '—'
  return `${elapsed.toFixed(1)}s`
}

/**
 * Progreso REAL de la instalación, leído de `GET /api/control/progress`.
 *
 * Todo texto de `current`/`last` viene de un SUBPROCESO y por tanto es no
 * confiable: se renderiza como hijos de React (escapado automático) y
 * NUNCA con `dangerouslySetInnerHTML`.
 */
export function SetupProgressPanel() {
  const { phase, total, stepsDone, current, last, updatedAt, error, authError, isLoading } =
    useScanProgress()

  const style = phaseStyle(phase)
  const percent = computePercent(stepsDone, total)
  const isRunning = phase === 'running'

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-panel rounded-xl p-3"
    >
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-accent-cyan">
          Setup Progress
        </span>
        <span className={`flex items-center gap-1 text-[10px] ${style.text}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${style.dot} ${isRunning ? 'animate-pulse' : ''}`} />
          {style.label}
        </span>
      </div>

      {authError ? (
        <div className="rounded-lg border border-cosmic-error/40 bg-cosmic-error/10 p-2">
          <p className="text-[10px] font-medium text-cosmic-error">Sin acceso al progreso</p>
          <p className="mt-1 text-[10px] leading-relaxed text-text-secondary">
            {error ??
              'El backend ARIA rechazó las credenciales (HTTP 401), así que no se puede leer el progreso.'}
          </p>
        </div>
      ) : (
        <>
          <div className="flex items-center gap-2">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-1">
              <div
                className={`h-full rounded-full transition-[width] duration-500 ease-out ${style.bar} ${
                  isRunning ? 'animate-pulse' : ''
                }`}
                style={{ width: `${percent ?? 0}%` }}
              />
            </div>
            <span className="w-12 shrink-0 text-right font-mono text-[10px] text-text-secondary">
              {percent === null ? '—' : `${percent}%`}
            </span>
          </div>

          <div className="mt-1.5 flex items-center justify-between">
            <span className="text-[10px] text-text-tertiary">Steps</span>
            <span className="font-mono text-[10px] text-text-secondary">
              {stepsDone === null ? '—' : stepsDone}
              <span className="text-text-muted"> / </span>
              {total === null ? '—' : total}
            </span>
          </div>

          {phase === 'idle' && (
            <p className="mt-1.5 text-[10px] text-text-tertiary">
              Idle — no setup run in progress
            </p>
          )}

          {isRunning && current && (
            <div className="mt-1.5 flex items-center justify-between">
              <span className="truncate text-[10px] text-text-secondary">{current.name ?? '—'}</span>
              {current.tier ? (
                <span className="ml-2 shrink-0 font-mono text-[9px] text-text-muted">
                  {current.tier}
                </span>
              ) : null}
            </div>
          )}

          {last && (
            <div className="mt-1.5 flex items-center justify-between border-t border-border/50 pt-1.5">
              <span className="truncate text-[10px] text-text-tertiary">
                Last: {last.name ?? '—'}
              </span>
              <span className="flex shrink-0 items-center gap-2">
                {last.status ? (
                  <span className={`font-mono text-[9px] ${stepStatusStyle(last.status)}`}>
                    {last.status}
                  </span>
                ) : null}
                <span className="font-mono text-[9px] text-text-muted">
                  {formatElapsed(last.elapsed_s)}
                </span>
              </span>
            </div>
          )}

          {last?.message ? (
            <p className="mt-1 break-words text-[9px] leading-relaxed text-text-muted">
              {last.message}
            </p>
          ) : null}

          {error ? <p className="mt-1.5 text-[10px] text-cosmic-error">{error}</p> : null}
        </>
      )}

      <div className="mt-2 flex items-center justify-between border-t border-border/50 pt-2">
        <span className="text-[10px] text-text-tertiary">Updated</span>
        <span className="font-mono text-[10px] text-text-muted">
          {updatedAt ?? '—'}
          {isLoading ? <span className="ml-1 text-text-muted">· syncing</span> : null}
        </span>
      </div>
    </motion.div>
  )
}