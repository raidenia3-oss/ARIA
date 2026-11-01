import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import type { UseEmbodiment } from '../../hooks/useEmbodiment'
import {
  channelAudience,
  channelIsListening,
  channelKindIcon,
  channelKindLabel,
  emotionLabel,
  emotionStrength,
  formatTraitChange,
  messageIsAddressed,
  messageIsAnswered,
  traitChangeIsVisible,
  traitLabel,
  worldCapabilityCount,
  worldKindIcon,
  worldKindLabel,
  worldStatusLabel,
} from '../../lib/embodiment'
import { timeAgo } from '../../lib/autonomy'
import styles from './styles.module.css'

const CHANNEL_KINDS = [
  { kind: 'twitch', label: 'Twitch', placeholder: 'canal (ej. vedal987)' },
  { kind: 'youtube', label: 'YouTube', placeholder: 'id o url del directo' },
  { kind: 'discord', label: 'Discord', placeholder: 'id del canal' },
  { kind: 'simulador', label: 'Simulador', placeholder: 'nombre libre' },
]

/**
 * Cuerpo y audiencia de ARIA.
 *
 * Es la parte del panel de presencia que la convierte en una criatura con
 * sitios donde estar y gente con la que hablar: los mundos donde puede
 * actuar, los canales que escucha y cómo está de ánimo.
 */
