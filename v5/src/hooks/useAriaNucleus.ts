import { useCallback, useEffect, useMemo, useState } from 'react'

export type AriaAspectName = 'gran_sabio' | 'raphael' | 'ciel' | 'fused'

export interface AriaSkillView {
  id: string
  name: string
  category: string
  level: number
  description: string
  icon: string
  cost: Record<string, unknown>
  effects: Array<{ type: string; value: unknown; description: string }>
  evolved_from: string | null
  evolves_to: string | null
  sacrifice_target: string | null
  sacrifice_cost: string | null
  unlocked: boolean
  active: boolean
  xp: number
  uses: number
  max_level: number
  aspect_required: string | null
}

export interface AriaEvolutionLink {
  id: string
  name: string
  level: number
  unlocked: boolean
  active: boolean
  evolves_to: string | null
  sacrifice_cost: string | null
}

export interface AriaEvolutionPath {
  root: string
  chain: AriaEvolutionLink[]
}

export interface AriaStatus {
  identity: string
  mode: string
  state: string
  aspect: string
  uptime_s: number
  thoughts: number
  actions: number
  observations: number
  errors: number
  sacrifices: number
  evolutions: number
  analyses: number
  transformations: number
  session_id: string
  ts: string
}

export interface AriaNucleusState {
  status: AriaStatus | null
  skills: AriaSkillView[]
  evolutionPaths: AriaEvolutionPath[]
  loading: boolean
  error: string | null
  online: boolean
  setAspect: (aspect: AriaAspectName) => Promise<{ ok: boolean; aspect?: string; error?: string }>
  activateSkill: (skillId: string) => Promise<{ ok: boolean; active?: boolean; error?: string }>
  deactivateSkill: (skillId: string) => Promise<{ ok: boolean; active?: boolean; error?: string }>
  sacrifice: (donorId: string, targetId: string) => Promise<{ ok: boolean; sacrificed?: string; evolved?: string; error?: string; new_level?: number }>
  analyze: (subject: string, depth?: number, aspect?: AriaAspectName) => Promise<any>
  transform: (target: string, into: string) => Promise<any>
  refresh: () => Promise<void>
}

const API_ORIGIN = 'http://127.0.0.1:8000'

async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_ORIGIN}${path}`, { method: 'GET' })
  if (!res.ok) throw new Error(`GET ${path} -> ${res.status}`)
  return res.json() as T
}

async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_ORIGIN}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`POST ${path} -> ${res.status}`)
  return res.json() as T
}

export function useAriaNucleus(): AriaNucleusState {
  const [state, setState] = useState<AriaNucleusState>({
    status: null,
    skills: [],
    evolutionPaths: [],
    loading: true,
    error: null,
    online: false,
    setAspect: async () => ({ ok: false, error: 'not_ready' }),
    activateSkill: async () => ({ ok: false, error: 'not_ready' }),
    deactivateSkill: async () => ({ ok: false, error: 'not_ready' }),
    sacrifice: async () => ({ ok: false, error: 'not_ready' }),
    analyze: async () => ({}),
    transform: async () => ({}),
    refresh: async () => {},
  })

  const refresh = useCallback(async () => {
    try {
      const [statusResp, skillsResp, pathsResp] = await Promise.all([
        apiGet<{ ok: boolean; status: AriaStatus }>('/aria/nucleus/status'),
        apiGet<{ ok: boolean; skills: AriaSkillView[] }>('/aria/nucleus/skills'),
        apiGet<{ ok: boolean; paths: AriaEvolutionPath[] }>('/aria/nucleus/evolution-paths'),
      ])

      setState((prev) => ({
        ...prev,
        status: statusResp.ok ? statusResp.status : null,
        skills: skillsResp.ok ? skillsResp.skills : [],
        evolutionPaths: pathsResp.ok ? pathsResp.paths : [],
        loading: false,
        error: null,
        online: true,
      }))
    } catch (error) {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: error instanceof Error ? error.message : String(error),
        online: false,
      }))
    }
  }, [])

  useEffect(() => {
    void refresh()
    const id = setInterval(() => void refresh(), 4000)
    return () => clearInterval(id)
  }, [refresh])

  const setAspect = useCallback(
    async (aspect: AriaAspectName) => {
      try {
        const res = await apiPost<{ ok: boolean; aspect?: string; error?: string }>(
          '/aria/nucleus/aspect',
          { aspect },
        )
        if (res.ok) await refresh()
        return res
      } catch (error) {
        return { ok: false, error: error instanceof Error ? error.message : String(error) }
      }
    },
    [refresh],
  )

  const activateSkill = useCallback(
    async (skillId: string) => {
      try {
        const res = await apiPost<{ ok: boolean; active?: boolean; error?: string }>(
          '/aria/nucleus/skills/activate',
          { skill_id: skillId },
        )
        if (res.ok) await refresh()
        return res
      } catch (error) {
        return { ok: false, error: error instanceof Error ? error.message : String(error) }
      }
    },
    [refresh],
  )

  const deactivateSkill = useCallback(
    async (skillId: string) => {
      try {
        const res = await apiPost<{ ok: boolean; active?: boolean; error?: string }>(
          '/aria/nucleus/skills/deactivate',
          { skill_id: skillId },
        )
        if (res.ok) await refresh()
        return res
      } catch (error) {
        return { ok: false, error: error instanceof Error ? error.message : String(error) }
      }
    },
    [refresh],
  )

  const sacrifice = useCallback(
    async (donorId: string, targetId: string) => {
      try {
        const res = await apiPost<{ ok: boolean; sacrificed?: string; evolved?: string; error?: string; new_level?: number }>(
          '/aria/nucleus/skills/sacrifice',
          { donor_id: donorId, target_id: targetId },
        )
        if (res.ok) await refresh()
        return res
      } catch (error) {
        return { ok: false, error: error instanceof Error ? error.message : String(error) }
      }
    },
    [refresh],
  )

  const analyze = useCallback(
    async (subject: string, depth = 3, aspect?: AriaAspectName) => {
      try {
        return await apiPost<{ ok: boolean; [key: string]: unknown }>('/aria/nucleus/analyze', {
          subject,
          depth,
          aspect,
        })
      } catch (error) {
        return { ok: false, error: error instanceof Error ? error.message : String(error) }
      }
    },
    [],
  )

  const transform = useCallback(
    async (target: string, into: string) => {
      try {
        return await apiPost<{ ok: boolean; [key: string]: unknown }>('/aria/nucleus/transform', {
          target,
          into,
        })
      } catch (error) {
        return { ok: false, error: error instanceof Error ? error.message : String(error) }
      }
    },
    [],
  )

  return useMemo(
    () => ({
      ...state,
      refresh,
      setAspect,
      activateSkill,
      deactivateSkill,
      sacrifice,
      analyze,
      transform,
    }),
    [state, refresh, setAspect, activateSkill, deactivateSkill, sacrifice, analyze, transform],
  )
}
