import { useCallback, useMemo, useState } from 'react'
import type { Dispatch, SetStateAction } from 'react'

export type OrbPhase = 'idle' | 'thinking' | 'responding' | 'listening' | 'wisdom'

export interface OrbPhaseTheme {
  primary: string
  glow: string
  label: string
}

/** Estados y colores del orbe (Serpantinum · Caelestia palette) */
export const orbStates: Record<OrbPhase, OrbPhaseTheme> = {
  idle: { primary: '#38bdf8', glow: 'rgba(56, 189, 248, 0.8)', label: 'Ready' },
  thinking: { primary: '#f59e0b', glow: 'rgba(245, 158, 11, 0.8)', label: 'Processing' },
  responding: { primary: '#00d4ff', glow: 'rgba(0, 212, 255, 1)', label: 'Speaking' },
  listening: { primary: '#b066ff', glow: 'rgba(176, 102, 255, 0.8)', label: 'Listening' },
  wisdom: { primary: '#ffffff', glow: 'rgba(167, 139, 234, 0.95)', label: 'Gran Sabio' },
}

export interface OrbStateController {
  orbState: OrbPhase
  setOrbState: Dispatch<SetStateAction<OrbPhase>>
  colors: OrbPhaseTheme
  pulse: (phase: OrbPhase, ms?: number) => void
}

export function useOrbState(initial: OrbPhase = 'idle'): OrbStateController {
  const [orbState, setOrbState] = useState<OrbPhase>(initial)
  const colors = useMemo(() => orbStates[orbState], [orbState])

  /** Muestra una fase temporalmente y vuelve a idle */
  const pulse = useCallback((phase: OrbPhase, ms = 1600) => {
    setOrbState(phase)
    window.setTimeout(() => setOrbState('idle'), ms)
  }, [])

  return { orbState, setOrbState, colors, pulse }
}