export function EmbodimentPanel({ embodiment }: { embodiment: UseEmbodiment }) {
  const { worlds, channels, messages, pending, affect, evolution, error, busy } = embodiment

  const [channelKind, setChannelKind] = useState('twitch')
  const [channelTarget, setChannelTarget] = useState('')

  const emotions = useMemo(() => {
    const raw = affect?.emotions ?? {}
    return Object.entries(raw).sort((a, b) => b[1] - a[1])
  }, [affect?.emotions])

  const traits = useMemo(() => {
    const raw = evolution?.traits ?? {}
    return Object.entries(raw).sort((a, b) => b[1] - a[1])
  }, [evolution?.traits])

  const lastChanges = useMemo(() => {
    const history = evolution?.history ?? []
    const notes = history
      .filter((record) => record.note && record.note.trim().length > 0)
      .slice(0, 4)
    return { history: history.slice(0, 4), notes }
  }, [evolution?.history])

  const submitChannel = async () => {
    const target = channelTarget.trim()
    if (!target) return
    await embodiment.createChannel(channelKind, target)
    setChannelTarget('')
  }

  return (
    <>
      {/* ── Mundos ─────────────────────────────────────────────────── */}
      <div className={styles.card}>
        <h3 className={styles.cardTitle}>Dónde está</h3>
        {worlds.length === 0 ? (
          <p className={styles.empty}>ARIA no tiene ningún sitio donde estar todavía.</p>
        ) : (
          <div className={styles.list}>
            {worlds.map((world) => (
              <motion.div
                key={world.id}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                className={styles.event}
              >
                <span className={styles.eventIcon}>{worldKindIcon(world.kind)}</span>
                <div className={styles.eventBody}>
                  <span className={styles.eventLabel}>
                    {world.label} · {worldKindLabel(world.kind)}
                  </span>
                  <p className={styles.eventText}>
                    {worldStatusLabel(world)} · {worldCapabilityCount(world)} capacidades
                    {world.pending > 0 ? ` · ${world.pending} en cola` : ''}
                  </p>
                </div>
                {world.kind === 'avatar' && (
                  <button
                    type="button"
                    className={styles.button}
                    disabled={busy}
                    onClick={() =>
                      void embodiment.force('vrchat', 'chatbox.say', {
                        text: 'Aquí estoy.',
                      })
                    }
                    title="Escribe en el chatbox de VRChat"
                  >
                    Hablar
                  </button>
                )}
              </motion.div>
            ))}
          </div>
        )}
      </div>

      {/* ── Audiencia ──────────────────────────────────────────────── */}
      <div className={styles.card}>
        <h3 className={styles.cardTitle}>Quién le habla</h3>

        <div className={styles.modeRow}>
          {CHANNEL_KINDS.map((option) => (
            <button
              key={option.kind}
              type="button"
              className={`${styles.button} ${
                channelKind === option.kind ? styles.buttonPrimary : styles.buttonGhost
              }`}
              onClick={() => setChannelKind(option.kind)}
            >
              {option.label}
            </button>
          ))}
        </div>

        <div className={styles.buttonRow}>
          <input
            className={styles.input}
            value={channelTarget}
            placeholder={CHANNEL_KINDS.find((o) => o.kind === channelKind)?.placeholder ?? ''}
            onChange={(event) => setChannelTarget(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') void submitChannel()
            }}
          />
          <button
            type="button"
            className={`${styles.button} ${styles.buttonPrimary}`}
            disabled={busy || channelTarget.trim().length === 0}
            onClick={() => void submitChannel()}
          >
            Escuchar
          </button>
        </div>

        {channels.length === 0 ? (
          <p className={styles.empty}>
            Todavía no escucha a nadie. Añade un canal y ARIA tendrá público.
          </p>
        ) : (
          <div className={styles.list}>
            {channels.map((channel) => (
              <div key={channel.id} className={styles.event}>
                <span className={styles.eventIcon}>{channelKindIcon(channel.kind)}</span>
                <div className={styles.eventBody}>
                  <span className={styles.eventLabel}>
                    {channel.label} · {channelKindLabel(channel.kind)}
                  </span>
                  <p className={styles.eventText}>
                    {channelAudience(channel)}
                    {channel.last_message_at ? ` · ${timeAgo(channel.last_message_at)}` : ''}
                    {channel.last_error ? ` · ${channel.last_error}` : ''}
                  </p>
                </div>
                <label className={styles.switch}>
                  <input
                    type="checkbox"
                    checked={channel.enabled}
                    disabled={busy}
                    onChange={(event) => void embodiment.toggleChannel(channel.id, event.target.checked)}
                  />
                  <span>{channelIsListening(channel) ? 'Escuchando' : 'Apagado'}</span>
                </label>
              </div>
            ))}
          </div>
        )}

        {pending && (
          <p className={styles.hint}>
            Pendiente de responder en {pending.channel}: “{pending.text}”
          </p>
        )}
      </div>

      {/* ── Mensajes ───────────────────────────────────────────────── */}
      {messages.length > 0 && (
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>La sala</h3>
          <div className={styles.list}>
            {messages.slice(0, 12).map((message) => (
              <div key={message.id} className={styles.event}>
                <span className={styles.eventIcon}>
                  {messageIsAnswered(message) ? '✓' : messageIsAddressed(message) ? '❗' : '·'}
                </span>
                <div className={styles.eventBody}>
                  <span className={styles.eventLabel}>{message.author}</span>
                  <p className={styles.eventText}>{message.text}</p>
                </div>
                <span className={styles.eventTime}>{timeAgo(message.at)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Ánimo y carácter ───────────────────────────────────────── */}
      <div className={styles.card}>
        <h3 className={styles.cardTitle}>Cómo está</h3>
        {affect ? (
          <>
            <div className={styles.presenceHead}>
              <span className={styles.presenceExpression}>
                {emotionLabel(affect.dominant)}
              </span>
              <span className={styles.presencePlace}>{affect.expression}</span>
            </div>
            <div className={styles.meterTrack}>
              <div
                className={styles.meterFill}
                style={{ width: `${Math.round((affect.mood ?? 0) * 100)}%` }}
              />
            </div>
            <div className={styles.drives}>
              {emotions.map(([name, level]) => (
                <div key={name} className={styles.drive}>
                  <div className={styles.driveHead}>
                    <span className={styles.driveName}>{emotionLabel(name)}</span>
                    <span className={styles.driveValue}>{level.toFixed(2)}</span>
                  </div>
                  <div className={styles.driveTrack}>
                    <div className={styles.driveFill} style={{ width: `${Math.round(level * 100)}%` }} />
                  </div>
                  <span className={styles.driveHint}>{emotionStrength(level)}</span>
                </div>
              ))}
            </div>
          </>
        ) : (
          <p className={styles.empty}>Sin datos de ánimo.</p>
        )}

        {traits.length > 0 && (
          <>
            <h3 className={styles.cardTitle}>Carácter</h3>
            <div className={styles.drives}>
              {traits.map(([name, level]) => (
                <div key={name} className={styles.drive}>
                  <div className={styles.driveHead}>
                    <span className={styles.driveName}>{traitLabel(name)}</span>
                    <span className={styles.driveValue}>{level.toFixed(2)}</span>
                  </div>
                  <div className={styles.driveTrack}>
                    <div className={styles.driveFill} style={{ width: `${Math.round(level * 100)}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </>
        )}

        {lastChanges.notes.length > 0 && (
          <div className={styles.list}>
            {lastChanges.notes.map((record) => (
              <div key={record.at} className={styles.episode}>
                <div className={styles.episodeHead}>
                  <span className={styles.episodeGoal}>{record.note}</span>
                  <span className={styles.episodeDrive}>{timeAgo(record.at)}</span>
                </div>
                {Object.entries(record.changes)
                  .filter(([, delta]) => traitChangeIsVisible(delta))
                  .map(([trait, delta]) => (
                    <span key={trait} className={styles.hint}>
                      {traitLabel(trait)} {formatTraitChange(delta)}
                    </span>
                  ))}
              </div>
            ))}
          </div>
        )}
      </div>

      {error && <p className={styles.error}>{error}</p>}
    </>
  )
}
