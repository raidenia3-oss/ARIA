import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import type { UseAutonomy } from '../../hooks/useAutonomy'
import type { UseEmbodiment } from '../../hooks/useEmbodiment'
import { EmbodimentPanel } from './EmbodimentPanel'
import {
  DRIVE_HINTS,
  driveLabel,
  episodeLabel,
  eventLabel,
  expressionLabel,
  initiativeStateIcon,
  initiativeStateLabel,
  lessonKindIcon,
  lessonKindLabel,
  modeLabel,
  pendingInitiatives,
  perceptionSummary,
  quirksToText,
  sourceIcon,
  textToQuirks,
  timeAgo,
  urgencyLabel,
  worldIcon,
  worldSilenceLabel,
  worldStateLabel,
} from '../../lib/autonomy'
import type { AutonomyMode, AutonomyPersona } from '../../lib/ariaBackend'
import { ariaBackend } from '../../lib/ariaBackend'
import styles from './styles.module.css'

const MODES: AutonomyMode[] = ['activa', 'tranquila', 'dormida']

/**
 * Panel de presencia: el estado vivo de ARIA.
 *
 * No es un panel de configuración: es la ventana al runtime. Se ve qué
 * pulsión la empuja a actuar, qué ha hecho, qué está pasando en los
 * escenarios (escritorio, Minecraft, VRChat) y se le puede cambiar el
 * humor y el carácter.
 */
