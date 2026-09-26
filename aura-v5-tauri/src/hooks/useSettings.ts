import { useCallback, useEffect, useState } from 'react'

export type ThemeName = 'cyan' | 'purple' | 'green' | 'orange'

export interface Settings {
  animations: boolean
  glassmorphism: boolean
  streaming: boolean
  soundEnabled: boolean
  vibration: boolean
  opacity: number
  theme: ThemeName
}

export const DEFAULT_SETTINGS: Settings = {
  animations: true,
  glassmorphism: true,
  streaming: true,
  soundEnabled: true,
  vibration: false,
  opacity: 100,
  theme: 'cyan',
}

const STORAGE_KEY = 'aria-v5-settings'

/** Acentos por tema — se aplican como CSS variables en :root */
export const THEME_ACCENTS: Record<ThemeName, { accent: string; bright: string; rgb: string }> = {
  cyan: { accent: '#38bdf8', bright: '#00d4ff', rgb: '56, 189, 248' },
  purple: { accent: '#b066ff', bright: '#c89bff', rgb: '176, 102, 255' },
  green: { accent: '#00ff88', bright: '#66ffb3', rgb: '0, 255, 136' },
  orange: { accent: '#ff6b4a', bright: '#ff9b7a', rgb: '255, 107, 74' },
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

  const updateSettings = useCallback((partial: Partial<Settings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...partial }
      try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      } catch {
        /* almacenamiento no disponible */
      }
      return next
    })
  }, [])

  // Live preview: tema, opacidad y efectos se aplican al documento
  useEffect(() => {
    const root = document.documentElement
    const theme = THEME_ACCENTS[settings.theme] ?? THEME_ACCENTS.cyan
    root.style.setProperty('--color-accent-cyan', theme.accent)
    root.style.setProperty('--color-accent-cyan-bright', theme.bright)
    root.style.setProperty('--accent-rgb', theme.rgb)
    root.classList.toggle('no-glass', !settings.glassmorphism)
    root.classList.toggle('no-anim', !settings.animations)
  }, [settings])

  return { settings, updateSettings }
}