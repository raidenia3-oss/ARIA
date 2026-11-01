import { useMemo } from 'react'
import { motion } from 'framer-motion'
import type { SkillTreeBranch, SkillTreeClass } from '../../lib/ariaBackend'
import styles from './styles.module.css'

interface ClassSelectProps {
  classes: SkillTreeClass[]
  branches: SkillTreeBranch[]
  onChoose: (classId: string) => void
  busy: boolean
}

/**
 * Pantalla de reencarnación: la elección de clase.
 *
 * Es la primera decisión del jugador y no se puede cambiar después, así que
 * cada carta dice exactamente qué empieza desbloqueado y por qué.
 */
export function ClassSelect({ classes, branches, onChoose, busy }: ClassSelectProps) {
  const branchOf = useMemo(() => {
    const map = new Map<string, SkillTreeBranch>()
    for (const b of branches) map.set(b.id, b)
    return map
  }, [branches])

  return (
    <div className={styles.classScreen}>
      <motion.div
        initial={{ opacity: 0, y: -18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className={styles.classHeader}
      >
        <span className={styles.classKicker}>REINCARNACIÓN</span>
        <h2 className={styles.classTitle}>Elige el origen de ARIA</h2>
        <p className={styles.classSubtitle}>
          Esta decisión define cómo empieza tu árbol. No se puede cambiar más adelante.
        </p>
      </motion.div>

      <div className={styles.classGrid}>
        {classes.map((cls, index) => {
          const branch = branchOf.get(cls.branch)
          const accent = branch?.color ?? '#38bdf8'
          return (
            <motion.button
              key={cls.id}
              type="button"
              disabled={busy}
              onClick={() => onChoose(cls.id)}
              initial={{ opacity: 0, y: 26 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, delay: index * 0.08 }}
              whileHover={{ y: -6, scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className={styles.classCard}
              style={{ '--accent': accent } as React.CSSProperties}
            >
              <span className={styles.classGlyph}>{cls.icon}</span>
              <span className={styles.className}>{cls.name}</span>
              <span className={styles.classDescription}>{cls.description}</span>
              <span className={styles.classBranch}>{branch?.name ?? cls.branch}</span>
              <span className={styles.classStart}>
                Empiezas con «{branch?.name ?? cls.branch}» y 1 punto de habilidad
              </span>
            </motion.button>
          )
        })}
      </div>
    </div>
  )
}