export function PresencePanel({
  autonomy,
  embodiment,
}: {
  autonomy: UseAutonomy
  embodiment: UseEmbodiment
}) {
  const { status, events, episodes, agenda, lessons, perception, connected, error, busy } = autonomy

  const [tone, setTone] = useState('')
  const [quirks, setQuirks] = useState('')
  const [savingPersona, setSavingPersona] = useState(false)
  const [savedNote, setSavedNote] = useState<string | null>(null)
  const [goal, setGoal] = useState('')
  const [rule, setRule] = useState('')

  const persona = status?.persona

  // El editor se carga con la persona del servidor, pero no pisa lo que el
  // usuario está escribiendo mientras llega el sondeo.
  useEffect(() => {
    if (!persona) return
    setTone((prev) => (prev ? prev : persona.tone))
    setQuirks((prev) => (prev ? prev : quirksToText(persona.quirks)))
  }, [persona])

  const drives = useMemo(() => {
    const raw = status?.drives ?? {}
    return Object.entries(raw).sort((a, b) => b[1] - a[1])
  }, [status?.drives])

  const threshold = status?.threshold ?? 0.55

  const pending = useMemo(() => pendingInitiatives(agenda), [agenda])

  const addGoal = async () => {
    const text = goal.trim()
    if (!text) return
    await autonomy.addGoal(text)
    setGoal('')
  }

  const addRule = async () => {
    const text = rule.trim()
    if (!text) return
    await autonomy.addLesson(text)
    setRule('')
  }

  const savePersona = async () => {
    if (!persona) return
    setSavingPersona(true)
    setSavedNote(null)
    try {
      const next: AutonomyPersona = {
        ...persona,
        tone: tone.trim() || persona.tone,
        quirks: textToQuirks(quirks),
      }
      await ariaBackend.autonomySetPersona(next)
      setSavedNote('Guardada')
      await autonomy.refresh()
      window.setTimeout(() => setSavedNote(null), 2500)
    } catch {
      setSavedNote('No se pudo guardar')
    } finally {
      setSavingPersona(false)
    }
  }

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <div>
          <span className={styles.kicker}>PRESENCIA</span>
          <h2 className={styles.title}>ARIA está viva</h2>
          <p className={styles.subtitle}>
            El runtime decide sola con sus propias pulsiones. Si nadie le habla, busca algo que
            hacer; si le hablan, contesta. Todo lo que hace queda escrito.
          </p>
        </div>

        <div className={styles.stats}>
          <div className={styles.stat}>
            <span className={styles.statValue}>{status?.stats.actions ?? 0}</span>
            <span className={styles.statLabel}>ACCIONES</span>
          </div>
          <div className={styles.stat}>
            <span className={styles.statValue}>{status?.stats.utterances ?? 0}</span>
            <span className={styles.statLabel}>FRASES</span>
          </div>
          <div className={styles.stat}>
            <span className={styles.statValue}>{status?.stats.reactions ?? 0}</span>
            <span className={styles.statLabel}>RESPUESTAS</span>
          </div>
          <div className={styles.stat}>
            <span className={`${styles.liveDot} ${connected ? styles.liveOn : ''}`} />
            <span className={styles.statLabel}>{connected ? 'EN VIVO' : 'SIN SEÑAL'}</span>
          </div>
        </div>
      </header>

      {error && <p className={styles.error}>{error}</p>}

      <div className={styles.columns}>
        <section className={styles.column}>
          {/* ── Estado ─────────────────────────────────────────────── */}
          <div className={styles.card}>
            <h3 className={styles.cardTitle}>Estado</h3>

            <div className={styles.modeRow}>
              {MODES.map((mode) => (
                <button
                  key={mode}
                  type="button"
                  className={`${styles.button} ${
                    status?.mode === mode ? styles.buttonPrimary : styles.buttonGhost
                  }`}
                  disabled={busy}
                  onClick={() => void autonomy.setMode(mode)}
                  title={mode}
                >
                  {modeLabel(mode)}
                </button>
              ))}
            </div>

            <label className={styles.switch}>
              <input
                type="checkbox"
                checked={status?.enabled ?? false}
                disabled={busy}
                onChange={(event) => void autonomy.toggle(event.target.checked)}
              />
              <span>Puede actuar sola</span>
            </label>

            <label className={styles.switch}>
              <input
                type="checkbox"
                checked={status?.allow_external ?? false}
                disabled={busy}
                onChange={(event) => void autonomy.setAllowExternal(event.target.checked)}
              />
              <span>Puede tocar el exterior (Minecraft, VRChat, Discord)</span>
            </label>

            <div className={styles.presenceBox}>
              <div className={styles.presenceHead}>
                <span className={styles.presenceExpression}>
                  {expressionLabel(status?.presence.expression ?? 'neutra')}
                </span>
                <span className={styles.presencePlace}>
                  {status?.presence.place ?? 'en el escritorio'}
                </span>
              </div>
              <div className={styles.meterTrack}>
                <div
                  className={styles.meterFill}
                  style={{ width: `${Math.round((status?.presence.mood ?? 0) * 100)}%` }}
                />
              </div>
              <p className={styles.hint}>
                Canal: {status?.presence.channel ?? 'escritorio'} ·{' '}
                {urgencyLabel(status?.urge ?? 0, threshold)} (umbral {threshold.toFixed(2)})
              </p>
            </div>

            <div className={styles.buttonRow}>
              <button
                type="button"
                className={`${styles.button} ${styles.buttonPrimary}`}
                disabled={busy}
                onClick={() => void autonomy.speak()}
              >
                Hablar ahora
              </button>
              <button
                type="button"
                className={`${styles.button} ${styles.buttonGhost}`}
                disabled={busy}
                onClick={() => void autonomy.tick()}
                title="Fuerza una vuelta del runtime"
              >
                Espabilarla
              </button>
            </div>
          </div>

          {/* ── Cuerpo y audiencia ─────────────────────────────────── */}
          <EmbodimentPanel embodiment={embodiment} />

          {/* ── Pulso ──────────────────────────────────────────────── */}
          <div className={styles.card}>
            <h3 className={styles.cardTitle}>Pulso</h3>
            {drives.length === 0 ? (
              <p className={styles.empty}>Sin datos todavía.</p>
            ) : (
              <div className={styles.drives}>
                {drives.map(([name, level]) => (
                  <div key={name} className={styles.drive}>
                    <div className={styles.driveHead}>
                      <span className={styles.driveName}>{driveLabel(name)}</span>
                      <span className={styles.driveValue}>{level.toFixed(2)}</span>
                    </div>
                    <div className={styles.driveTrack}>
                      <div
                        className={`${styles.driveFill} ${
                          level >= threshold ? styles.driveHot : ''
                        }`}
                        style={{ width: `${Math.round(level * 100)}%` }}
                      />
                      <div className={styles.threshold} style={{ left: `${threshold * 100}%` }} />
                    </div>
                    <span className={styles.driveHint}>{DRIVE_HINTS[name] ?? ''}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ── Personalidad ───────────────────────────────────────── */}
          <div className={styles.card}>
            <h3 className={styles.cardTitle}>Personalidad</h3>
            {persona ? (
              <>
                <p className={styles.personaLine}>
                  <strong>{persona.name}</strong> · {persona.role}
                </p>
                <label className={styles.field}>
                  <span className={styles.fieldLabel}>TONO</span>
                  <textarea
                    className={styles.textarea}
                    rows={2}
                    value={tone}
                    onChange={(event) => setTone(event.target.value)}
                  />
                </label>
                <label className={styles.field}>
                  <span className={styles.fieldLabel}>CÓMO ES (una por línea)</span>
                  <textarea
                    className={styles.textarea}
                    rows={4}
                    value={quirks}
                    onChange={(event) => setQuirks(event.target.value)}
                  />
                </label>
                <div className={styles.buttonRow}>
                  <button
                    type="button"
                    className={`${styles.button} ${styles.buttonPrimary}`}
                    disabled={savingPersona}
                    onClick={() => void savePersona()}
                  >
                    {savingPersona ? 'Guardando…' : 'Guardar'}
                  </button>
                  {savedNote && <span className={styles.note}>{savedNote}</span>}
                </div>
              </>
            ) : (
              <p className={styles.empty}>Cargando la persona…</p>
            )}
          </div>
        </section>

        <section className={styles.column}>
          {/* ── Ahora mismo ─────────────────────────────────────────── */}
          <div className={styles.card}>
            <h3 className={styles.cardTitle}>Ahora mismo</h3>
            <p className={styles.perceptionLine}>{perceptionSummary(perception)}</p>

            {perception && perception.worlds.length > 0 && (
              <div className={styles.worlds}>
                {perception.worlds.map((world) => (
                  <div key={world.id} className={styles.world}>
                    <span className={styles.worldIcon}>{worldIcon(world)}</span>
                    <div className={styles.worldBody}>
                      <span className={styles.worldName}>
                        {world.label}
                        <span className={styles.worldState}>{worldStateLabel(world)}</span>
                      </span>
                      <span className={styles.worldMeta}>
                        {worldSilenceLabel(world)}
                        {world.pending > 0 ? ` · ${world.pending} esperando` : ''}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {perception?.audience && (
              <p className={styles.hint}>
                {perception.audience.author} en {perception.audience.channel}: “{perception.audience.text}”
              </p>
            )}
          </div>

          {/* ── La agenda ──────────────────────────────────────────── */}
          <div className={styles.card}>
            <h3 className={styles.cardTitle}>Lo que tiene entre manos</h3>

            <div className={styles.goalRow}>
              <input
                className={styles.input}
                placeholder="Dile qué quieres que haga…"
                value={goal}
                onChange={(event) => setGoal(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') void addGoal()
                }}
              />
              <button
                type="button"
                className={`${styles.button} ${styles.buttonPrimary}`}
                disabled={busy || goal.trim().length === 0}
                onClick={() => void addGoal()}
              >
                Apuntar
              </button>
            </div>

            {pending.length === 0 ? (
              <p className={styles.empty}>
                No tiene nada entre manos. Si la dejas en modo activa, se busca algo que hacer sola.
              </p>
            ) : (
              <div className={styles.list}>
                {pending.map((initiative) => (
                  <div key={initiative.id} className={styles.goal}>
                    <div className={styles.goalHead}>
                      <span className={styles.goalState}>{initiativeStateIcon(initiative.state)}</span>
                      <span className={styles.goalText}>{initiative.goal}</span>
                      <button
                        type="button"
                        className={styles.goalDrop}
                        disabled={busy}
                        title="Soltar este objetivo"
                        onClick={() => void autonomy.dropGoal(initiative.id)}
                      >
                        ✕
                      </button>
                    </div>
                    <span className={styles.goalMeta}>
                      {initiativeStateLabel(initiative.state)} · {driveLabel(initiative.drive)} ·{' '}
                      {initiative.attempts} intento{initiative.attempts === 1 ? '' : 's'} ·{' '}
                      {timeAgo(initiative.created_at)}
                    </span>
                    {initiative.reason && <p className={styles.goalReason}>{initiative.reason}</p>}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ── Lo que ha aprendido ─────────────────────────────────── */}
          <div className={styles.card}>
            <h3 className={styles.cardTitle}>Lo que ha aprendido</h3>

            <div className={styles.goalRow}>
              <input
                className={styles.input}
                placeholder="Enséñale una regla…"
                value={rule}
                onChange={(event) => setRule(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') void addRule()
                }}
              />
              <button
                type="button"
                className={`${styles.button} ${styles.buttonGhost}`}
                disabled={busy || rule.trim().length === 0}
                onClick={() => void addRule()}
              >
                Enseñar
              </button>
            </div>

            {lessons.length === 0 ? (
              <p className={styles.empty}>
                Todavía no ha aprendido nada. Lo aprende sola de lo que le sale bien y mal.
              </p>
            ) : (
              <div className={styles.list}>
                {lessons.slice(0, 8).map((lesson) => (
                  <div
                    key={lesson.id}
                    className={`${styles.lesson} ${lesson.suppressed ? styles.lessonOff : ''}`}
                  >
                    <div className={styles.lessonHead}>
                      <span className={styles.lessonKind}>
                        {lessonKindIcon(lesson.kind)} {lessonKindLabel(lesson.kind)}
                      </span>
                      <span className={styles.lessonWeight}>{lesson.weight.toFixed(2)}</span>
                      <button
                        type="button"
                        className={styles.goalDrop}
                        disabled={busy}
                        title={lesson.suppressed ? 'Volver a activarla' : 'Dejar de usarla'}
                        onClick={() => void autonomy.toggleLesson(lesson.id, !lesson.suppressed)}
                      >
                        {lesson.suppressed ? '○' : '●'}
                      </button>
                    </div>
                    <p className={styles.lessonText}>{lesson.text}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ── Acciones ───────────────────────────────────────────── */}
          <div className={styles.card}>
            <h3 className={styles.cardTitle}>Lo que ha hecho</h3>
            {episodes.length === 0 ? (
              <p className={styles.empty}>
                Todavía no ha actuado por su cuenta. Ponla en modo activa y deja que se maneje.
              </p>
            ) : (
              <div className={styles.list}>
                {episodes.map((episode) => (
                  <motion.div
                    key={episode.id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={styles.episode}
                  >
                    <div className={styles.episodeHead}>
                      <span className={styles.episodeGoal}>{episodeLabel(episode)}</span>
                      <span className={styles.episodeDrive}>{driveLabel(episode.drive)}</span>
                    </div>
                    {episode.said && <p className={styles.episodeSaid}>“{episode.said}”</p>}
                    {episode.result && !episode.said && (
                      <p className={styles.episodeResult}>{episode.result}</p>
                    )}
                    <span className={styles.episodeTime}>
                      {timeAgo(episode.ended_at)}
                      {episode.started_at === episode.ended_at ? '' : ''}
                    </span>
                  </motion.div>
                ))}
              </div>
            )}
          </div>

          {/* ── En directo ─────────────────────────────────────────── */}
          <div className={styles.card}>
            <h3 className={styles.cardTitle}>En directo</h3>
            {events.length === 0 ? (
              <p className={styles.empty}>
                Nadie ha dicho nada todavía. Los escenarios (Minecraft, VRChat, Discord) aparecen
                aquí en cuanto pase algo.
              </p>
            ) : (
              <div className={styles.list}>
                {events.map((event) => (
                  <div key={event.id} className={styles.event}>
                    <span className={styles.eventIcon}>{sourceIcon(event.source)}</span>
                    <div className={styles.eventBody}>
                      <span className={styles.eventLabel}>{eventLabel(event)}</span>
                      {event.text && <p className={styles.eventText}>{event.text}</p>}
                    </div>
                    <span className={styles.eventTime}>{timeAgo(event.at)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}
