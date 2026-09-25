import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'

export interface SkillItem {
  name: string
  description: string
}

/** Fallback si el backend no responde (25 skills de ARIA v4) */
const FALLBACK_SKILLS: string[] = [
  'status',
  'time',
  'ping',
  'scan',
  'whois',
  'open',
  'volume',
  'lock',
  'apps',
  'screenshot',
  'memory',
  'search',
  'weather',
  'list',
  'read',
  'write',
  'working',
  'short_term',
  'long_term',
  'proactive',
  'evolution',
  'learning',
  'personality',
  'voice',
  'vision',
]

function normalizeSkills(raw: unknown): SkillItem[] {
  const container = raw as { skills?: unknown[] } | unknown[] | null
  const list: unknown[] = Array.isArray(container)
    ? container
    : Array.isArray(container?.skills)
      ? (container as { skills: unknown[] }).skills
      : []

  const result: SkillItem[] = []
  for (const entry of list) {
    if (typeof entry === 'string') {
      result.push({ name: entry, description: '' })
      continue
    }
    if (entry && typeof entry === 'object') {
      const record = entry as Record<string, unknown>
      const name = record.name ?? record.id ?? record.skill
      if (typeof name === 'string' && name.length > 0) {
        result.push({
          name,
          description: typeof record.description === 'string' ? record.description : '',
        })
      }
    }
  }
  return result
}

export function SkillsSidebar() {
  const [skills, setSkills] = useState<SkillItem[]>(
    FALLBACK_SKILLS.map((name) => ({ name, description: '' }))
  )
  const [enabled, setEnabled] = useState<Set<string>>(() => new Set(FALLBACK_SKILLS))
  const [query, setQuery] = useState('')
  const [live, setLive] = useState(false)

  useEffect(() => {
    const api = window.electronAPI
    if (!api?.skillsLoad) return
    let cancelled = false
    api
      .skillsLoad()
      .then((raw) => {
        if (cancelled) return
        const normalized = normalizeSkills(raw)
        if (normalized.length === 0) return
        setSkills(normalized)
        setEnabled(new Set(normalized.map((item) => item.name)))
        setLive(true)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [])

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return skills
    return skills.filter((skill) => skill.name.toLowerCase().includes(needle))
  }, [skills, query])

  const toggle = (name: string) => {
    setEnabled((prev) => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  return (
    <div className="flex h-full w-[168px] min-w-[168px] flex-col p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-widest text-accent-cyan">
          ◇ Skills
        </span>
        <span className="text-[10px] text-text-tertiary">
          {enabled.size}/{skills.length}
        </span>
      </div>

      <div className="h-px w-full bg-white/10" />

      <input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Filtrar..."
        className="no-drag my-2 w-full rounded-lg bg-black/25 px-2 py-1.5 text-[11px] text-text-secondary outline-none placeholder-text-tertiary focus:ring-1 focus:ring-accent-cyan"
        aria-label="Filtrar skills"
      />

      <div className="skill-list flex-1 space-y-1.5 overflow-y-auto pr-1">
        {filtered.map((skill) => {
          const checked = enabled.has(skill.name)
          return (
            <motion.button
              key={skill.name}
              type="button"
              whileHover={{ x: 2 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => toggle(skill.name)}
              title={skill.description || skill.name}
              className={checked ? 'skill-item skill-item-on' : 'skill-item'}
              aria-pressed={checked}
            >
              <span className="skill-dot" />
              <span className="truncate">{skill.name}</span>
            </motion.button>
          )
        })}

        {filtered.length === 0 && (
          <p className="px-1 py-2 text-[11px] text-text-tertiary">Sin resultados</p>
        )}
      </div>

      <div className="mt-2 text-[10px] text-text-tertiary">
        {live ? `${skills.length} skills activas` : 'lista local (backend offline)'}
      </div>
    </div>
  )
}
