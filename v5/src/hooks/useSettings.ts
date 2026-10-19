import { useCallback, useEffect, useState } from 'react'

export type ThemeName = 'cyan' | 'purple' | 'green' | 'orange' | 'gran_sabio' | 'raphael' | 'ciel' | 'fused'

export interface Settings {
  animations: boolean
  glassmorphism: boolean
  streaming: boolean
  soundEnabled: boolean
  vibration: boolean
  opacity: number
  theme: ThemeName
  aspect: 'gran_sabio' | 'raphael' | 'ciel' | 'fused'
}

export const DEFAULT_SETTINGS: Settings = {
  animations: true,
  glassmorphism: true,
  streaming: true,
  soundEnabled: true,
  vibration: false,
  opacity: 100,
  theme: 'fused',
  aspect: 'fused',
}

const STORAGE_KEY = 'aria-v5-settings'

/** Acentos por tema/aspecto — aplicados como CSS variables en :root */
export const THEME_ACCENTS: Record<ThemeName, { accent: string; bright: string; rgb: string }> = {
  cyan: { accent: '#38bdf8', bright: '#00d4ff', rgb: '56, 189, 248' },
  purple: { accent: '#b066ff', bright: '#c89bff', rgb: '176, 102, 255' },
  green: { accent: '#00ff88', bright: '#66ffb3', rgb: '0, 255, 136' },
  orange: { accent: '#ff6b4a', bright: '#ff9b7a', rgb: '255, 107, 74' },
  gran_sabio: { accent: '#60a5fa', bright: '#93c5fd', rgb: '96, 165, 250' },
  raphael: { accent: '#4ade80', bright: '#86efac', rgb: '74, 222, 128' },
  ciel: { accent: '#a78bfa', bright: '#c4b5fd', rgb: '167, 139, 250' },
  fused: { accent: '#818cf8', bright: '#a5b4fc', rgb: '129, 140, 248' },
}

/** Colores del orbe por fase/aspecto (Gran Sabio · Raphael · Ciel) */
export const ORB_ASPECT_COLORS: Record<'gran_sabio' | 'raphael' | 'ciel' | 'fused', { core: string; glow: string; eye: string }> = {
  gran_sabio: { core: '#60a5fa', glow: '#3b82f6', eye: '#bfdbfe' },
  raphael: { core: '#4ade80', glow: '#22c55e', eye: '#bbf7d0' },
  ciel: { core: '#a78bfa', glow: '#8b5cf6', eye: '#ddd6fe' },
  fused: { core: '#818cf8', glow: '#6366f1', eye: '#c7d2fe' },
}

function loadLocal(): Partial<Settings> {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as Partial<Settings>) : {}
  } catch {
    return {}
  }
}

export interface SettingsController {
  settings: Settings
  updateSettings: (partial: Partial<Settings>) => void
}

export function useSettings(): SettingsController {
  const [settings, setSettings] = useState<Settings>({ ...DEFAULT_SETTINGS, ...loadLocal() })

  useEffect(() => {
    const api = window.electronAPI
    if (!api?.settingsGet) return
    let cancelled = false
    api
      .settingsGet()
      .then((remote) => {
        if (cancelled || !remote || Object.keys(remote).length === 0) return
        setSettings((prev) => ({ ...prev, ...(remote as Partial<Settings>) }))
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [])

  const updateSettings = useCallback((partial: Partial<Settings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...partial }
      try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      } catch {
        /* almacenamiento no disponible */
      }
      void window.electronAPI?.settingsSet?.(next)
      return next
    })
  }, [])

  useEffect(() => {
    const root = document.documentElement
    const theme = THEME_ACCENTS[settings.theme] ?? THEME_ACCENTS.fused
    root.style.setProperty('--color-accent-cyan', theme.accent)
    root.style.setProperty('--color-accent-cyan-bright', theme.bright)
    root.style.setProperty('--accent-rgb', theme.rgb)
    // aspect → variable de aspecto activo
    const aspect = ORB_ASPECT_COLORS[settings.aspect] ?? ORB_ASPECT_COLORS.fused
    root.style.setProperty('--aspect-core', aspect.core)
    root.style.setProperty('--aspect-glow', aspect.glow)
    root.style.setProperty('--aspect-eye', aspect.eye)
    root.classList.toggle('no-glass', !settings.glassmorphism)
    root.classList.toggle('no-anim', !settings.animations)
    root.classList.remove('aspect-gran_sabio', 'aspect-raphael', 'aspect-ciel', 'aspect-fused')
    root.classList.add(`aspect-${settings.aspect}`)
    void window.electronAPI?.windowSetOpacity?.(settings.opacity)
  }, [settings])

  return { settings, updateSettings }
}
