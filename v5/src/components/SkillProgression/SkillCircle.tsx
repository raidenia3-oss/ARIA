import { useState } from 'react'
import { Ability } from '../../store/skillStore'
import styles from './styles.module.css'

interface SkillCircleProps {
  abilities: Ability[]
  onAbilityHover: (ability: Ability | null) => void
  onAbilityClick: (ability: Ability) => void
}

export function SkillCircle({ abilities, onAbilityHover, onAbilityClick }: SkillCircleProps) {
  const [hoveredAbility, setHoveredAbility] = useState<Ability | null>(null)

  const commonAbilities = abilities.filter((a) => a.type === 'common')
  const uniqueAbilities = abilities.filter((a) => a.type === 'unique')

  return (
    <svg viewBox="0 0 400 400" className={styles.skillCircle}>
      <circle cx="200" cy="200" r="180" fill="none" stroke="#1e293b" strokeWidth="1" />
      <circle cx="200" cy="200" r="120" fill="none" stroke="#1e293b" strokeWidth="1" />

      <g>
        <circle cx="200" cy="200" r="50" fill="#0f172a" stroke="#38bdf8" strokeWidth="2" />
        <text x="200" y="195" textAnchor="middle" className={styles.centerText}>
          Level 1
        </text>
        <text x="200" y="215" textAnchor="middle" className={styles.centerMana}>
          Mana: 100/100
        </text>
      </g>

      {commonAbilities.map((ability, idx) => {
        const angle = (idx / Math.max(commonAbilities.length, 1)) * Math.PI * 2
        const x = 200 + Math.cos(angle) * 100
        const y = 200 + Math.sin(angle) * 100

        return (
          <g
            key={ability.id}
            onMouseEnter={() => { setHoveredAbility(ability); onAbilityHover(ability) }}
            onMouseLeave={() => { setHoveredAbility(null); onAbilityHover(null) }}
            onClick={() => onAbilityClick(ability)}
            style={{ cursor: 'pointer' }}
          >
            <circle
              cx={x} cy={y} r="20"
              fill={ability.unlocked ? '#34d399' : '#475569'}
              opacity={hoveredAbility?.id === ability.id ? 1 : 0.7}
            />
            <text x={x} y={y} textAnchor="middle" dominantBaseline="central" className={styles.abilityIcon}>
              {ability.icon}
            </text>
          </g>
        )
      })}

      {uniqueAbilities.map((ability, idx) => {
        const angle = (idx / Math.max(uniqueAbilities.length, 1)) * Math.PI * 2
        const x = 200 + Math.cos(angle) * 150
        const y = 200 + Math.sin(angle) * 150

        return (
          <g
            key={ability.id}
            onMouseEnter={() => { setHoveredAbility(ability); onAbilityHover(ability) }}
            onMouseLeave={() => { setHoveredAbility(null); onAbilityHover(null) }}
            onClick={() => onAbilityClick(ability)}
            style={{ cursor: 'pointer' }}
          >
            <circle
              cx={x} cy={y} r="25"
              fill={ability.unlocked ? '#a78bfa' : '#475569'}
              stroke={hoveredAbility?.id === ability.id ? '#38bdf8' : 'none'}
              strokeWidth="2"
            />
            <text x={x} y={y} textAnchor="middle" dominantBaseline="central" className={styles.abilityIcon} fontSize="20">
              {ability.icon}
            </text>
          </g>
        )
      })}
    </svg>
  )
}