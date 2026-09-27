import React, { useState } from 'react'
import { useSkillStore, Ability, Race } from '../../store/skillStore'
import { SkillCircle } from './SkillCircle'
import styles from './styles.module.css'

export function SkillProgression() {
  const character = useSkillStore((state) => state.character)
  const initCharacter = useSkillStore((state) => state.initCharacter)
  const unlockAbility = useSkillStore((state) => state.unlockAbility)
  const [hoveredAbility, setHoveredAbility] = useState<Ability | null>(null)

  if (!character) {
    return (
      <div className={styles.raceSelection}>
        <h1>SELECT YOUR RACE</h1>
        <div className={styles.raceGrid}>
          {(['human', 'dwarf', 'elf', 'ogre', 'slime'] as Race[]).map((race) => (
            <button key={race} className={styles.raceButton} onClick={() => initCharacter(race)}>
              {race.toUpperCase()}
            </button>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className={styles.container}>
      <SkillCircle
        abilities={character.abilities}
        onAbilityHover={setHoveredAbility}
        onAbilityClick={(ability) => {
          if (!ability.unlocked) unlockAbility(ability.id)
        }}
      />

      {hoveredAbility && (
        <div className={styles.tooltip}>
          <h3>{hoveredAbility.name}</h3>
          <p>{hoveredAbility.description}</p>
          <p>Mana Cost: {hoveredAbility.mana_cost}</p>
          <p>Tier: {hoveredAbility.tier}</p>
        </div>
      )}
    </div>
  )
}