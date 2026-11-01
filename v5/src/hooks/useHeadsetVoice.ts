import { useCallback, useEffect, useRef, useState } from 'react'
import { ariaBackend } from '../lib/ariaBackend'
import { pickVoice, VoiceGate } from '../lib/voiceGate'
import type { IdentityVerdict } from '../lib/identity'
import type { AudioInputDevice } from './useAudioDevices'

/**
 * Canal de voz de ARIA sobre el auricular.
 *
 * El auricular con micrófono es el canal real de comunicación: se graba
 * desde ese dispositivo, se corta cada frase porsegments de voz, se
 * transcribe en el backend (faster-whisper) y la orden llega al chat.
 *
 * La cámara decide si la orden vale: si hay un perfil de identidad
 * enrolado y la cámara no reconoce al usuario, el micrófono no manda
 * nada.
 */

/** Fragmentos de audio que se guardan antes de la frase (contexto previo). */
const PREROLL_CHUNKS = 6
/** Cada cuánto se recorta el audio en trozos. */
const CHUNK_MS = 200
/** Cada cuánto se mide el nivel del micrófono. */
const LEVEL_POLL_MS = 50
/** Tamaño de la ventana del analizador. */
const FFT_SIZE = 512

export interface HeadsetVoiceOptions {
  /** Auricular detectado. Si es `null` se usa la entrada por defecto. */
  device: AudioInputDevice | null
  /** Veredicto de identidad de la cámara. */
  identity: IdentityVerdict
  /** `true` si ya hay un rostro enrolado contra el que comparar. */
  enrolled: boolean
  /** Idioma de la transcripción y de la voz de ARIA. */
  language?: string
  /** Callback con la frase transcrita. */
  onCommand?: (text: string) => void | Promise<void>
}

export interface HeadsetVoiceController {
  /** `true` mientras el micrófono está abierto. */
  listening: boolean
  /** `true` mientras se transcribe una frase. */
  transcribing: boolean
  /** Nivel del micrófono (0..1). */
  level: number
  /** Última frase transcrita. */
  transcript: string
  /** Último error legible. */
  error: string | null
  /** `true` si la identidad impide usar el canal. */
  blocked: boolean
  start: () => Promise<void>
  stop: () => void
  /** Habla un texto con la voz de ARIA. */
  speak: (text: string) => void
}

function pickMimeType(): string {
  if (typeof MediaRecorder === 'undefined') return ''
  const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus']
  for (const candidate of candidates) {
    if (MediaRecorder.isTypeSupported?.(candidate)) return candidate
  }
  return ''
}

