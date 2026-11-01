import { useCallback, useEffect, useRef, useState } from 'react'
import type React from 'react'
import {
  FaceLandmarker,
  FilesetResolver,
  HandLandmarker,
  type FaceLandmarkerResult,
  type HandLandmarkerResult,
} from '@mediapipe/tasks-vision'
import {
  classifyGesture,
  handMotion,
  GESTURE_ACTIONS,
  type Gesture,
  type HandPoint,
} from '../lib/gestures'
import {
  averageDescriptors,
  cosineSimilarity,
  faceDescriptor,
  identityVerdict,
  type FaceDescriptor,
  type IdentityVerdict,
} from '../lib/identity'

/* La lógica de gestos vive en `lib/gestures`: este hook sólo la orquesta. */
export type { Gesture, HandPoint } from '../lib/gestures'

/** Frames que un gesto debe mantenerse para contar como deliberado. */
const GESTURE_HOLD_FRAMES = 4
/** Similitud mínima entre fotogramas para considerar que la mano no se movió. */
const HAND_MOTION_TOLERANCE = 0.035
/** Muestras de rostro necesarias para enrolar una identidad. */
export const ENROLL_SAMPLES = 8

/** Punto de la malla: reexportado desde `lib/gestures` para no duplicar tipos. */
type Landmark = HandPoint

export interface CameraGesturesState {
  /** `true` cuando la cámara está transmitiendo. */
  active: boolean
  /** `true` mientras se cargan los modelos de MediaPipe. */
  loading: boolean
  error: string | null
  gesture: Gesture
  /** Confianza del gesto actual, 0..1. */
  confidence: number
  /** Landmarks de la mano detectada (21 puntos), si la hay. */
  handLandmarks: Landmark[] | null
  /** Landmarks del rostro detectados (468+ puntos), si hay rostro. */
  faceLandmarks: Landmark[] | null
  /** Veredicto de identidad del rostro actual. */
  identity: IdentityVerdict
  /** Similitud del rostro con el perfil enrolmentado, 0..1. */
  identityScore: number
  /** `true` si ya hay un perfil enrolmentado. */
  enrolled: boolean
  /** Progreso de la enrolación, 0..1. */
  enrollProgress: number
  /** Último gesto que se ha confirmado tras mantenerlo. */
  lastTriggered: { gesture: Gesture; at: number } | null
}

export interface UseCameraGestures extends CameraGesturesState {
  /** `<video>` al que hay que enganchar el stream de la cámara. */
  videoRef: React.RefObject<HTMLVideoElement | null>
  start: () => Promise<void>
  stop: () => void
  /** Captura el descriptor facial actual para enrolar la identidad. */
  enroll: (name: string) => Promise<boolean>
  /** Borra la identidad enrolmentada. */
  forget: () => void
  /** `true` si el gesto actual puede ejecutarse sin identidad confirmada. */
  canTrigger: (gesture: Gesture) => boolean
}

/** Estado guardado por el bridge de Electron, si existe. */
interface ElectronIdentityBridge {
  identitySave?: (profile: unknown) => Promise<{ ok: boolean }>
  identityLoad?: () => Promise<unknown>
}

function readBridge(): ElectronIdentityBridge | null {
  if (typeof window === 'undefined') return null
  const bridge = (window as unknown as { electronAPI?: Record<string, unknown> }).electronAPI
  if (!bridge || typeof bridge !== 'object') return null
  return bridge as ElectronIdentityBridge
}

