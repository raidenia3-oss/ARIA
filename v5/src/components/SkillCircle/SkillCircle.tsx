import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'

export interface Skill {
  name: string
  description: string
  category: string
  enabled: boolean
  level: number
  xp: number
  xp_max: number
}

export interface SkillProgressionState {
  skills: Skill[]
  total_xp: number
  level: number
  unlocked: number
}

function useSkillSystem(): SkillProgressionState {
  const [state, setState] = useState<SkillProgressionState>({
    skills: [],
    total_xp: 0,
    level: 1,
    unlocked: 0,
  })

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const res = await fetch('/api/agents/harness/skills')
        const data = await res.json()
        if (cancelled) return
        const rawSkills = data.skills || []
        const skills: Skill[] = rawSkills.map((s: Record<string, unknown>, i: number) => ({
          name: String(s.name || `skill_${i}`),
          description: String(s.description || ''),
          category: String(s.category || 'system'),
          enabled: Boolean(s.enabled ?? true),
          level: 1,
          xp: 0,
          xp_max: 100,
        }))
        const total_xp = skills.reduce((sum, s) => sum + s.xp, 0)
        const level = Math.floor(total_xp / 500) + 1
        setState({ skills, total_xp, level, unlocked: skills.filter((s) => s.enabled).length })
      } catch {
        /* fallback */
      }
    }
    load()
    const id = setInterval(load, 5000)
    return () => { cancelled = true; clearInterval(id) }
  }, [])
  return state
}

const CATEGORY_COLORS: Record<string, string> = {
  system: '#38bdf8',
  web: '#a78bfa',
  files: '#34d399',
  research: '#f59e0b',
  brain: '#f472b6',
  integration: '#60a5fa',
  improvement: '#fbbf24',
}

export function SkillCircle() {
  const state = useSkillSystem()
  const radius = 140
  const circumference = 2 * Math.PI * radius

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative h-[320px] w-[320px]">
        <svg viewBox="0 0 320 320" className="h-full w-full">
          <defs>
            <filter id="skillGlow">
              <feGaussianBlur stdDeviation="2" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Background ring */}
          <circle cx={160} cy={160} r={radius} fill="none"
            stroke="#1e293b" strokeWidth="8" />

          {/* Level progress ring */}
          <circle cx={160} cy={160} r={radius} fill="none"
            stroke="#38bdf8" strokeWidth="8"
            strokeDasharray={circumference}
            strokeDashoffset={circumference * (1 - state.skills.length ? 0.65 : 0)}
            strokeLinecap="round"
            transform="rotate(-90 160 160)"
            filter="url(#skillGlow)"
            style={{ transition: 'strokeDashoffset 0.8s ease' }}
          />

          {/* Center stats */}
          <text x={160} y={150} textAnchor="middle" fill="#e2e8f0"
            fontSize="32" fontFamily="monospace" fontWeight="bold">
            LVL {state.level}
          </text>
          <text x={160} y={175} textAnchor="middle" fill="#64748b"
            fontSize="11" fontFamily="monospace">
            {state.unlocked} skills · {state.total_xp} XP
          </text>
        </svg>

        {/* Skill dots around circle */}
        {state.skills.slice(0, 8).map((skill, i) => {
          const angle = (i / Math.max(state.skills.length, 8)) * Math.PI * 2 - Math.PI / 2
          const ax = 160 + Math.cos(angle) * radius
          const ay = 160 + Math.sin(angle) * radius
          const color = CATEGORY_COLORS[skill.category] || '#64748b'
          return (
            <motion.div
              key={skill.name}
              className="absolute flex h-6 w-6 items-center justify-center rounded-full"
              style={{
                left: ax - 12,
                top: ay - 12,
                backgroundColor: skill.enabled ? color : '#1e293b',
                border: `2px solid ${color}`,
                boxShadow: skill.enabled ? `0 0 8px ${color}` : 'none',
              }}
              whileHover={{ scale: 1.3 }}
              title={`${skill.name} (${skill.category}) LVL ${skill.level}`}
            >
              {skill.enabled && (
                <div className="h-1.5 w-1.5 rounded-full bg-white" />
              )}
            </motion.div>
          )
        })}
      </div>

      {/* Skill list */}
      <div className="w-full max-w-xs space-y-1.5">
        {state.skills.slice(0, 6).map((skill) => {
          const color = CATEGORY_COLORS[skill.category] || '#64748b'
          return (
            <div key={skill.name} className="flex items-center gap-2 text-xs">
              <span className="h-2 w-2 rounded-full"
                style={{ backgroundColor: skill.enabled ? color : '#334155' }} />
              <span className="flex-1 truncate text-text-secondary">{skill.name}</span>
              <span className="text-[10px] text-text-tertiary">{skill.category}</span>
              <span className="text-[10px]" style={{ color }}>
                L{skill.level}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}