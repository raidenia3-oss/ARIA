import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ariaBackend,
  type AutonomyEvent,
  type AutonomyEpisode,
  type AutonomyInitiative,
  type AutonomyLesson,
  type AutonomyMode,
  type AutonomyStatusResponse,
  type PerceptionSnapshot,
} from '../lib/ariaBackend'

/**
 * Conexión con el runtime autónomo de ARIA.
 *
 * El runtime vive en el backend: esto es sólo el ojo que lo mira. Se
 * suscribe al flujo de eventos en vivo (SSE) y sondea el estado cada pocos
 * segundos para tener las pulsiones y los episodios frescos.
 *
 * El sondeo pide DOS cosas y no más: el estado (`/api/autonomy/status`) y
 * la percepción (`/api/perception`). La segunda ya trae la agenda, las
 * lecciones, los mundos y la audiencia, así que no hace falta pedir cada
 * bloque por separado — es el mismo trabajo que hace el runtime para
 * decidir, no una versión de escaparate.
 */

export interface UseAutonomy {
  status: AutonomyStatusResponse | null
  events: AutonomyEvent[]
  episodes: AutonomyEpisode[]
  /** Lo que ARIA tiene entre manos. */
  agenda: AutonomyInitiative[]
  /** Lo que ARIA ha aprendido. */
  lessons: AutonomyLesson[]
  /** Lo que ARIA ve ahora mismo. */
  perception: PerceptionSnapshot | null
  /** Última frase que ha dicho ARIA por su cuenta. */
  speech: { id: number; text: string } | null
  connected: boolean
  error: string | null
  busy: boolean
  setMode: (mode: AutonomyMode) => Promise<void>
  toggle: (enabled: boolean) => Promise<void>
  /** El freno de seguridad: con `false` ARIA no toca mundos ni canales. */
  setAllowExternal: (allowed: boolean) => Promise<void>
  speak: (topic?: string) => Promise<string | null>
  act: (payload: { action: string; topic?: string; skill_id?: string }) => Promise<void>
  tick: () => Promise<void>
  /** Apunta un objetivo: ARIA lo seguirá sola. */
  addGoal: (goal: string, reason?: string) => Promise<void>
  /** Suelta un objetivo de la agenda. */
  dropGoal: (id: number) => Promise<void>
  /** Enseña una regla a ARIA. */
  addLesson: (text: string, kind?: 'regla' | 'exito' | 'fallo') => Promise<void>
  /** Silencia o reactiva una lección. */
  toggleLesson: (id: number, suppressed: boolean) => Promise<void>
  /** Fusiona las lecciones repetidas. */
  curateLessons: () => Promise<void>
  refresh: () => Promise<void>
}

const POLL_INTERVAL_MS = 15000
const MAX_EVENTS = 60

