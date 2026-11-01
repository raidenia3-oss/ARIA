import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ariaBackend,
  type SkillTreeNode,
  type SkillTreeProgression,
  type SkillTreeResponse,
} from '../lib/ariaBackend'

/**
 * Estado del árbol de habilidades.
 *
 * El servidor es la autoridad: cada mutación devuelve la progresión nueva y
 * aquí se reemplaza. Si una mutación falla, la progresión NO se toca — el
 * error se muestra aparte, para que la UI nunca insinúe un cambio que el
 * servidor rechazó.
 */
export interface SkillTreeState {
  nodes: SkillTreeNode[]
  branches: SkillTreeResponse['branches']
  classes: SkillTreeResponse['classes']
  progression: SkillTreeProgression | null
  loading: boolean
  error: string | null
  /** Mensaje de error de la última mutación fallida. */
  mutationError: string | null
  online: boolean
}

export interface UseSkillTree extends SkillTreeState {
  refresh: () => Promise<void>
  unlock: (nodeId: string) => Promise<boolean>
  equip: (nodeId: string, equipped: boolean) => Promise<boolean>
  chooseClass: (classId: string) => Promise<boolean>
  reset: () => Promise<boolean>
  clearMutationError: () => void
  nodeById: (id: string) => SkillTreeNode | undefined
  branchColor: (branchId: string) => string
}

export function useSkillTree(): UseSkillTree {
  const [state, setState] = useState<SkillTreeState>({
    nodes: [],
    branches: [],
    classes: [],
    progression: null,
    loading: true,
    error: null,
    mutationError: null,
    online: false,
  })

  const refresh = useCallback(async () => {
    try {
      const payload = await ariaBackend.skillTree()
      setState((prev) => ({
        ...prev,
        nodes: payload.nodes ?? [],
        branches: payload.branches ?? [],
        classes: payload.classes ?? [],
        progression: payload.progression ?? null,
        loading: false,
        error: null,
        online: true,
      }))
    } catch (error) {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: error instanceof Error ? error.message : String(error),
        online: false,
      }))
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  /**
   * Aplica una mutación y actualiza la progresión con lo que devuelve el
   * servidor. Devuelve `true` si la operación fue aceptada.
   */
  const mutate = useCallback(
    async (
      run: () => Promise<{
        status: string
        error?: string
        progression?: SkillTreeProgression
      }>,
    ): Promise<boolean> => {
      try {
        const result = await run()
        if (result.status !== 'ok') {
          setState((prev) => ({
            ...prev,
            mutationError: result.error ?? 'Operación rechazada',
          }))
          return false
        }
        setState((prev) => ({
          ...prev,
          mutationError: null,
          progression: result.progression ?? prev.progression,
        }))
        // La lista de nodos cambia de estado (available/blocked_by), así que
        // se recarga entera tras cada mutación.
        await refresh()
        return true
      } catch (error) {
        setState((prev) => ({
          ...prev,
          mutationError: error instanceof Error ? error.message : String(error),
        }))
        return false
      }
    },
    [refresh],
  )

  const unlock = useCallback(
    (nodeId: string) => mutate(() => ariaBackend.skillTreeUnlock(nodeId)),
    [mutate],
  )

  const equip = useCallback(
    (nodeId: string, equipped: boolean) =>
      mutate(() => ariaBackend.skillTreeEquip(nodeId, equipped)),
    [mutate],
  )

  const chooseClass = useCallback(
    (classId: string) => mutate(() => ariaBackend.skillTreeChooseClass(classId)),
    [mutate],
  )

  const reset = useCallback(() => mutate(() => ariaBackend.skillTreeReset()), [mutate])

  const clearMutationError = useCallback(() => {
    setState((prev) => ({ ...prev, mutationError: null }))
  }, [])

  const nodeById = useCallback(
    (id: string) => state.nodes.find((n) => n.id === id),
    [state.nodes],
  )

  const branchColor = useCallback(
    (branchId: string) =>
      state.branches.find((b) => b.id === branchId)?.color ?? '#38bdf8',
    [state.branches],
  )

  return useMemo(
    () => ({
      ...state,
      refresh,
      unlock,
      equip,
      chooseClass,
      reset,
      clearMutationError,
      nodeById,
      branchColor,
    }),
    [state, refresh, unlock, equip, chooseClass, reset, clearMutationError, nodeById, branchColor],
  )
}
