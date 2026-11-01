import React, { useCallback, useState } from 'react'
import { motion } from 'framer-motion'
import { useAriaNucleus } from '../../hooks/useAriaNucleus'

export function EvolutionPanel() {
  const nucleus = useAriaNucleus()
  const [osd, setOsd] = useState<{ title: string; sub: string; type: 'sacrifice' | 'evolve' } | null>(null)

  const showOsd = useCallback((title: string, sub: string, type: 'sacrifice' | 'evolve') => {
    setOsd({ title, sub, type })
    setTimeout(() => setOsd(null), 3000)
  }, [])

  const handleSacrifice = async (donorId: string, targetId: string) => {
    const res = await nucleus.sacrifice(donorId, targetId)
    if (res.ok) {
      showOsd('Evolución completada', `Se sacrificó ${res.sacrificed} → ${res.evolved} (nivel ${res.new_level})`, 'evolve')
    } else {
      showOsd('Sacrificio bloqueado', res.error ?? 'No se pudo completar', 'sacrifice')
    }
  }

  if (nucleus.loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-accent-cyan border-opacity-50 animate-spin mb-2" />
        <span className="text-[11px] text-text-tertiary">Cargando núcleo…</span>
      </div>
    )
  }

  if (!nucleus.online) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-4">
        <span className="text-[11px] text-text-tertiary mb-2">Backend no disponible</span>
        <button
          onClick={() => void nucleus.refresh()}
          className="btn-glow flex h-8 w-8 items-center justify-center rounded-lg text-text-tertiary hover:text-accent-cyan"
        >
          ↻
        </button>
      </div>
    )
  }

  const paths = nucleus.evolutionPaths
  const skillsById = new Map(nucleus.skills.map((s) => [s.id, s]))

  return (
    <div className="flex h-full flex-col p-4 gap-4">
      {/* OSD flotante */}
      {osd && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          className={`osd-notification ${osd.type}`}
        >
          <div className="osd-content">
            <span className="osd-icon">{osd.type === 'evolve' ? '✦' : '⚡'}</span>
            <div className="osd-text">
              <span className="osd-title">{osd.title}</span>
              <span className="osd-subtitle">{osd.sub}</span>
            </div>
          </div>
        </motion.div>
      )}

      <div className="flex-1 overflow-y-auto space-y-4">
        {/* Estado del núcleo */}
        <div className="sacrifice-panel p-4 fade-in-up">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[11px] font-semibold uppercase tracking-widest text-text-secondary">
              Núcleo ARIA
            </span>
            <span className="text-[11px] font-mono text-text-tertiary">
              {nucleus.status?.aspect ?? '—'}
            </span>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-text-tertiary">Estado</span>
              <span className="text-text-secondary">{nucleus.status?.state ?? '—'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-tertiary">Aspecto</span>
              <span className="text-text-secondary">{nucleus.status?.aspect ?? '—'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-tertiary">Sacrificios</span>
              <span className="text-text-secondary">{nucleus.status?.sacrifices ?? 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-tertiary">Evoluciones</span>
              <span className="text-text-secondary">{nucleus.status?.evolutions ?? 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-tertiary">Análisis</span>
              <span className="text-text-secondary">{nucleus.status?.analyses ?? 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-tertiary">Transformaciones</span>
              <span className="text-text-secondary">{nucleus.status?.transformations ?? 0}</span>
            </div>
          </div>
          <div className="mt-3 flex items-center gap-2 pt-3 border-t border-white/5">
            <span className="text-[10px] text-text-tertiary">Uptime</span>
            <span className="text-[11px] font-mono text-accent-cyan">{nucleus.status?.uptime_s?.toFixed(1) ?? '0'}s</span>
          </div>
        </div>

        {/* Cadenas de evolución */}
        <div className="space-y-3 fade-in-up">
          <span className="text-[11px] font-semibold uppercase tracking-widest text-text-secondary">
            Cadenas de Evolución
          </span>

          {paths.length === 0 ? (
            <p className="text-[11px] text-text-tertiary">Sin cadenas de evolución registradas.</p>
          ) : (
            <div className="space-y-3">
              {paths.map((path) => (
                <div key={path.root} className="evolution-chain">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-medium text-text-tertiary uppercase">
                      Nodo raíz: {path.root}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {path.chain.map((node, i) => {
                      const skill = skillsById.get(node.id)
                      const isLast = i === path.chain.length - 1
                      return (
                        <React.Fragment key={node.id}>
                          <div className={`evolution-node ${node.unlocked ? '' : 'locked'} ${node.active ? 'active' : ''}`}>
                            <span className="evolution-node-icon">{skill?.icon ?? '◇'}</span>
                            <div className="evolution-node-info">
                              <span className="evolution-node-name">{node.name}</span>
                              <span className="evolution-node-level">
                                Nivel {node.level} · {node.unlocked ? 'Desbloqueado' : 'Bloqueado'}
                              </span>
                            </div>
                            {!isLast && (
                              <span className="evolution-node-cost">
                                {node.sacrifice_cost ? `◆ ${node.sacrifice_cost}` : '—'}
                              </span>
                            )}
                          </div>
                          {!isLast && (
                            <motion.span
                              className="evolution-arrow"
                              initial={{ opacity: 0 }}
                              animate={{ opacity: 1 }}
                              transition={{ delay: i * 0.1 }}
                            >
                              ▸
                            </motion.span>
                          )}
                        </React.Fragment>
                      )
                    })}
                  </div>
                  {path.chain.length > 1 && (
                    <div className="mt-2 flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          const donor = path.chain[0]
                          const target = path.chain[1]
                          if (donor && target) {
                            void handleSacrifice(donor.id, target.id)
                          }
                        }}
                        disabled={!path.chain[0]?.unlocked || !path.chain[1]?.sacrifice_cost}
                        className={`sacrifice-btn ${!path.chain[0]?.unlocked || !path.chain[1]?.sacrifice_cost ? 'disabled' : ''}`}
                      >
                        ⚡ Sacrificar {path.chain[0]?.name} → {path.chain[1]?.name}
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Lista de skills */}
        <div className="space-y-3 fade-in-up">
          <span className="text-[11px] font-semibold uppercase tracking-widest text-text-secondary">
            Habilidades del Núcleo ({nucleus.skills.length})
          </span>
          <div className="skill-list flex-1 space-y-1.5 overflow-y-auto max-h-48 pr-1">
            {nucleus.skills.map((skill) => {
              const unlocked = skill.unlocked
              return (
                <motion.button
                  key={skill.id}
                  type="button"
                  whileHover={{ x: 2 }}
                  whileTap={{ scale: 0.97 }}
                  className={`skill-item ${unlocked ? 'skill-item-on' : ''}`}
                  disabled={!unlocked}
                >
                  <span className="skill-dot" />
                  <span className="flex-1 truncate">
                    {skill.name}
                    <span className="ml-1 text-[9px] opacity-60">L{skill.level}</span>
                  </span>
                  <span className="text-[10px] font-mono">
                    {unlocked ? skill.uses : '—'} usos
                  </span>
                </motion.button>
              )
            })}
            {nucleus.skills.length === 0 && (
              <p className="px-1 py-2 text-[11px] text-text-tertiary">Sin habilidades</p>
            )}
          </div>
        </div>
      </div>

      {nucleus.error && (
        <div className="p-2 rounded-lg bg-red-500/10 border border-red-500/20 text-[11px] text-red-400">
          {nucleus.error}
        </div>
      )}
    </div>
  )
}