export function useAutonomy(enabled = true): UseAutonomy {
  const [status, setStatus] = useState<AutonomyStatusResponse | null>(null)
  const [events, setEvents] = useState<AutonomyEvent[]>([])
  const [episodes, setEpisodes] = useState<AutonomyEpisode[]>([])
  const [agenda, setAgenda] = useState<AutonomyInitiative[]>([])
  const [lessons, setLessons] = useState<AutonomyLesson[]>([])
  const [perception, setPerception] = useState<PerceptionSnapshot | null>(null)
  const [speech, setSpeech] = useState<{ id: number; text: string } | null>(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const seenSpeech = useRef<number>(0)

  const refresh = useCallback(async () => {
    try {
      // Las dos peticiones van a la vez: el panel no tiene que esperar dos
      // rondas para estar al día.
      const [statusPayload, perceptionPayload] = await Promise.all([
        ariaBackend.autonomyStatus(),
        ariaBackend.perception(),
      ])
      setStatus(statusPayload)
      setPerception(perceptionPayload.perception ?? null)
      setAgenda(perceptionPayload.perception?.agenda ?? [])
      setLessons(perceptionPayload.perception?.lessons ?? [])
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }, [])

  /* ── Sondeo periódico del estado ─────────────────────────────────── */

  useEffect(() => {
    if (!enabled) return
    void refresh()
    const timer = window.setInterval(() => void refresh(), POLL_INTERVAL_MS)
    return () => window.clearInterval(timer)
  }, [enabled, refresh])

  /* ── Flujo de eventos en vivo ────────────────────────────────────── */

  useEffect(() => {
    if (!enabled) return

    const controller = new AbortController()
    let stopped = false

    const connect = async () => {
      while (!stopped && !controller.signal.aborted) {
        try {
          await ariaBackend.autonomyStream(
            (event) => {
              setConnected(true)
              setEvents((prev) => [event, ...prev].slice(0, MAX_EVENTS))
              // Lo que ARIA dice por su cuenta se marca para que el chat
              // lo recoja: es ella hablando, no una respuesta.
              if (event.kind === 'habla' && event.id > seenSpeech.current) {
                seenSpeech.current = event.id
                setSpeech({ id: event.id, text: event.text })
              }
            },
            controller.signal,
          )
        } catch {
          // Sin backend no hay flujo: se reintenta con calma.
        }
        if (stopped || controller.signal.aborted) break
        setConnected(false)
        await new Promise((resolve) => window.setTimeout(resolve, 4000))
      }
    }

    void connect()

    return () => {
      stopped = true
      controller.abort()
      setConnected(false)
    }
  }, [enabled])

  /* ── Acciones ────────────────────────────────────────────────────── */

  const setMode = useCallback(async (mode: AutonomyMode) => {
    setBusy(true)
    try {
      await ariaBackend.autonomySetMode(mode)
      await refresh()
    } finally {
      setBusy(false)
    }
  }, [refresh])

  const toggle = useCallback(async (enabled: boolean) => {
    setBusy(true)
    try {
      await ariaBackend.autonomyToggle(enabled)
      await refresh()
    } finally {
      setBusy(false)
    }
  }, [refresh])

  const setAllowExternal = useCallback(async (allowed: boolean) => {
    setBusy(true)
    try {
      await ariaBackend.autonomyPermissions(allowed)
      await refresh()
    } finally {
      setBusy(false)
    }
  }, [refresh])

  const speak = useCallback(async (topic?: string) => {
    setBusy(true)
    try {
      const payload = await ariaBackend.autonomySpeak(topic)
      if (payload.said) {
        setSpeech({ id: Date.now(), text: payload.said })
      }
      await refresh()
      return payload.said
    } finally {
      setBusy(false)
    }
  }, [refresh])

  const act = useCallback(
    async (payload: { action: string; topic?: string; skill_id?: string }) => {
      setBusy(true)
      try {
        await ariaBackend.autonomyAct(payload)
        await refresh()
      } finally {
        setBusy(false)
      }
    },
    [refresh],
  )

  const tick = useCallback(async () => {
    setBusy(true)
    try {
      await ariaBackend.autonomyTick(true)
      await refresh()
    } finally {
      setBusy(false)
    }
  }, [refresh])

  const addGoal = useCallback(
    async (goal: string, reason?: string) => {
      setBusy(true)
      try {
        await ariaBackend.autonomyAddAgenda({ goal, reason: reason ?? '' })
        await refresh()
      } finally {
        setBusy(false)
      }
    },
    [refresh],
  )

  const dropGoal = useCallback(
    async (id: number) => {
      setBusy(true)
      try {
        await ariaBackend.autonomyDropAgenda(id)
        await refresh()
      } finally {
        setBusy(false)
      }
    },
    [refresh],
  )

  const addLesson = useCallback(
    async (text: string, kind: 'regla' | 'exito' | 'fallo' = 'regla') => {
      setBusy(true)
      try {
        await ariaBackend.lessonsRecord({ kind, text })
        await refresh()
      } finally {
        setBusy(false)
      }
    },
    [refresh],
  )

  const toggleLesson = useCallback(
    async (id: number, suppressed: boolean) => {
      setBusy(true)
      try {
        await ariaBackend.lessonsSuppress(id, suppressed)
        await refresh()
      } finally {
        setBusy(false)
      }
    },
    [refresh],
  )

  const curateLessons = useCallback(async () => {
    setBusy(true)
    try {
      await ariaBackend.lessonsCurate()
      await refresh()
    } finally {
      setBusy(false)
    }
  }, [refresh])

  // Los episodios vienen en el estado: se copian para poder mostrarlos
  // aunque el sondeo se retrase.
  useEffect(() => {
    if (status?.episodes) setEpisodes(status.episodes)
  }, [status?.episodes])

  return {
    status,
    events,
    episodes,
    agenda,
    lessons,
    perception,
    speech,
    connected,
    error,
    busy,
    setMode,
    toggle,
    setAllowExternal,
    speak,
    act,
    tick,
    addGoal,
    dropGoal,
    addLesson,
    toggleLesson,
    curateLessons,
    refresh,
  }
}
