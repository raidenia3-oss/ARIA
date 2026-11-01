import { useCallback, useEffect, useRef, useState } from 'react'
import { cleanDeviceLabel, looksLikeHeadset } from '../lib/headset'

/**
 * Dispositivos de audio y detección de audífonos con micrófono.
 *
 * `enumerateDevices()` sólo devuelve etiquetas de los dispositivos tras
 * conceder permiso de micrófono, así que el hook pide acceso una vez y
 * vuelve a enumerar: sin permiso sólo hay `deviceId` vacío.
 */

export interface AudioInputDevice {
  deviceId: string
  label: string
  /** `true` si la etiqueta sugiere un auricular o casco (con micrófono). */
  isHeadset: boolean
  /** `true` si el dispositivo es el que el sistema usa por defecto. */
  isDefault: boolean
}

export interface AudioOutputDevice {
  deviceId: string
  label: string
  isHeadset: boolean
}

export interface AudioDeviceState {
  inputs: AudioInputDevice[]
  outputs: AudioOutputDevice[]
  /** Auricular con micrófono detectado, si hay uno. */
  headset: AudioInputDevice | null
  /** `true` si el navegador ya nos dejó ver las etiquetas. */
  labelled: boolean
  permission: 'unknown' | 'granted' | 'denied' | 'unsupported'
  error: string | null
  loading: boolean
}

/**
 * Patrones de etiqueta que delatan un auricular/casco con micrófono.
 *
 * Reexportados desde `lib/headset` para que la lógica sea comprobable sin
 * navegador.
 */
export { looksLikeHeadset, cleanDeviceLabel }

export interface UseAudioDevices extends AudioDeviceState {
  /** Pide permiso de micrófono y reenumera los dispositivos. */
  requestPermission: () => Promise<boolean>
  refresh: () => void
  /** Abre el micrófono del auricular detectado y devuelve su stream. */
  openHeadsetStream: () => Promise<MediaStream | null>
  /** Silencia y libera todos los streams abiertos por el hook. */
  stopAll: () => void
}

export function useAudioDevices(): UseAudioDevices {
  const [inputs, setInputs] = useState<AudioInputDevice[]>([])
  const [outputs, setOutputs] = useState<AudioOutputDevice[]>([])
  const [labelled, setLabelled] = useState(false)
  const [permission, setPermission] = useState<AudioDeviceState['permission']>('unknown')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const streamsRef = useRef<MediaStream[]>([])

  const enumerate = useCallback(async () => {
    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.enumerateDevices) {
      setPermission('unsupported')
      return
    }
    setLoading(true)
    try {
      const all = await navigator.mediaDevices.enumerateDevices()
      const nextInputs: AudioInputDevice[] = []
      const nextOutputs: AudioOutputDevice[] = []

      for (const device of all) {
        if (device.kind === 'audioinput') {
          nextInputs.push({
            deviceId: device.deviceId,
            label: cleanDeviceLabel(device.label),
            isHeadset: looksLikeHeadset(device.label),
            isDefault: device.deviceId === 'default',
          })
        } else if (device.kind === 'audiooutput') {
          nextOutputs.push({
            deviceId: device.deviceId,
            label: cleanDeviceLabel(device.label),
            isHeadset: looksLikeHeadset(device.label),
          })
        }
      }

      setInputs(nextInputs)
      setOutputs(nextOutputs)
      // Las etiquetas sólo aparecen con permiso concedido: sin ellas no se
      // puede saber si un dispositivo es un auricular.
      setLabelled(nextInputs.some((d) => d.label.length > 0))
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void enumerate()
    const devices = navigator.mediaDevices
    if (!devices) return
    const handler = () => void enumerate()
    devices.addEventListener?.('devicechange', handler)
    return () => {
      devices.removeEventListener?.('devicechange', handler)
    }
  }, [enumerate])

  const requestPermission = useCallback(async () => {
    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      setPermission('unsupported')
      return false
    }
    try {
      // Se pide sólo audio: es el permiso que revela las etiquetas.
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      stream.getTracks().forEach((track) => track.stop())
      setPermission('granted')
      await enumerate()
      return true
    } catch (err) {
      setPermission('denied')
      setError(err instanceof Error ? err.message : String(err))
      return false
    }
  }, [enumerate])

  const headset = inputs.find((d) => d.isHeadset) ?? null

  const openHeadsetStream = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia) return null
    const target = headset ?? inputs.find((d) => d.isDefault) ?? inputs[0]
    if (!target) return null
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: target.deviceId && target.deviceId !== 'default'
          ? { deviceId: { exact: target.deviceId }, echoCancellation: true, noiseSuppression: true }
          : { echoCancellation: true, noiseSuppression: true },
      })
      streamsRef.current.push(stream)
      return stream
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      return null
    }
  }, [headset, inputs])

  const stopAll = useCallback(() => {
    for (const stream of streamsRef.current) {
      stream.getTracks().forEach((track) => track.stop())
    }
    streamsRef.current = []
  }, [])

  useEffect(() => stopAll, [stopAll])

  return {
    inputs,
    outputs,
    headset,
    labelled,
    permission,
    error,
    loading,
    requestPermission,
    refresh: () => void enumerate(),
    openHeadsetStream,
    stopAll,
  }
}
