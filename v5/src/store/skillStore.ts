import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type Race = 'human' | 'dwarf' | 'elf' | 'ogre' | 'slime'

export interface Ability {
  id: string
  name: string
  description: string
  type: 'common' | 'unique'
  tier: number
  mana_cost: number
  icon: string
  unlocked: boolean
}

export interface CharacterStats {
  race: Race
  level: number
  mana: number
  max_mana: number
  abilities: Ability[]
}

export interface SkillState {
  character: CharacterStats | null
  initCharacter: (race: Race) => void
  unlockAbility: (abilityId: string) => void
  levelUp: () => void
  saveToBackend: () => Promise<void>
}

function getInitialMana(race: Race): number {
  const manas: Record<Race, number> = {
    human: 100, dwarf: 80, elf: 120, ogre: 150, slime: 200,
  }
  return manas[race]
}

function getInitialAbilities(race: Race): Ability[] {
  const base: Ability[] = [
    { id: '1', name: 'Analyst', description: 'Analyze code patterns', type: 'common', tier: 1, mana_cost: 10, icon: '🔍', unlocked: true },
    { id: '2', name: 'Absorb', description: 'Integrate knowledge', type: 'unique', tier: 2, mana_cost: 30, icon: '🌊', unlocked: false },
    { id: '3', name: 'Regenerate', description: 'Recover from errors', type: 'unique', tier: 3, mana_cost: 50, icon: '💚', unlocked: false },
  ]
  if (race === 'slime') {
    base.push({ id: '4', name: 'Dissolve', description: 'Absorb any substance', type: 'unique', tier: 2, mana_cost: 25, icon: '🧪', unlocked: false })
  }
  return base
}

export const useSkillStore = create<SkillState>()(
  persist(
    (set, get) => ({
      character: null,

      initCharacter: (race: Race) => {
        const newChar: CharacterStats = {
          race, level: 1, mana: getInitialMana(race), max_mana: getInitialMana(race),
          abilities: getInitialAbilities(race),
        }
        set({ character: newChar })
        get().saveToBackend()
      },

      unlockAbility: (abilityId: string) => {
        set((state) => {
          if (!state.character) return state
          return {
            character: {
              ...state.character,
              abilities: state.character.abilities.map((a) =>
                a.id === abilityId ? { ...a, unlocked: true } : a
              ),
            },
          }
        })
        get().saveToBackend()
      },

      levelUp: () => {
        set((state) => {
          if (!state.character) return state
          return {
            character: {
              ...state.character,
              level: state.character.level + 1,
              max_mana: state.character.max_mana + 50,
              mana: state.character.max_mana + 50,
            },
          }
        })
        get().saveToBackend()
      },

      saveToBackend: async () => {
        const state = get()
        if (!state.character) return
        try {
          await fetch('http://127.0.0.1:8000/api/agents/skills/progression', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(state.character),
          })
        } catch {
          /* save failed */
        }
      },
    }),
    { name: 'skill-store' }
  )
)