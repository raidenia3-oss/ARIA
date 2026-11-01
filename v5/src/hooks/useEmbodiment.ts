import { useCallback, useEffect, useState } from 'react'
import {
  ariaBackend,
  type AffectResponse,
  type EvolutionResponse,
  type SocialChannel,
  type SocialMessage,
  type SocialPrompt,
  type EmbodimentWorld,
} from '../lib/ariaBackend'

/**
 * Cuerpo, audiencia y ánimo de ARIA.
 *
 * Tres fuentes distintas que el backend expone por separado:
 *
 * - los **mundos** (`/api/worlds`): dónde está y qué puede hacer,
 * - los **canales** (`/api/social/*`): quién le está hablando,
 * - el **ánimo** (`/api/affect`): cómo está.
 *
 * Se sondean por separado porque cambian a ritmos distintos: el ánimo cambia
 * cada tick, la audiencia cada mensaje.
 */

export interface UseEmbodiment {
  worlds: EmbodimentWorld[]
  channels: SocialChannel[]
  messages: SocialMessage[]
  pending: SocialPrompt | null
  affect: AffectResponse | null
  evolution: EvolutionResponse | null
  error: string | null
  busy: boolean
  toggleChannel: (id: string, enabled: boolean) => Promise<void>
  createChannel: (kind: string, target: string) => Promise<void>
  say: (channel: string, text: string) => Promise<void>
  force: (world: string, action: string, args?: Record<string, unknown>) => Promise<void>
  refresh: () => Promise<void>
}

const POLL_INTERVAL_MS = 12000
const MESSAGE_LIMIT = 30

export function useEmbodiment(enabled = true): UseEmbodiment {
  const [worlds, setWorlds] = useState<EmbodimentWorld[]>([])
  const [channels, setChannels] = useState<SocialChannel[]>([])
  const [messages, setMessages] = useState<SocialMessage[]>([])
  const [pending, setPending] = useState<SocialPrompt | null>(null)
  const [affect, setAffect] = useState<AffectResponse | null>(null)
  const [evolution, setEvolution] = useState<EvolutionResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const [worldsPayload, channelsPayload, messagesPayload, pendingPayload, affectPayload] =
        await Promise.all([
          ariaBackend.worlds(),
          ariaBackend.socialChannels(),
          ariaBackend.socialMessages(undefined, MESSAGE_LIMIT),
          ariaBackend.socialPending(),
          ariaBackend.affect(),
        ])
      setWorlds(worldsPayload.worlds ?? [])
      setChannels(channelsPayload.channels ?? [])
      setMessages(messagesPayload.messages ?? [])
      setPending(pendingPayload.pending ?? null)
      setAffect(affectPayload)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }, [])

  // El historial de cambios de carácter cambia muy poco: se pide menos a
  // menudo.
  useEffect(() => {
    if (!enabled) return
    void ariaBackend
      .affectEvolution()
      .then((payload) => setEvolution(payload))
      .catch(() => undefined)
  }, [enabled])

  useEffect(() => {
    if (!enabled) return
    void refresh()
    const timer = window.setInterval(() => void refresh(), POLL_INTERVAL_MS)
    return () => window.clearInterval(timer)
  }, [enabled, refresh])

  const toggleChannel = useCallback(
    async (id: string, enabledState: boolean) => {
      setBusy(true)
      try {
        await ariaBackend.socialToggleChannel(id, enabledState)
        await refresh()
      } finally {
        setBusy(false)
      }
    },
    [refresh],
  )

  const createChannel = useCallback(
    async (kind: string, target: string) => {
      setBusy(true)
      try {
        await ariaBackend.socialCreateChannel({ kind, target })
        await refresh()
      } finally {
        setBusy(false)
      }
    },
    [refresh],
  )

  const say = useCallback(
    async (channel: string, text: string) => {
      setBusy(true)
      try {
        await ariaBackend.socialSay(channel, text)
        await refresh()
      } finally {
        setBusy(false)
      }
    },
    [refresh],
  )

  const force = useCallback(
    async (world: string, action: string, args?: Record<string, unknown>) => {
      setBusy(true)
      try {
        await ariaBackend.worldForce(world, action, args)
        await refresh()
      } finally {
        setBusy(false)
      }
    },
    [refresh],
  )

  return {
    worlds,
    channels,
    messages,
    pending,
    affect,
    evolution,
    error,
    busy,
    toggleChannel,
    createChannel,
    say,
    force,
    refresh,
  }
}
