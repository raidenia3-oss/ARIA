import { useMemo } from 'react'
import { motion } from 'framer-motion'
import type { SkillTreeBranch, SkillTreeNode } from '../../lib/ariaBackend'
import styles from './styles.module.css'

/* Geometría del grafo. Todo el layout es determinista para que el HTML y la
   capa SVG compartan exactamente el mismo sistema de coordenadas: no hace
   falta medir el DOM ni sincronizar dos layouts distintos. */
const LANE_LABEL_W = 138
const COL_W = 158
const NODE_W = 126
const NODE_H = 54
const LANE_H = 132
const LANE_TOP = 20
const SUB_STEP = 60

interface Position {
  x: number
  y: number
  cx: number
  cy: number
}

interface TreeGraphProps {
  nodes: SkillTreeNode[]
  branches: SkillTreeBranch[]
  onSelect: (node: SkillTreeNode) => void
  branchColor: (branchId: string) => string
}

/**
 * Grafo del árbol.
 *
 * Cada rama es un carril horizontal y los niveles avanzan de izquierda a
 * derecha. Dos nodos del mismo nivel dentro de la misma rama se apilan en
 * sub-carriles, de modo que nunca se solapan.
 */
export function TreeGraph({ nodes, branches, onSelect, branchColor }: TreeGraphProps) {
  const { positions, links, width, height } = useMemo(() => {
    const pos = new Map<string, Position>()
    const branchOrder = new Map<string, number>()
    branches.forEach((b, i) => branchOrder.set(b.id, i))

    const laneIndex = new Map<string, number>()
    branches.forEach((b, i) => laneIndex.set(b.id, i))

    // Para cada rama y nivel, el sub-índice vertical del nodo.
    const subIndex = new Map<string, number>()
    const ordered = [...nodes].sort((a, b) => {
      const la = laneIndex.get(a.branch) ?? 0
      const lb = laneIndex.get(b.branch) ?? 0
      if (la !== lb) return la - lb
      if (a.tier !== b.tier) return a.tier - b.tier
      return a.slot - b.slot
    })
    const counters = new Map<string, number>()
    for (const node of ordered) {
      const key = `${node.branch}:${node.tier}`
      const idx = counters.get(key) ?? 0
      counters.set(key, idx + 1)
      subIndex.set(node.id, idx)
    }

    for (const node of ordered) {
      const lane = laneIndex.get(node.branch) ?? 0
      const x = LANE_LABEL_W + (node.tier - 1) * COL_W
      const y = lane * LANE_H + LANE_TOP + (subIndex.get(node.id) ?? 0) * SUB_STEP
      pos.set(node.id, { x, y, cx: x + NODE_W / 2, cy: y + NODE_H / 2 })
    }

    const edges: Array<{ from: string; to: string; active: boolean; color: string }> = []
    for (const node of nodes) {
      for (const req of node.requires) {
        const from = pos.get(req)
        const to = pos.get(node.id)
        if (!from || !to) continue
        edges.push({
          from: req,
          to: node.id,
          active: nodes.find((n) => n.id === req)?.unlocked === true,
          color: branchColor(node.branch),
        })
      }
    }

    const maxX = Math.max(...[...pos.values()].map((p) => p.x + NODE_W), LANE_LABEL_W)
    const maxY = Math.max(...[...pos.values()].map((p) => p.y + NODE_H), LANE_H)
    return {
      positions: pos,
      links: edges,
      width: maxX + 24,
      height: maxY + 24,
    }
  }, [nodes, branches, branchColor])

  return (
    <div className={styles.graphScroll}>
      <div className={styles.graph} style={{ width, height }}>
        <svg className={styles.links} width={width} height={height} aria-hidden="true">
          <defs>
            <filter id="link-glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          {links.map((link, i) => {
            const from = positions.get(link.from)
            const to = positions.get(link.to)
            if (!from || !to) return null
            const x1 = from.x + NODE_W
            const y1 = from.cy
            const x2 = to.x
            const y2 = to.cy
            const mid = (x1 + x2) / 2
            const d = `M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`
            return (
              <g key={`${link.from}-${link.to}-${i}`}>
                <path
                  d={d}
                  className={link.active ? styles.linkActive : styles.linkIdle}
                  stroke={link.active ? link.color : undefined}
                  filter={link.active ? 'url(#link-glow)' : undefined}
                />
                {link.active && (
                  <path
                    d={d}
                    className={styles.linkFlow}
                    stroke={link.color}
                  />
                )}
              </g>
            )
          })}
        </svg>

        {branches.map((branch, index) => (
          <div
            key={branch.id}
            className={styles.lane}
            style={{
              top: index * LANE_H,
              height: LANE_H,
              '--accent': branch.color,
            } as React.CSSProperties}
          >
            <div className={styles.laneLabel}>
              <span className={styles.laneDot} />
              <span className={styles.laneName}>{branch.name}</span>
            </div>
            <div className={styles.laneRail} />
          </div>
        ))}

        {nodes.map((node) => {
          const p = positions.get(node.id)
          if (!p) return null
          const color = branchColor(node.branch)
          const state = node.equipped
            ? 'equipped'
            : node.unlocked
              ? 'unlocked'
              : node.available
                ? 'available'
                : 'locked'
          return (
            <motion.button
              key={node.id}
              type="button"
              onClick={() => onSelect(node)}
              initial={{ opacity: 0, scale: 0.85 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.3 }}
              whileHover={{ scale: 1.06 }}
              className={`${styles.node} ${styles[state]}`}
              style={
                {
                  left: p.x,
                  top: p.y,
                  width: NODE_W,
                  height: NODE_H,
                  '--accent': color,
                } as React.CSSProperties
              }
              aria-label={`${node.name} — ${node.description}`}
            >
              <span className={styles.nodeIcon}>{node.icon}</span>
              <span className={styles.nodeName}>{node.name}</span>
              {node.equipped && <span className={styles.nodeBadge}>EQUIPADA</span>}
              {!node.unlocked && node.cost > 0 && (
                <span className={styles.nodeCost}>◆{node.cost}</span>
              )}
            </motion.button>
          )
        })}
      </div>
    </div>
  )
}
