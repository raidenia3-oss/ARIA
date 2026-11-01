import { useCallback, useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ariaBackend } from '../../lib/ariaBackend'
import type {
  CreativityIdea,
  CreativityIntegration,
  CreativitySkill,
  CreativityStateResponse,
} from '../../lib/ariaBackend'
import {
  canCreateSkill,
  canForge,
  canProbe,
  effectiveScore,
  ideaStatusLabel,
  integrationKindLabel,
  originLabel,
  percent,
  sortIdeas,
  statusTone,
  weightTone,
} from '../../lib/creativity'
import styles from './styles.module.css'

/**
 * Laboratorio de creatividad de ARIA.
 *
 * Es el sitio donde ARIA propone ideas, aprende de los veredictos y forja
 * skills nuevas. El bucle completo:
 *
 * 1. Pides ideas (o pides que ARIA se mejore a sí misma).
 * 2. Judizas cada idea: «me gusta», «no» o «mejórala».
 * 3. Una idea aceptada se forja en una skill real.
 * 4. La skill se equipa (entra en el prompt del chat) y se ejecuta.
 *
 * Además de ese bucle, el laboratorio permite tres cosas más:
 *
 * * **Resolver** — un problema concreto se convierte en soluciones, y las
 *   soluciones se forjan como cualquier otra idea.
 * * **Crear** — una skill se pide directamente, sin pasar por una idea.
 * * **Integrar** — se registran capacidades externas (herramientas,
 *   servicios) que quedan activas para ARIA.
 *
 * El servidor es la autoridad: esta UI no inventa ideas, pesos ni skills.
 */