export function useCameraGestures(): UseCameraGestures {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const handRef = useRef<HandLandmarker | null>(null)
  const faceRef = useRef<FaceLandmarker | null>(null)
  const rafRef = useRef<number | null>(null)
  const lastVideoTimeRef = useRef(-1)

  const candidateRef = useRef<{ gesture: Gesture; frames: number; points: Landmark[] } | null>(null)
  const lastHandRef = useRef<Landmark[] | null>(null)
  const enrolledRef = useRef<FaceDescriptor | null>(null)
  const enrollSamplesRef = useRef<FaceDescriptor[]>([])

  const [state, setState] = useState<CameraGesturesState>({
    active: false,
    loading: false,
    error: null,
    gesture: 'none',
    confidence: 0,
    handLandmarks: null,
    faceLandmarks: null,
    identity: 'desconocido',
    identityScore: 0,
    enrolled: false,
    enrollProgress: 0,
    lastTriggered: null,
  })

  /* ── Identidad persistida ─────────────────────────────────────── */

  const loadEnrolled = useCallback(async () => {
    const bridge = readBridge()
    if (bridge?.identityLoad) {
      try {
        const raw = await bridge.identityLoad()
        const profile = raw as { descriptor?: FaceDescriptor } | null
        if (profile?.descriptor && Array.isArray(profile.descriptor) && profile.descriptor.length > 0) {
          enrolledRef.current = profile.descriptor
          setState((prev) => ({ ...prev, enrolled: true }))
          return
        }
      } catch {
        /* sin bridge o perfil corrupto */
      }
    }
    // Respaldo en localStorage (navegador sin Electron).
    try {
      const raw = localStorage.getItem('aria.identity.v1')
      if (raw) {
        const parsed = JSON.parse(raw) as { descriptor?: FaceDescriptor }
        if (Array.isArray(parsed.descriptor) && parsed.descriptor.length > 0) {
          enrolledRef.current = parsed.descriptor
          setState((prev) => ({ ...prev, enrolled: true }))
        }
      }
    } catch {
      /* sin storage */
    }
  }, [])

  useEffect(() => {
    void loadEnrolled()
  }, [loadEnrolled])

  /* ── Bucle de detección ───────────────────────────────────────── */

  const detectLoop = useCallback(() => {
    const video = videoRef.current
    const hand = handRef.current
    const face = faceRef.current
    if (!video || !hand || !face) return

    if (video.readyState >= 2 && video.currentTime !== lastVideoTimeRef.current) {
      lastVideoTimeRef.current = video.currentTime

      let handResult: HandLandmarkerResult | null = null
      let faceResult: FaceLandmarkerResult | null = null
      try {
        handResult = hand.detectForVideo(video, performance.now())
        faceResult = face.detectForVideo(video, performance.now())
      } catch (err) {
        setState((prev) => ({
          ...prev,
          error: err instanceof Error ? err.message : String(err),
        }))
      }

      const handPoints = handResult?.landmarks?.[0] ?? null
      const facePoints = (faceResult?.faceLandmarks?.[0] as Landmark[] | undefined) ?? null

      /* Identidad: el descriptor se compara con el perfil enrolmentado. */
      let identity: IdentityVerdict = 'desconocido'
      let identityScore = 0
      if (facePoints) {
        const descriptor = faceDescriptor(facePoints)
        if (descriptor && enrolledRef.current) {
          identityScore = cosineSimilarity(descriptor, enrolledRef.current)
          identity = identityVerdict(identityScore)
        }
      }

      /* Gesto: se exige que la mano se quede quieta y mantenga la forma. */
      let gesture: Gesture = 'none'
      let confidence = 0
      if (handPoints) {
        const motion = handMotion(lastHandRef.current, handPoints)
        const shape = classifyGesture(handPoints)
        if (motion < HAND_MOTION_TOLERANCE && shape !== 'none') {
          const candidate = candidateRef.current
          if (candidate && candidate.gesture === shape) {
            candidate.frames += 1
            candidateRef.current = candidate
          } else {
            candidateRef.current = { gesture: shape, frames: 1, points: handPoints }
          }
          if (candidateRef.current.frames >= GESTURE_HOLD_FRAMES) {
            gesture = shape
            confidence = Math.min(1, candidateRef.current.frames / (GESTURE_HOLD_FRAMES * 2))
          }
        } else {
          candidateRef.current = null
        }
        lastHandRef.current = handPoints
      } else {
        candidateRef.current = null
        lastHandRef.current = null
      }

      setState((prev) => {
        const triggered =
          gesture !== 'none' && gesture !== prev.gesture
            ? { gesture, at: Date.now() }
            : prev.lastTriggered
        return {
          ...prev,
          gesture,
          confidence,
          handLandmarks: handPoints,
          faceLandmarks: facePoints,
          identity,
          identityScore,
          lastTriggered: triggered,
        }
      })
    }

    rafRef.current = requestAnimationFrame(detectLoop)
  }, [])

  /* ── Arranque ─────────────────────────────────────────────────── */

  const start = useCallback(async () => {
    if (state.active || state.loading) return
    setState((prev) => ({ ...prev, loading: true, error: null }))

    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error('Este entorno no expone cámara (navigator.mediaDevices)')
      }

      const fileset = await FilesetResolver.forVisionTasks('/mediapipe/wasm')
      handRef.current = await HandLandmarker.createFromOptions(fileset, {
        baseOptions: {
          modelAssetPath: '/models/hand_landmarker.task',
          delegate: 'GPU',
        },
        numHands: 1,
        runningMode: 'VIDEO',
        minHandDetectionConfidence: 0.6,
        minHandPresenceConfidence: 0.6,
        minTrackingConfidence: 0.6,
      })

      faceRef.current = await FaceLandmarker.createFromOptions(fileset, {
        baseOptions: {
          modelAssetPath: '/models/face_landmarker.task',
          delegate: 'GPU',
        },
        runningMode: 'VIDEO',
        numFaces: 1,
        outputFaceBlendshapes: false,
      })

      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
        audio: false,
      })
      streamRef.current = stream

      const video = videoRef.current
      if (video) {
        video.srcObject = stream
        await video.play().catch(() => undefined)
      }

      lastVideoTimeRef.current = -1
      setState((prev) => ({ ...prev, active: true, loading: false }))
      rafRef.current = requestAnimationFrame(detectLoop)
    } catch (err) {
      setState((prev) => ({
        ...prev,
        loading: false,
        active: false,
        error: err instanceof Error ? err.message : String(err),
      }))
    }
  }, [detectLoop, state.active, state.loading])

  const stop = useCallback(() => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current)
      rafRef.current = null
    }
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    const video = videoRef.current
    if (video) video.srcObject = null
    candidateRef.current = null
    lastHandRef.current = null
    setState((prev) => ({ ...prev, active: false, gesture: 'none', handLandmarks: null }))
  }, [])

  useEffect(() => stop, [stop])

  /* ── Enrolación ───────────────────────────────────────────────── */

  const enroll = useCallback(async (name: string) => {
    const points = state.faceLandmarks
    if (!points) return false
    const descriptor = faceDescriptor(points)
    if (!descriptor) return false
    enrollSamplesRef.current.push(descriptor)
    setState((prev) => ({
      ...prev,
      enrollProgress: Math.min(1, enrollSamplesRef.current.length / ENROLL_SAMPLES),
    }))

    if (enrollSamplesRef.current.length < ENROLL_SAMPLES) return false

    const averaged = averageDescriptors(enrollSamplesRef.current)
    if (!averaged) return false
    enrolledRef.current = averaged

    const profile = {
      name,
      descriptor: averaged,
      samples: enrollSamplesRef.current.length,
      enrolledAt: Date.now(),
    }

    const bridge = readBridge()
    if (bridge?.identitySave) {
      try {
        await bridge.identitySave(profile)
      } catch {
        /* el respaldo en localStorage todavía guardará */
      }
    }
    try {
      localStorage.setItem('aria.identity.v1', JSON.stringify(profile))
    } catch {
      /* sin storage */
    }

    enrollSamplesRef.current = []
    setState((prev) => ({ ...prev, enrolled: true, enrollProgress: 0, identity: 'confirmado' }))
    return true
  }, [state.faceLandmarks])

  const forget = useCallback(() => {
    enrolledRef.current = null
    enrollSamplesRef.current = []
    const bridge = readBridge()
    if (bridge?.identitySave) {
      void bridge.identitySave(null).catch(() => undefined)
    }
    try {
      localStorage.removeItem('aria.identity.v1')
    } catch {
      /* sin storage */
    }
    setState((prev) => ({
      ...prev,
      enrolled: false,
      enrollProgress: 0,
      identity: 'desconocido',
      identityScore: 0,
    }))
  }, [])

  const canTrigger = useCallback(
    (gesture: Gesture) => {
      const action = GESTURE_ACTIONS.find((a) => a.gesture === gesture)
      if (!action) return false
      if (action.safeWithoutIdentity) return true
      return state.identity === 'confirmado' || state.identity === 'probable'
    },
    [state.identity],
  )

  return {
    ...state,
    videoRef,
    start,
    stop,
    enroll,
    forget,
    canTrigger,
  }
}