export function useHeadsetVoice(options: HeadsetVoiceOptions): HeadsetVoiceController {
  const { device, identity, enrolled, language = 'es' } = options

  const [listening, setListening] = useState(false)
  const [transcribing, setTranscribing] = useState(false)
  const [level, setLevel] = useState(0)
  const [transcript, setTranscript] = useState('')
  const [error, setError] = useState<string | null>(null)

  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const contextRef = useRef<AudioContext | null>(null)
  const timerRef = useRef<number | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const startIndexRef = useRef(0)
  const gateRef = useRef(new VoiceGate())
  const processingRef = useRef(false)
  const optionsRef = useRef(options)
  optionsRef.current = options

  const blocked = enrolled && identity !== 'confirmado' && identity !== 'probable'

  /* ── Transcripción de una frase ───────────────────────────────── */

  const transcribe = useCallback(async (blob: Blob) => {
    if (processingRef.current) return
    processingRef.current = true
    setTranscribing(true)
    try {
      const response = await ariaBackend.voiceStt(blob, { language })
      if (response.status !== 'ok') {
        setError(response.error ?? 'El motor de voz no pudo transcribir')
        return
      }
      const text = (response.text ?? '').trim()
      if (!text) {
        setError('No se detectó voz en el auricular')
        return
      }
      setError(null)
      setTranscript(text)
      await optionsRef.current.onCommand?.(text)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      processingRef.current = false
      setTranscribing(false)
    }
  }, [language])

  /* ── Arranque ──────────────────────────────────────────────────── */

  const start = useCallback(async () => {
    if (recorderRef.current) return
    if (blocked) {
      setError('La cámara no te ha identificado: el micrófono queda en pausa')
      return
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setError('Este entorno no expone micrófono')
      return
    }
    if (typeof MediaRecorder === 'undefined') {
      setError('Este navegador no puede grabar audio')
      return
    }

    setError(null)
    try {
      const target = device
      const constraints: MediaStreamConstraints = {
        audio: target && target.deviceId && target.deviceId !== 'default'
          ? {
              deviceId: { exact: target.deviceId },
              echoCancellation: true,
              noiseSuppression: true,
              autoGainControl: true,
            }
          : { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      }
      const stream = await navigator.mediaDevices.getUserMedia(constraints)
      streamRef.current = stream

      const mimeType = pickMimeType()
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
      chunksRef.current = []
      startIndexRef.current = 0
      gateRef.current = new VoiceGate()

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) chunksRef.current.push(event.data)
      }
      recorder.onstop = () => {
        chunksRef.current = []
        startIndexRef.current = 0
      }
      recorder.start(CHUNK_MS)
      recorderRef.current = recorder

      /* Medidor de nivel: alimenta el segmentador de frases. */
      const Ctor = window.AudioContext
      if (Ctor) {
        const ctx = new Ctor()
        contextRef.current = ctx
        const source = ctx.createMediaStreamSource(stream)
        const analyser = ctx.createAnalyser()
        analyser.fftSize = FFT_SIZE
        source.connect(analyser)
        const data = new Uint8Array(analyser.fftSize)

        timerRef.current = window.setInterval(() => {
          analyser.getByteTimeDomainData(data)
          let sum = 0
          for (const value of data) {
            const centered = (value - 128) / 128
            sum += centered * centered
          }
          const rms = Math.sqrt(sum / data.length)
          setLevel(rms)

          const event = gateRef.current.update(rms, performance.now())
          if (!event) return
          if (event.type === 'speech-start') {
            // Se conserva algo de audio previo: la frase empieza cuando el
            // nivel cruza el umbral, no cuando empieza el sonido.
            startIndexRef.current = Math.max(0, chunksRef.current.length - PREROLL_CHUNKS)
            return
          }
          if (event.reason === 'too-short') {
            startIndexRef.current = chunksRef.current.length
            return
          }
          const slice = chunksRef.current.slice(startIndexRef.current)
          startIndexRef.current = chunksRef.current.length
          if (!slice.length) return
          const type = mimeType || recorder.mimeType || 'audio/webm'
          void transcribe(new Blob(slice, { type }))
        }, LEVEL_POLL_MS)
      }

      setListening(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      await stopRef.current()
    }
  }, [blocked, device, transcribe])

  const stopRef = useRef<() => void>(() => undefined)
  stopRef.current = () => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current)
      timerRef.current = null
    }
    const recorder = recorderRef.current
    recorderRef.current = null
    if (recorder && recorder.state !== 'inactive') {
      try {
        recorder.stop()
      } catch {
        /* ya estaba parado */
      }
    }
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    const ctx = contextRef.current
    contextRef.current = null
    if (ctx) void ctx.close().catch(() => undefined)
    gateRef.current.reset()
    setLevel(0)
    setListening(false)
  }

  const stop = useCallback(() => {
    stopRef.current()
  }, [])

  useEffect(() => stop, [stop])

  /* ── Voz de ARIA ───────────────────────────────────────────────── */

  const speak = useCallback(
    (text: string) => {
      if (!text || typeof speechSynthesis === 'undefined') return
      try {
        speechSynthesis.cancel()
        const utterance = new SpeechSynthesisUtterance(text)
        const voice = pickVoice(speechSynthesis.getVoices(), language)
        if (voice) {
          utterance.lang = voice.lang
          utterance.voice = speechSynthesis.getVoices().find((v) => v.name === voice.name) ?? null
        } else {
          utterance.lang = language
        }
        speechSynthesis.speak(utterance)
      } catch {
        /* sin síntesis disponible */
      }
    },
    [language],
  )

  return {
    listening,
    transcribing,
    level,
    transcript,
    error,
    blocked,
    start,
    stop,
    speak,
  }
}