export function CreativityLab() {
  const [state, setState] = useState<CreativityStateResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  const [topic, setTopic] = useState('')
  const [theme, setTheme] = useState('')
  const [count, setCount] = useState(2)

  /** Problema a resolver. */
  const [problem, setProblem] = useState('')
  /** Objetivo de la skill que se quiere crear. */
  const [skillGoal, setSkillGoal] = useState('')
  /** Nombre propuesto para la skill (opcional). */
  const [skillName, setSkillName] = useState('')
  /** Instrucciones escritas a mano (opcional). */
  const [skillInstruction, setSkillInstruction] = useState('')
  /** Integración nueva. */
  const [integrationName, setIntegrationName] = useState('')
  const [integrationKind, setIntegrationKind] = useState('herramienta')
  const [integrationTarget, setIntegrationTarget] = useState('')
  const [integrationDescription, setIntegrationDescription] = useState('')

  /** Notas en borrador, por idea. */
  const [notes, setNotes] = useState<Record<string, string>>({})
  /** Idea cuya nota está abierta. */
  const [openNote, setOpenNote] = useState<string | null>(null)
  /** Entrada de ejecución, por skill. */
  const [runInputs, setRunInputs] = useState<Record<string, string>>({})
  /** Salida de la última ejecución, por skill. */
  const [outputs, setOutputs] = useState<Record<string, string>>({})
  /** Resultado de probar una integración. */
  const [probes, setProbes] = useState<Record<string, string>>({})

  const refresh = useCallback(async () => {
    try {
      const payload = await ariaBackend.creativityState()
      setState(payload)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const ideas = useMemo(
    () => (state ? sortIdeas(state.ideas, state.profile) : []),
    [state],
  )
  const skills = state?.skills ?? []
  const integrations = state?.integrations ?? []

  const generate = async () => {
    if (!topic.trim()) {
      setError('Escribe sobre qué quieres ideas.')
      return
    }
    setBusy('generate')
    setError(null)
    try {
      const payload = await ariaBackend.creativityGenerate(topic.trim(), {
        theme: theme.trim() || undefined,
        count,
      })
      if (payload.status === 'error') {
        setError(payload.error ?? 'El laboratorio no pudo generar ideas.')
      }
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  const improve = async () => {
    setBusy('improve')
    setError(null)
    try {
      const payload = await ariaBackend.creativityImprove(topic.trim() || undefined, { count })
      if (payload.status === 'error') {
        setError(payload.error ?? 'ARIA no pudo proponer mejoras.')
      }
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  const feedback = async (idea: CreativityIdea, verdict: 'accept' | 'reject' | 'improve') => {
    setBusy(`feedback:${idea.id}`)
    setError(null)
    try {
      const payload = await ariaBackend.creativityFeedback(
        idea.id,
        verdict,
        verdict === 'improve' ? notes[idea.id] : undefined,
      )
      if (payload.status === 'error') {
        setError(payload.error ?? 'No se pudo registrar el veredicto.')
      }
      setOpenNote(null)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  const forge = async (idea: CreativityIdea) => {
    setBusy(`forge:${idea.id}`)
    setError(null)
    try {
      const payload = await ariaBackend.creativityForge(idea.id)
      if (payload.status === 'error') {
        setError(payload.error ?? 'No se pudo forjar la skill.')
      }
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  const equip = async (skill: CreativitySkill, equipped: boolean) => {
    setBusy(`equip:${skill.id}`)
    setError(null)
    try {
      const payload = await ariaBackend.creativityEquipSkill(skill.id, equipped)
      if (payload.status === 'error') {
        setError(payload.error ?? 'No se pudo equipar la skill.')
      }
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  const run = async (skill: CreativitySkill) => {
    setBusy(`run:${skill.id}`)
    setError(null)
    try {
      const payload = await ariaBackend.creativityRunSkill(skill.id, runInputs[skill.id] ?? '')
      if (payload.status === 'error') {
        setError(payload.error ?? 'La skill no se pudo ejecutar.')
        setOutputs((prev) => ({
          ...prev,
          [skill.id]: payload.error ?? 'La skill no se pudo ejecutar.',
        }))
      } else {
        setOutputs((prev) => ({ ...prev, [skill.id]: payload.output ?? '' }))
      }
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  /** Resuelve un problema: las soluciones llegan como ideas más. */
  const solve = async () => {
    if (!problem.trim()) {
      setError('Escribe qué problema hay que resolver.')
      return
    }
    setBusy('solve')
    setError(null)
    try {
      const payload = await ariaBackend.creativitySolve(problem.trim(), { count })
      if (payload.status === 'error') {
        setError(payload.error ?? 'ARIA no pudo buscar soluciones.')
      }
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  /** Crea una skill nueva sin pasar por una idea. */
  const createSkill = async () => {
    if (!canCreateSkill(skillGoal)) {
      setError('Escribe qué debe hacer la skill.')
      return
    }
    setBusy('create-skill')
    setError(null)
    try {
      const payload = await ariaBackend.creativityCreateSkill(skillGoal.trim(), {
        name: skillName.trim() || undefined,
        instruction: skillInstruction.trim() || undefined,
      })
      if (payload.status === 'error') {
        setError(payload.error ?? 'No se pudo crear la skill.')
      } else {
        setSkillGoal('')
        setSkillName('')
        setSkillInstruction('')
      }
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  /** ARIA reescribe su propia skill para mejorarla. */
  const improveSkill = async (skill: CreativitySkill) => {
    setBusy(`improve-skill:${skill.id}`)
    setError(null)
    try {
      const payload = await ariaBackend.creativityImproveSkill(skill.id)
      if (payload.status === 'error') {
        setError(payload.error ?? 'No se pudo mejorar la skill.')
      }
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  /** Registra una capacidad externa. */
  const registerIntegration = async () => {
    if (!integrationName.trim() || !integrationTarget.trim()) {
      setError('La integración necesita nombre y destino.')
      return
    }
    setBusy('register-integration')
    setError(null)
    try {
      const payload = await ariaBackend.creativityRegisterIntegration({
        name: integrationName.trim(),
        kind: integrationKind,
        target: integrationTarget.trim(),
        description: integrationDescription.trim() || undefined,
      })
      if (payload.status === 'error') {
        setError(payload.error ?? 'No se pudo registrar la integración.')
      } else {
        setIntegrationName('')
        setIntegrationTarget('')
        setIntegrationDescription('')
      }
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  /** Activa o desactiva una integración. */
  const toggleIntegration = async (integration: CreativityIntegration, enabled: boolean) => {
    setBusy(`toggle:${integration.id}`)
    setError(null)
    try {
      const payload = await ariaBackend.creativityToggleIntegration(integration.id, enabled)
      if (payload.status === 'error') {
        setError(payload.error ?? 'No se pudo cambiar la integración.')
      }
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  /** Comprueba que un servicio HTTP responde. */
  const probeIntegration = async (integration: CreativityIntegration) => {
    setBusy(`probe:${integration.id}`)
    setError(null)
    try {
      const payload = await ariaBackend.creativityProbeIntegration(integration.id)
      const summary =
        payload.status === 'error'
          ? (payload.error ?? 'La integración no respondió.')
          : `HTTP ${payload.http_status} · ${(payload.body ?? '').slice(0, 220)}`
      setProbes((prev) => ({ ...prev, [integration.id]: summary }))
      if (payload.status === 'error') {
        setError(summary)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  if (loading) {
    return (
      <div className={styles.loading}>
        <span className={styles.spinner} />
        Abriendo el laboratorio…
      </div>
    )
  }

  const stats = state?.stats
  const profile = state?.profile ?? []

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <div>
          <span className={styles.kicker}>LABORATORIO</span>
          <h2 className={styles.title}>Creatividad de ARIA</h2>
          <p className={styles.subtitle}>
            ARIA propone ideas, aprende de tus veredictos y forja skills con lo que apruebas.
          </p>
        </div>
        <div className={styles.stats}>
          <Stat label="IDEAS" value={stats?.ideas ?? 0} />
          <Stat label="ACEPTADAS" value={stats?.accepted ?? 0} tone="good" />
          <Stat label="RECHAZADAS" value={stats?.rejected ?? 0} tone="bad" />
          <Stat label="FORJADAS" value={stats?.built ?? 0} tone="accent" />
          <Stat label="CICLOS" value={stats?.cycles ?? 0} />
          <Stat label="INTEGRACIONES" value={stats?.active_integrations ?? 0} tone="accent" />
        </div>
      </header>

      {error && <p className={styles.error}>{error}</p>}

      <div className={styles.columns}>
        <section className={styles.column}>
          <div className={styles.card}>
            <h3 className={styles.cardTitle}>Pedir ideas</h3>
            <label className={styles.field}>
              <span className={styles.fieldLabel}>TEMA</span>
              <input
                className={styles.input}
                value={topic}
                placeholder="la voz, la memoria, el árbol de habilidades…"
                onChange={(event) => setTopic(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') void generate()
                }}
              />
            </label>
            <label className={styles.field}>
              <span className={styles.fieldLabel}>CATEGORÍA (opcional)</span>
              <input
                className={styles.input}
                value={theme}
                placeholder="voz"
                onChange={(event) => setTheme(event.target.value)}
              />
            </label>
            <label className={styles.field}>
              <span className={styles.fieldLabel}>CUÁNTAS · {count}</span>
              <input
                className={styles.slider}
                type="range"
                min={1}
                max={12}
                value={count}
                onChange={(event) => setCount(Number(event.target.value))}
              />
            </label>
            <div className={styles.buttonRow}>
              <button
                type="button"
                className={`${styles.button} ${styles.buttonPrimary}`}
                onClick={() => void generate()}
                disabled={busy !== null}
              >
                {busy === 'generate' ? 'Pensando…' : 'Generar ideas'}
              </button>
              <button
                type="button"
                className={`${styles.button} ${styles.buttonGhost}`}
                onClick={() => void improve()}
                disabled={busy !== null}
                title="ARIA propone mejoras de sí misma"
              >
                {busy === 'improve' ? 'Pensando…' : 'Que ARIA se mejore'}
              </button>
            </div>
            <p className={styles.hint}>
              El modelo local corre por CPU: cada idea puede tardar minutos. Si el modelo no
              responde, ARIA propone ideas de reserva al instante.
            </p>
          </div>

          <div className={styles.card}>
            <h3 className={styles.cardTitle}>Resolver un problema</h3>
            <label className={styles.field}>
              <span className={styles.fieldLabel}>PROBLEMA</span>
              <textarea
                className={styles.textarea}
                value={problem}
                rows={3}
                placeholder="la cámara no arranca cuando el auricular está conectado…"
                onChange={(event) => setProblem(event.target.value)}
              />
            </label>
            <div className={styles.buttonRow}>
              <button
                type="button"
                className={`${styles.button} ${styles.buttonPrimary}`}
                onClick={() => void solve()}
                disabled={busy !== null}
              >
                {busy === 'solve' ? 'Pensando…' : 'Buscar soluciones'}
              </button>
            </div>
            <p className={styles.hint}>
              Las soluciones llegan como ideas: se juzgan igual y se pueden forjar en una skill.
            </p>
          </div>

          <div className={styles.card}>
            <h3 className={styles.cardTitle}>Crear una skill</h3>
            <label className={styles.field}>
              <span className={styles.fieldLabel}>QUÉ DEBE HACER</span>
              <input
                className={styles.input}
                value={skillGoal}
                placeholder="resumir lo que dice el auricular en tres frases"
                onChange={(event) => setSkillGoal(event.target.value)}
              />
            </label>
            <label className={styles.field}>
              <span className={styles.fieldLabel}>NOMBRE (opcional)</span>
              <input
                className={styles.input}
                value={skillName}
                placeholder="resumir_voz"
                onChange={(event) => setSkillName(event.target.value)}
              />
            </label>
            <label className={styles.field}>
              <span className={styles.fieldLabel}>INSTRUCCIONES (opcional)</span>
              <textarea
                className={styles.textarea}
                value={skillInstruction}
                rows={2}
                placeholder="Si las escribes tú, ARIA las respeta tal cual."
                onChange={(event) => setSkillInstruction(event.target.value)}
              />
            </label>
            <div className={styles.buttonRow}>
              <button
                type="button"
                className={`${styles.button} ${styles.buttonPrimary}`}
                onClick={() => void createSkill()}
                disabled={busy !== null}
              >
                {busy === 'create-skill' ? 'Escribiendo…' : 'Crear skill'}
              </button>
            </div>
            <p className={styles.hint}>
              Sin pasar por una idea: la skill nace, se equipa y se ejecuta como cualquier otra.
            </p>
          </div>

          <div className={styles.card}>
            <h3 className={styles.cardTitle}>Lo que ARIA ha aprendido</h3>
            {profile.length === 0 ? (
              <p className={styles.empty}>
                Todavía no hay veredictos. Acepta o rechaza una idea y ARIA empieza a aprender qué
                te gusta.
              </p>
            ) : (
              profile.map((entry) => {
                const tone = weightTone(entry.weight)
                const width = Math.min(Math.abs(entry.weight), 1) * 100
                return (
                  <div key={entry.theme} className={styles.profileRow}>
                    <span className={styles.profileTheme}>{entry.theme}</span>
                    <div className={styles.profileTrack}>
                      <div
                        className={`${styles.profileFill} ${
                          tone === 'like'
                            ? styles.profileFillLike
                            : tone === 'dislike'
                              ? styles.profileFillDislike
                              : ''
                        }`}
                        style={{ width: `${width}%` }}
                      />
                    </div>
                    <span className={styles.profileValue}>
                      {entry.weight > 0 ? '+' : ''}
                      {entry.weight.toFixed(2)}
                    </span>
                  </div>
                )
              })
            )}
          </div>
        </section>

        <section className={styles.column}>
          <div className={styles.card}>
            <h3 className={styles.cardTitle}>
              Ideas <span className={styles.count}>{ideas.length}</span>
              {state?.last_engine && (
                <span className={styles.engine} title="De dónde salieron las últimas ideas">
                  {state.last_engine}
                </span>
              )}
            </h3>
            {ideas.length === 0 ? (
              <p className={styles.empty}>
                Todavía no hay ideas. Pide unas arriba y ARIA empieza a proponer.
              </p>
            ) : (
              <div className={styles.list}>
                <AnimatePresence initial={false}>
                  {ideas.map((idea) => (
                    <motion.article
                      key={idea.id}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, height: 0 }}
                      className={styles.idea}
                    >
                      <div className={styles.ideaHead}>
                        <h4 className={styles.ideaTitle}>{idea.title}</h4>
                        <span className={`${styles.status} ${styles[statusTone(idea.status)] ?? ''}`}>
                          {ideaStatusLabel(idea.status)}
                        </span>
                      </div>

                      <div className={styles.ideaMeta}>
                        <span className={styles.theme}>{idea.theme}</span>
                        {idea.origin !== 'idea' && (
                          <span className={styles.theme}>{originLabel(idea.origin)}</span>
                        )}
                        <span className={styles.score}>{percent(effectiveScore(idea, profile))}</span>
                      </div>

                      {idea.summary && <p className={styles.ideaSummary}>{idea.summary}</p>}
                      {idea.detail && <p className={styles.ideaDetail}>{idea.detail}</p>}

                      <div className={styles.meters}>
                        <Meter label="NOVEDAD" value={idea.novelty} />
                        <Meter label="VIABILIDAD" value={idea.feasibility} />
                        <Meter label="IMPACTO" value={idea.impact} />
                      </div>

                      {idea.note && <p className={styles.note}>Nota: {idea.note}</p>}

                      <div className={styles.ideaActions}>
                        <button
                          type="button"
                          className={`${styles.action} ${styles.actionGood}`}
                          onClick={() => void feedback(idea, 'accept')}
                          disabled={busy !== null}
                        >
                          ✓ Me gusta
                        </button>
                        <button
                          type="button"
                          className={`${styles.action} ${styles.actionBad}`}
                          onClick={() => void feedback(idea, 'reject')}
                          disabled={busy !== null}
                        >
                          ✗ No
                        </button>
                        <button
                          type="button"
                          className={`${styles.action} ${styles.actionGhost}`}
                          onClick={() => setOpenNote(openNote === idea.id ? null : idea.id)}
                          disabled={busy !== null}
                        >
                          ↻ Mejórala
                        </button>
                        {canForge(idea) && (
                          <button
                            type="button"
                            className={`${styles.action} ${styles.actionAccent}`}
                            onClick={() => void forge(idea)}
                            disabled={busy !== null}
                          >
                            ⚒ Forjar skill
                          </button>
                        )}
                        {idea.skill_id && (
                          <span className={styles.builtTag}>skill {idea.skill_id}</span>
                        )}
                      </div>

                      {openNote === idea.id && (
                        <div className={styles.noteBox}>
                          <input
                            className={styles.input}
                            placeholder="¿Qué le falta?"
                            value={notes[idea.id] ?? ''}
                            onChange={(event) =>
                              setNotes((prev) => ({ ...prev, [idea.id]: event.target.value }))
                            }
                            onKeyDown={(event) => {
                              if (event.key === 'Enter') void feedback(idea, 'improve')
                            }}
                          />
                          <button
                            type="button"
                            className={`${styles.button} ${styles.buttonGhost}`}
                            onClick={() => void feedback(idea, 'improve')}
                            disabled={busy !== null}
                          >
                            Guardar
                          </button>
                        </div>
                      )}
                    </motion.article>
                  ))}
                </AnimatePresence>
              </div>
            )}
          </div>

          <div className={styles.card}>
            <h3 className={styles.cardTitle}>
              Skills creadas por ARIA <span className={styles.count}>{skills.length}</span>
            </h3>
            {skills.length === 0 ? (
              <p className={styles.empty}>
                Ninguna todavía. Acepta una idea y forja la primera skill.
              </p>
            ) : (
              <div className={styles.list}>
                {skills.map((skill) => (
                  <div key={skill.id} className={styles.skill}>
                    <div className={styles.ideaHead}>
                      <h4 className={styles.ideaTitle}>{skill.name}</h4>
                      <span className={styles.theme}>{skill.theme}</span>
                    </div>
                    <p className={styles.ideaSummary}>{skill.description}</p>
                    <p className={styles.runs}>
                      ejecutada {skill.runs} veces
                      {skill.revisions > 0 ? ` · mejorada ${skill.revisions} veces` : ''}
                    </p>

                    <div className={styles.skillActions}>
                      <input
                        className={styles.input}
                        placeholder="entrada para la skill…"
                        value={runInputs[skill.id] ?? ''}
                        onChange={(event) =>
                          setRunInputs((prev) => ({ ...prev, [skill.id]: event.target.value }))
                        }
                      />
                      <button
                        type="button"
                        className={`${styles.button} ${styles.buttonPrimary}`}
                        onClick={() => void run(skill)}
                        disabled={busy !== null}
                      >
                        Ejecutar
                      </button>
                      <button
                        type="button"
                        className={`${styles.button} ${skill.equipped ? styles.buttonAccent : styles.buttonGhost}`}
                        onClick={() => void equip(skill, !skill.equipped)}
                        disabled={busy !== null}
                        title="Equipada: entra en el prompt del chat"
                      >
                        {skill.equipped ? 'Equipada' : 'Equipar'}
                      </button>
                      <button
                        type="button"
                        className={`${styles.button} ${styles.buttonGhost}`}
                        onClick={() => void improveSkill(skill)}
                        disabled={busy !== null}
                        title="ARIA reescribe la skill para mejorarla"
                      >
                        {busy === `improve-skill:${skill.id}` ? 'Mejorando…' : 'Mejorar'}
                      </button>
                    </div>

                    {outputs[skill.id] && (
                      <pre className={styles.output}>{outputs[skill.id]}</pre>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className={styles.card}>
            <h3 className={styles.cardTitle}>
              Integraciones <span className={styles.count}>{integrations.length}</span>
            </h3>
            {integrations.length === 0 ? (
              <p className={styles.empty}>
                Ninguna todavía. Registra una herramienta o un servicio y ARIA lo usa como
                cualquier otra capacidad.
              </p>
            ) : (
              <div className={styles.list}>
                {integrations.map((integration) => (
                  <div key={integration.id} className={styles.skill}>
                    <div className={styles.ideaHead}>
                      <h4 className={styles.ideaTitle}>{integration.name}</h4>
                      <span className={styles.theme}>
                        {integrationKindLabel(integration.kind)}
                      </span>
                    </div>
                    <p className={styles.ideaSummary}>{integration.description}</p>
                    <p className={styles.runs}>
                      {integration.target} · probada {integration.calls} veces
                    </p>
                    <div className={styles.skillActions}>
                      <button
                        type="button"
                        className={`${styles.button} ${
                          integration.enabled ? styles.buttonAccent : styles.buttonGhost
                        }`}
                        onClick={() => void toggleIntegration(integration, !integration.enabled)}
                        disabled={busy !== null}
                        title="Activa: la integración entra en el prompt del chat"
                      >
                        {integration.enabled ? 'Activa' : 'Inactiva'}
                      </button>
                      {canProbe(integration) && (
                        <button
                          type="button"
                          className={`${styles.button} ${styles.buttonGhost}`}
                          onClick={() => void probeIntegration(integration)}
                          disabled={busy !== null}
                          title="Comprueba que el servicio responde"
                        >
                          {busy === `probe:${integration.id}` ? 'Probando…' : 'Probar'}
                        </button>
                      )}
                    </div>
                    {probes[integration.id] && (
                      <pre className={styles.output}>{probes[integration.id]}</pre>
                    )}
                  </div>
                ))}
              </div>
            )}

            <div className={styles.divider} />

            <label className={styles.field}>
              <span className={styles.fieldLabel}>NOMBRE</span>
              <input
                className={styles.input}
                value={integrationName}
                placeholder="nmap"
                onChange={(event) => setIntegrationName(event.target.value)}
              />
            </label>
            <label className={styles.field}>
              <span className={styles.fieldLabel}>TIPO</span>
              <select
                className={styles.input}
                value={integrationKind}
                onChange={(event) => setIntegrationKind(event.target.value)}
              >
                <option value="herramienta">herramienta</option>
                <option value="servicio">servicio</option>
                <option value="módulo">módulo</option>
              </select>
            </label>
            <label className={styles.field}>
              <span className={styles.fieldLabel}>DESTINO</span>
              <input
                className={styles.input}
                value={integrationTarget}
                placeholder="nmap -sV · http://localhost:11434"
                onChange={(event) => setIntegrationTarget(event.target.value)}
              />
            </label>
            <label className={styles.field}>
              <span className={styles.fieldLabel}>PARA QUÉ SIRVE (opcional)</span>
              <input
                className={styles.input}
                value={integrationDescription}
                placeholder="escanea puertos de la red local"
                onChange={(event) => setIntegrationDescription(event.target.value)}
              />
            </label>
            <div className={styles.buttonRow}>
              <button
                type="button"
                className={`${styles.button} ${styles.buttonPrimary}`}
                onClick={() => void registerIntegration()}
                disabled={busy !== null}
              >
                {busy === 'register-integration' ? 'Registrando…' : 'Integrar'}
              </button>
            </div>
            <p className={styles.hint}>
              Las integraciones activas salen en el prompt del chat: ARIA sabe qué tiene a mano.
            </p>
          </div>
        </section>
      </div>
    </div>
  )
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string
  value: number
  tone?: 'good' | 'bad' | 'accent'
}) {
  const toneClass = tone ? styles[tone] ?? '' : ''
  return (
    <div className={`${styles.stat} ${toneClass}`}>
      <span className={styles.statValue}>{value}</span>
      <span className={styles.statLabel}>{label}</span>
    </div>
  )
}

function Meter({ label, value }: { label: string; value: number }) {
  return (
    <div className={styles.meter}>
      <span className={styles.meterLabel}>{label}</span>
      <div className={styles.meterTrack}>
        <div className={styles.meterFill} style={{ width: `${percent(value)}%` }} />
      </div>
      <span className={styles.meterValue}>{percent(value)}</span>
    </div>
  )
}
