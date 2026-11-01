import { useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { GESTURE_ACTIONS, GESTURE_GLYPH } from '../../lib/gestures'
import { emitGesture } from '../../lib/gestureActions'
import { useCameraGestures, type UseCameraGestures } from '../../hooks/useCameraGestures'
import { useAudioDevices } from '../../hooks/useAudioDevices'
import styles from './styles.module.css'

interface LogEntry {
  id: number
  at: number
  text: string
  tone: 'info' | 'ok' | 'warn' | 'error'
}

/** Conexiones de la malla de la mano, en el orden de MediaPipe. */
const HAND_CONNECTIONS: Array<[number, number]> = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [5, 9], [9, 10], [10, 11], [11, 12],
  [9, 13], [13, 14], [14, 15], [15, 16],
  [13, 17], [17, 18], [18, 19], [19, 20],
  [0, 17],
]

export interface GestureEyeProps {
  /**
   * Instancia de la cámara compartida con el resto de la app.
   *
   * La cámara es un recurso único: si el canal de voz y esta consola
   * tuvieran cada una su propia instancia, la identidad se calcularía dos
   * veces y la cámara se abriría dos veces. Si no se pasa una, el componente
   * usa la suya (así sigue sirviendo por sí solo).
   */
  gestures?: UseCameraGestures
}

/**
 * Consola de gestos: cámara, rostro, manos y auricular.
 *
 * Tres cosas en una pantalla porque forman una sola decisión: ARIA sólo
 * obedece un gesto si sabe quién eres, y habla por el micrófono que tú
 * elegiste.
 */
