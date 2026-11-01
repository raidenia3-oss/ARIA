import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useSkillTree } from '../../hooks/useSkillTree'
import type { SkillTreeNode } from '../../lib/ariaBackend'
import { ClassSelect } from './ClassSelect'
import { TreeGraph } from './TreeGraph'
import styles from './styles.module.css'

/**
 * Árbol de habilidades de ARIA.
 *
 * Cada nodo es una capacidad real; desbloquearla cuesta puntos que se ganan
 * usando otras capacidades. El servidor es la autoridad del estado: esta UI
 * nunca inventa niveles ni desbloqueos.
 */
export function SkillTree() {
  const tree = useSkillTree()
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const selected: SkillTreeNode | undefined = selectedId ? tree.nodeById(selectedId) : undefined

  // Al recargar, si el nodo seleccionado ya no existe, se suelta la selección
  // en vez de dejar un panel vacío.
  useEffect(() => {
    if (selectedId && !tree.nodeById(selectedId)) setSelectedId(null)
  }, [selectedId, tree])

  if (tree.loading) {
    return (
      <div className={styles.loading}>
        <span className={styles.spinner} />
        Cargando árbol de habilidades…
      </div>
    )
  }

  if (!tree.online) {
    return (
      <div className={styles.loading}>
        <span className={styles.offline}>●</span> Backend ARIA no disponible ({tree.error})
      </div>
    )
  }

  const progression = tree.progression
  const hasClass = Boolean(progression?.class)

  return (
    <div className={styles.container}>
      {!hasClass ? (
        <ClassSelect
          classes={tree.classes}
          branches={tree.branches}
          busy={Boolean(tree.mutationError)}
          onChoose={(id) => void tree.chooseClass(id)}
        />
      ) : (
        <>
          <header className={styles.header}>
            <div className={styles.levelBlock}>
              <span className={styles.levelLabel}>NIVEL</span>
              <span className={styles.levelValue}>{progression?.level ?? 1}</span>
            </div>

            <div className={styles.xpBlock}>
              <div className={styles.xpTrack}>
                <motion.div
                  className={styles.xpFill}
                  animate={{ width: `${xpPercent(progression)}%` }}
                  transition={{ duration: 0.6, ease: 'easeOut' }}
                />
              </div>
              <span className={styles.xpText}>
                {progression?.xp_into_level ?? 0} / {progression?.xp_for_next_level ?? 0} XP
                {progression && progression.xp_to_next > 0 && (
                  <span className={styles.xpRemaining}> · faltan {progression.xp_to_next}</span>
                )}
              </span>
            </div>

            <div className={styles.pointsBlock}>
              <span className={styles.pointsLabel}>PUNTOS</span>
              <span className={styles.pointsValue}>{progression?.points ?? 0}</span>
            </div>

            <div className={styles.equippedBlock}>
              <span className={styles.equippedLabel}>EQUIPADAS</span>
              <div className={styles.equippedSlots}>
                {Array.from({ length: progression?.max_equipped ?? 3 }).map((_, i) => {
                  const id = progression?.equipped[i]
                  const node = id ? tree.nodeById(id) : undefined
                  return (
                    <button
                      key={i}
                      type="button"
                      className={`${styles.equippedSlot} ${node ? styles.equippedSlotFilled : ''}`}
                      onClick={() => node && setSelectedId(node.id)}
                      title={node ? node.name : 'Espacio libre'}
                    >
                      {node ? node.icon : '·'}
                    </button>
                  )
                })}
              </div>
            </div>

            <button
              type="button"
              className={styles.resetButton}
              onClick={() => {
                if (window.confirm('¿Reiniciar el árbol de habilidades? Se pierde todo el progreso.')) {
                  void tree.reset()
                }
              }}
            >
              Reiniciar
            </button>
          </header>

          <div className={styles.body}>
            <TreeGraph
              nodes={tree.nodes}
              branches={tree.branches}
              onSelect={(node) => setSelectedId(node.id)}
              branchColor={tree.branchColor}
            />

            <aside className={styles.detail}>
              <AnimatePresence mode="wait">
                {selected ? (
                  <motion.div
                    key={selected.id}
                    initial={{ opacity: 0, x: 14 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 14 }}
                    transition={{ duration: 0.2 }}
                    className={styles.detailInner}
                  >
                    <div
                      className={styles.detailIcon}
                      style={{ '--accent': tree.branchColor(selected.branch) } as React.CSSProperties}
                    >
                      {selected.icon}
                    </div>
                    <h3 className={styles.detailName}>{selected.name}</h3>
                    <p className={styles.detailDescription}>{selected.description}</p>

                    <dl className={styles.detailStats}>
                      <div>
                        <dt>Rama</dt>
                        <dd>{tree.branches.find((b) => b.id === selected.branch)?.name ?? selected.branch}</dd>
                      </div>
                      <div>
                        <dt>Tipo</dt>
                        <dd>{selected.kind === 'active' ? 'Activa (equipar)' : 'Pasiva (siempre)'}</dd>
                      </div>
                      <div>
                        <dt>Coste</dt>
                        <dd>{selected.cost} ◆</dd>
                      </div>
                      <div>
                        <dt>XP al desbloquear</dt>
                        <dd>{selected.xp_reward}</dd>
                      </div>
                      {selected.uses > 0 && (
                        <div>
                          <dt>Usos</dt>
                          <dd>{selected.uses}</dd>
                        </div>
                      )}
                    </dl>

                    {selected.requires.length > 0 && (
                      <div className={styles.requires}>
                        <span className={styles.requiresLabel}>Requiere</span>
                        <div className={styles.requiresList}>
                          {selected.requires.map((req) => {
                            const node = tree.nodeById(req)
                            const ok = node?.unlocked ?? false
                            return (
                              <button
                                key={req}
                                type="button"
                                className={`${styles.requiresChip} ${ok ? styles.requiresOk : ''}`}
                                onClick={() => node && setSelectedId(node.id)}
                              >
                                {node?.icon ?? '·'} {node?.name ?? req}
                              </button>
                            )
                          })}
                        </div>
                      </div>
                    )}

                    {tree.mutationError && (
                      <p className={styles.error}>{tree.mutationError}</p>
                    )}

                    <div className={styles.detailActions}>
                      {selected.unlocked ? (
                        selected.kind === 'active' ? (
                          <button
                            type="button"
                            className={`${styles.action} ${selected.equipped ? styles.actionOff : ''}`}
                            onClick={() => void tree.equip(selected.id, !selected.equipped)}
                          >
                            {selected.equipped ? 'Desequipar' : 'Equipar'}
                          </button>
                        ) : (
                          <span className={styles.detailNote}>Habilidad pasiva activa</span>
                        )
                      ) : (
                        <button
                          type="button"
                          className={styles.action}
                          disabled={!selected.available}
                          onClick={() => void tree.unlock(selected.id)}
                        >
                          {selected.available ? 'Desbloquear' : (selected.blocked_by ?? 'Bloqueado')}
                        </button>
                      )}
                    </div>
                  </motion.div>
                ) : (
                  <motion.div
                    key="hint"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className={styles.detailHint}
                  >
                    <span className={styles.hintGlyph}>◈</span>
                    <p>Selecciona una habilidad del árbol para ver sus detalles.</p>
                    <p className={styles.hintSmall}>
                      Usa tus habilidades para ganar XP, sube de nivel y consigue puntos.
                    </p>
                  </motion.div>
                )}
              </AnimatePresence>
            </aside>
          </div>
        </>
      )}
    </div>
  )
}

/** Porcentaje de XP dentro del nivel actual, acotado a 0..100. */
function xpPercent(progression: { xp_into_level: number; xp_for_next_level: number } | null): number {
  if (!progression || progression.xp_for_next_level <= 0) return 0
  const pct = (progression.xp_into_level / progression.xp_for_next_level) * 100
  return Math.max(0, Math.min(100, pct))
}
