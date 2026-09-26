import { motion } from 'framer-motion'
import type { Settings, ThemeName } from '../../hooks/useSettings'
import { THEME_ACCENTS } from '../../hooks/useSettings'

export interface ControlCenterProps {
  settings: Settings
  onUpdate: (partial: Partial<Settings>) => void
  onClose: () => void
}

interface ToggleProps {
  label: string
  hint?: string
  checked: boolean
  onChange: (value: boolean) => void
}

function Toggle({ label, hint, checked, onChange }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className="toggle-row"
    >
      <span className="flex flex-col items-start gap-0.5">
        <span className="text-[12px] text-text-secondary">{label}</span>
        {hint && <span className="text-[10px] text-text-tertiary">{hint}</span>}
      </span>
      <span className={checked ? 'toggle-track toggle-track-on' : 'toggle-track'}>
        <motion.span layout className="toggle-knob" />
      </span>
    </button>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-4">
      <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-accent-cyan">{title}</h3>
      <div className="space-y-1">{children}</div>
    </section>
  )
}

const THEMES: Array<{ id: ThemeName; label: string }> = [
  { id: 'cyan', label: 'Cyan' },
  { id: 'purple', label: 'Purple' },
  { id: 'green', label: 'Green' },
  { id: 'orange', label: 'Orange' },
]

export function ControlCenter({ settings, onUpdate, onClose }: ControlCenterProps) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-2.5">
        <span className="text-[12px] font-semibold uppercase tracking-widest text-text-secondary">
          ⚙ Control
        </span>
        <motion.button
          whileHover={{ scale: 1.1, rotate: 90 }}
          whileTap={{ scale: 0.9 }}
          onClick={onClose}
          className="btn-glow no-drag flex h-6 w-6 items-center justify-center rounded-md text-text-tertiary hover:text-accent-cyan"
          aria-label="Cerrar control center"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5">
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </motion.button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <Section title="Visual">
          <Toggle
            label="Animaciones 3D"
            hint="Orbe, partículas y transiciones"
            checked={settings.animations}
            onChange={(animations) => onUpdate({ animations })}
          />
          <Toggle
            label="Glassmorphism"
            hint="Blur real sobre los paneles"
            checked={settings.glassmorphism}
            onChange={(glassmorphism) => onUpdate({ glassmorphism })}
          />
          <Toggle
            label="Streaming"
            hint="Respuesta carácter a carácter"
            checked={settings.streaming}
            onChange={(streaming) => onUpdate({ streaming })}
          />
        </Section>

        <Section title="Notificaciones">
          <Toggle
            label="Sonidos"
            hint="Blip al enviar mensajes"
            checked={settings.soundEnabled}
            onChange={(soundEnabled) => onUpdate({ soundEnabled })}
          />
          <Toggle
            label="Vibración"
            hint="Feedback háptico (si está soportado)"
            checked={settings.vibration}
            onChange={(vibration) => onUpdate({ vibration })}
          />
        </Section>

        <Section title="Opacidad">
          <div className="toggle-row flex-col items-stretch gap-2">
            <div className="flex items-center justify-between">
              <span className="text-[12px] text-text-secondary">Ventana</span>
              <span className="text-[11px] text-accent-cyan">{settings.opacity}%</span>
            </div>
            <input
              type="range"
              min={20}
              max={100}
              value={settings.opacity}
              onChange={(event) => onUpdate({ opacity: Number(event.target.value) })}
              className="opacity-slider no-drag"
              aria-label="Opacidad de la ventana"
            />
          </div>
        </Section>

        <Section title="Tema">
          <div className="flex items-center gap-2">
            {THEMES.map((theme) => {
              const accent = THEME_ACCENTS[theme.id]
              const active = settings.theme === theme.id
              return (
                <motion.button
                  key={theme.id}
                  whileHover={{ scale: 1.08 }}
                  whileTap={{ scale: 0.94 }}
                  onClick={() => onUpdate({ theme: theme.id })}
                  title={theme.label}
                  aria-label={`Tema ${theme.label}`}
                  className={active ? 'theme-swatch theme-swatch-on' : 'theme-swatch'}
                  style={{
                    background: `linear-gradient(135deg, ${accent.accent}, ${accent.bright})`,
                    boxShadow: active ? `0 0 12px ${accent.accent}` : undefined,
                  }}
                />
              )
            })}
          </div>
        </Section>

        <p className="mt-2 text-[10px] leading-relaxed text-text-tertiary">
          Los cambios se aplican al instante. La configuración se guarda localmente y en `settings.json`
          del usuario cuando corre dentro de Electron.
        </p>
      </div>
    </div>
  )
}