export function GestureEye({ gestures: shared }: GestureEyeProps = {}) {
  const ownGestures = useCameraGestures()
  const gestures = shared ?? ownGestures
  const audio = useAudioDevices()
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const [log, setLog] = useState<LogEntry[]>([])
  const [micLevel, setMicLevel] = useState(0)
  const [headsetStream, setHeadsetStream] = useState<MediaStream | null>(null)
  const logId = useRef(0)

  const push = useCallback((text: string, tone: LogEntry['tone'] = 'info') => {
    setLog((prev) => [
      { id: logId.current++, at: Date.now(), text, tone },
      ...prev.slice(0, 40),
    ])
  }, [])

  /* ── Overlay de landmarks ─────────────────────────────────────── */

  useEffect(() => {
    const canvas = canvasRef.current
    const video = gestures.videoRef.current
    if (!canvas || !video) return

    const draw = () => {
      const ctx = canvas.getContext('2d')
      if (!ctx) {
        requestAnimationFrame(draw)
        return
      }
      const w = video.clientWidth || 640
      const h = video.clientHeight || 480
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w
        canvas.height = h
      }
      ctx.clearRect(0, 0, w, h)

      const hand = gestures.handLandmarks
      if (hand && hand.length >= 21) {
        ctx.strokeStyle = 'rgba(56, 189, 248, 0.9)'
        ctx.lineWidth = 2
        for (const [a, b] of HAND_CONNECTIONS) {
          const p1 = hand[a]
          const p2 = hand[b]
          if (!p1 || !p2) continue
          ctx.beginPath()
          ctx.moveTo(p1.x * w, p1.y * h)
          ctx.lineTo(p2.x * w, p2.y * h)
          ctx.stroke()
        }
        ctx.fillStyle = '#e0f2fe'
        for (const p of hand) {
          ctx.beginPath()
          ctx.arc(p.x * w, p.y * h, 3, 0, Math.PI * 2)
          ctx.fill()
        }
      }

      const face = gestures.faceLandmarks
      if (face && face.length > 100) {
        // Caja del rostro: suficiente para saber que hay alguien delante.
        const xs = face.map((p) => p.x)
        const ys = face.map((p) => p.y)
        const minX = Math.min(...xs) * w
        const maxX = Math.max(...xs) * w
        const minY = Math.min(...ys) * h
        const maxY = Math.max(...ys) * h
        const confirmed = gestures.identity === 'confirmado'
        ctx.strokeStyle = confirmed ? 'rgba(52, 211, 153, 0.9)' : 'rgba(251, 191, 36, 0.75)'
        ctx.setLineDash([6, 4])
        ctx.lineWidth = 1.5
        ctx.strokeRect(minX, minY, maxX - minX, maxY - minY)
        ctx.setLineDash([])
      }

      requestAnimationFrame(draw)
    }

    const id = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(id)
  }, [gestures.handLandmarks, gestures.faceLandmarks, gestures.identity, gestures.videoRef])

  /* ── Gesto confirmado ─────────────────────────────────────────── */

  useEffect(() => {
    const triggered = gestures.lastTriggered
    if (!triggered) return
    const action = GESTURE_ACTIONS.find((a) => a.gesture === triggered.gesture)
    if (!action) return
    if (!gestures.canTrigger(triggered.gesture)) {
      push(`«${action.label}» bloqueado: identidad sin confirmar`, 'warn')
      return
    }
    // El gesto no se queda en un log: emite la acción y quien tenga la
    // capacidad de ejecutarla la ejecuta (chat, voz, navegación).
    const emitted = emitGesture(triggered.gesture)
    push(
      emitted
        ? `Gesto «${action.label}» → ${action.description}`
        : `Gesto «${action.label}» recibido (sin acción asociada)`,
      'ok',
    )
  }, [gestures.lastTriggered, gestures.canTrigger, push])

  /* ── Medidor de nivel del micrófono ──────────────────────────── */

  useEffect(() => {
    if (!headsetStream) {
      setMicLevel(0)
      return
    }
    const Ctor = window.AudioContext
    if (!Ctor) return
    const ctx = new Ctor()
    const source = ctx.createMediaStreamSource(headsetStream)
    const analyser = ctx.createAnalyser()
    analyser.fftSize = 512
    source.connect(analyser)
    const data = new Uint8Array(analyser.frequencyBinCount)

    const tick = () => {
      analyser.getByteFrequencyData(data)
      let sum = 0
      for (const v of data) sum += v
      setMicLevel(Math.min(1, sum / data.length / 90))
      requestAnimationFrame(tick)
    }
    tick()
    return () => {
      void ctx.close()
    }
  }, [headsetStream])

  const startCamera = useCallback(async () => {
    await gestures.start()
    if (gestures.error) {
      push(`Cámara: ${gestures.error}`, 'error')
    } else {
      push('Cámara activada', 'ok')
    }
  }, [gestures, push])

  const connectHeadset = useCallback(async () => {
    const stream = await audio.openHeadsetStream()
    if (stream) {
      setHeadsetStream(stream)
      push(`Micrófono: ${audio.headset?.label ?? 'entrada por defecto'}`, 'ok')
    } else {
      push('No se pudo abrir ningún micrófono', 'error')
    }
  }, [audio, push])

  const identityTone =
    gestures.identity === 'confirmado' ? 'ok' : gestures.identity === 'probable' ? 'warn' : 'idle'

  return (
    <div className={styles.container}>
      <div className={styles.left}>
        <div className={styles.viewport}>
          <video
            ref={gestures.videoRef}
            className={styles.video}
            muted
            playsInline
            style={{ transform: 'scaleX(-1)' }}
          />
          <canvas ref={canvasRef} className={styles.canvas} />

          {!gestures.active && (
            <div className={styles.viewportOverlay}>
              <span className={styles.overlayGlyph}>◎</span>
              <p>La cámara está apagada</p>
              <button type="button" className={styles.primary} onClick={() => void startCamera()}>
                {gestures.loading ? 'Cargando modelos…' : 'Activar cámara'}
              </button>
              {gestures.error && <p className={styles.error}>{gestures.error}</p>}
            </div>
          )}

          {gestures.active && (
            <div className={styles.viewportBadges}>
              <span className={`${styles.badge} ${styles.badgeLive}`}>● EN VIVO</span>
              <span className={styles.badge}>
                {GESTURE_GLYPH[gestures.gesture]} {gestures.gesture}
              </span>
            </div>
          )}
        </div>

        <div className={styles.statusRow}>
          <div className={`${styles.statusCard} ${styles[identityTone]}`}>
            <span className={styles.statusLabel}>IDENTIDAD</span>
            <span className={styles.statusValue}>
              {gestures.enrolled ? gestures.identity : 'sin enrolar'}
            </span>
            {gestures.enrolled && (
              <span className={styles.statusHint}>
                {Math.round(gestures.identityScore * 100)}% de similitud
              </span>
            )}
          </div>

          <div className={`${styles.statusCard} ${audio.headset ? styles.ok : styles.warn}`}>
            <span className={styles.statusLabel}>AURICULAR</span>
            <span className={styles.statusValue}>
              {audio.headset ? 'con micrófono' : 'no detectado'}
            </span>
            <span className={styles.statusHint}>
              {audio.headset?.label ?? `${audio.inputs.length} entradas`}
            </span>
          </div>

          <div className={styles.statusCard}>
            <span className={styles.statusLabel}>NIVEL MIC</span>
            <div className={styles.meter}>
              <div
                className={styles.meterFill}
                style={{ width: `${Math.round(micLevel * 100)}%` }}
              />
            </div>
            <span className={styles.statusHint}>
              {headsetStream ? 'escuchando' : 'micrófono cerrado'}
            </span>
          </div>
        </div>
      </div>

      <div className={styles.right}>
        <section className={styles.panel}>
          <h3 className={styles.panelTitle}>Identidad</h3>
          <p className={styles.panelText}>
            ARIA compara el rostro con tu perfil antes de obedecer las órdenes que
            tocan el sistema.
          </p>
          <div className={styles.enrollRow}>
            <button
              type="button"
              className={styles.primary}
              disabled={!gestures.active || gestures.enrollProgress > 0}
              onClick={() => {
                void gestures.enroll('user').then((done) => {
                  if (done) push('Identidad enrolada', 'ok')
                })
              }}
            >
              {gestures.enrollProgress > 0
                ? `Enrolando ${Math.round(gestures.enrollProgress * 100)}%`
                : gestures.enrolled
                  ? 'Re-enrolar'
                  : 'Enrolar rostro'}
            </button>
            {gestures.enrolled && (
              <button type="button" className={styles.ghost} onClick={gestures.forget}>
                Olvidar
              </button>
            )}
          </div>
        </section>

        <section className={styles.panel}>
          <h3 className={styles.panelTitle}>Micrófono</h3>
          <p className={styles.panelText}>
            {audio.permission === 'granted' || audio.labelled
              ? 'ARIA usa el auricular con micrófono como canal principal para hablar contigo.'
              : 'Concede el permiso de micrófono para que ARIA vea los nombres de los dispositivos.'}
          </p>
          <div className={styles.enrollRow}>
            <button type="button" className={styles.primary} onClick={() => void audio.requestPermission()}>
              Detectar auricular
            </button>
            <button
              type="button"
              className={styles.ghost}
              onClick={() => void connectHeadset()}
              disabled={!audio.inputs.length}
            >
              Usar
            </button>
          </div>
          {audio.inputs.length > 0 && (
            <ul className={styles.deviceList}>
              {audio.inputs.map((device) => (
                <li
                  key={device.deviceId}
                  className={`${styles.device} ${device.isHeadset ? styles.deviceHeadset : ''}`}
                >
                  <span>{device.label || 'Entrada sin nombre'}</span>
                  {device.isHeadset && <span className={styles.deviceTag}>AURICULAR</span>}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className={styles.panel}>
          <h3 className={styles.panelTitle}>Gestos</h3>
          <ul className={styles.gestureList}>
            {GESTURE_ACTIONS.map((action) => {
              const armed = gestures.canTrigger(action.gesture)
              const active = gestures.gesture === action.gesture
              return (
                <li
                  key={action.gesture}
                  className={`${styles.gesture} ${active ? styles.gestureActive : ''} ${
                    armed ? '' : styles.gestureLocked
                  }`}
                >
                  <span className={styles.gestureGlyph}>{GESTURE_GLYPH[action.gesture]}</span>
                  <span className={styles.gestureBody}>
                    <span className={styles.gestureLabel}>{action.label}</span>
                    <span className={styles.gestureDescription}>{action.description}</span>
                  </span>
                  {!armed && <span className={styles.gestureLock}>identidad</span>}
                </li>
              )
            })}
          </ul>
        </section>

        <section className={styles.panel}>
          <h3 className={styles.panelTitle}>Registro</h3>
          <div className={styles.log}>
            <AnimatePresence initial={false}>
              {log.map((entry) => (
                <motion.div
                  key={entry.id}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0 }}
                  className={`${styles.logEntry} ${styles[`log${entry.tone}`]}`}
                >
                  {entry.text}
                </motion.div>
              ))}
            </AnimatePresence>
            {log.length === 0 && <p className={styles.logEmpty}>Sin actividad todavía.</p>}
          </div>
        </section>
      </div>
    </div>
  )
}
