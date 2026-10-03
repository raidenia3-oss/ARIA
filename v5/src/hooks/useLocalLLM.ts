import { useCallback, useState } from 'react'

/**
 * Origen del backend Python (FastAPI) que sirve `/api/ai/*`.
 *
 * SUPUESTO DOCUMENTADO: no existe un canal IPC para hardware info. Lo verifiqué
 * leyendo `v5/electron/preload.ts` y `v5/src/vite-env.d.ts` — exponen
 * `aiLocalInference`, `aiLocalModels`, `aiSttTranscribe` y `aiTtsSynthesize`, y
 * nada de hardware. Antes se usaba `fetch('/api/ai/hardware/info')`, una URL
 * RELATIVA: en el renderer empaquetado eso resuelve contra `file://` y nunca
 * llega al servidor. El puerto 8000 es el mismo que arranca el proceso main
 * (`v5/electron/main.ts:12 BACKEND_PORT = 8000`) y el que usan sus handlers
 * `ai:*`. Cuando exista un canal `aiHardwareInfo`, `readHardwareBridge()` lo
 * recoge sin tocar nada más.
 */
const PYTHON_BACKEND_ORIGIN = 'http://127.0.0.1:8000'

export interface ModelInfo {
  name: string
  type: string
  path: string
  size_gb: number
  context_length: number
  loaded: boolean
  /** `'measured'` leído de un backend real, `'mock'` para el stub de dev. */
  data_source: string
  /** Explicación del servidor; `null` cuando no la da. */
  detail: string | null
}

/**
 * Envoltura REAL de `GET /api/ai/local/models`
 * (`ARIA_APP/backend/api/ai_infrastructure.py:588`). Nunca es un array pelado:
 * es un objeto con `models`, `data_source` y `detail`.
 *
 * `models` es `null` con `data_source: 'unavailable'` cuando no se pudo medir el
 * listado. Por eso la envoltura es parte de la API: un `[]` y un `null`
 * significan cosas distintas y solo el segundo lo dice el servidor.
 */
export interface LocalModelsEnvelope {
  models: ModelInfo[] | null
  /** `null` cuando el cuerpo no era la envoltura documentada. */
  data_source: string | null
  detail: string | null
}

export interface LocalInferenceResult {
  text: string
  /** `null` cuando no se ejecutó nada: `0` afirmaría una medición inexistente. */
  tokens_generated: number | null
  latency_ms: number | null
  model: string
  /** Etiqueta del dispositivo; `'offline'` cuando no hubo llamada. */
  device: string
  /**
   * Opcionales: el handler IPC `ai:local:inference` devuelve `{ error }` sin
   * estos campos cuando el backend no responde (`main.ts:377-379`).
   */
  data_source?: string | null
  detail?: string | null
}

/** Un segmento tal cual lo emite whisper.cpp: las claves extra son opcionales. */
export interface STTSegment {
  start_ms: number
  end_ms: number
  text: string
  tokens?: unknown[]
  avg_logprob?: number
}

export interface STTResult {
  text: string
  /** Idioma pedido por el llamante; `null` si se dejó en autodetección. */
  language: string | null
  /** Tiempo de la llamada; `null` cuando no se transcribió nada. */
  duration_ms: number | null
  segments: STTSegment[]
  /** `'measured'` si corrió Whisper, `'unavailable'` si no. */
  data_source: string | null
  detail: string | null
}

export interface TTSResult {
  /** Bytes codificados reales; `null` cuando no se produjo audio. */
  audio_base64: string | null
  /** `null` cuando no se produjo audio: no se puede asumir 22050. */
  sample_rate: number | null
  /** Parseado de la cabecera WAV; `null` si no se pudo medir. */
  duration_ms: number | null
  /** `null` si la síntesis nunca arrancó. */
  latency_ms: number | null
  voice: string | null
  data_source: string | null
  detail: string | null
}

/**
 * `GET /api/ai/hardware/info` (`ai_infrastructure.py:1007`).
 *
 * VERIFICADO 2026-10-03: el servidor NO envía `data_source`. El modelo Pydantic
 * `HardwareInfo` (líneas 134-139) no lo declara y `response_model` descarta las
 * claves extra, así que el handler (línea 1069) no puede añadirlo. Por eso el
 * campo es OPCIONAL y el cliente no inventa un origen para lo que el servidor no
 * declara.
 */
export interface HardwareInfo {
  cpu: Record<string, unknown> | null
  gpu: Array<Record<string, unknown>> | null
  memory_gb: number | null
  compute_devices: string[] | null
  recommended_backend: string | null
  data_source?: string
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return asRecord(value) !== null
}

/** Mensaje del sobre `{ error }` que devuelve el IPC cuando no hay backend. */
function transportDetail(raw: unknown): string | null {
  const row = asRecord(raw)
  const error = row ? row.error : undefined
  return typeof error === 'string' ? error : null
}

/**
 * Normaliza una fila de `models`. Se descarta la fila si le falta cualquier
 * campo que el modelo Pydantic declara obligatorio: una fila a medio validar no
 * puede mostrarse como si estuviera medida.
 */
function normalizeModelInfo(value: unknown): ModelInfo | null {
  const row = asRecord(value)
  if (!row) return null
  if (typeof row.name !== 'string') return null
  if (typeof row.type !== 'string') return null
  if (typeof row.path !== 'string') return null
  if (typeof row.size_gb !== 'number') return null
  if (typeof row.context_length !== 'number') return null
  if (typeof row.loaded !== 'boolean') return null
  if (typeof row.data_source !== 'string') return null
  return {
    name: row.name,
    type: row.type,
    path: row.path,
    size_gb: row.size_gb,
    context_length: row.context_length,
    loaded: row.loaded,
    data_source: row.data_source,
    detail: typeof row.detail === 'string' ? row.detail : null,
  }
}

/**
 * Desenvuelve `GET /api/ai/local/models` preservando `data_source`/`detail`.
 *
 * El sobre `{ error }` que devuelve el handler IPC cuando el backend no está
 * levantado (`main.ts:386-388`) NO tiene `models`: se traduce a
 * `models: null` con `data_source: null` y el mensaje real en `detail`, nunca a
 * un array vacío que se leería como "hay cero modelos".
 */
function readModelsEnvelope(raw: unknown): LocalModelsEnvelope {
  const payload = asRecord(raw)
  if (!payload) {
    return {
      models: null,
      data_source: null,
      detail: 'respuesta ilegible: el cuerpo no es un objeto JSON',
    }
  }
  const models = Array.isArray(payload.models)
    ? payload.models
        .map(normalizeModelInfo)
        .filter((model): model is ModelInfo => model !== null)
    : null
  const declared = typeof payload.data_source === 'string' ? payload.data_source : null
  const detail =
    typeof payload.detail === 'string' ? payload.detail : transportDetail(raw)

  if (models === null && declared === null) {
    return {
      models: null,
      data_source: null,
      detail: detail ?? 'la respuesta no trae `models` ni `data_source`',
    }
  }
  return { models, data_source: declared, detail }
}

function normalizeSTTSegment(value: unknown): STTSegment | null {
  const row = asRecord(value)
  if (!row) return null
  if (typeof row.start_ms !== 'number') return null
  if (typeof row.end_ms !== 'number') return null
  if (typeof row.text !== 'string') return null
  const segment: STTSegment = {
    start_ms: row.start_ms,
    end_ms: row.end_ms,
    text: row.text,
  }
  if (Array.isArray(row.tokens)) segment.tokens = row.tokens
  if (typeof row.avg_logprob === 'number') segment.avg_logprob = row.avg_logprob
  return segment
}

/** `null` cuando el cuerpo no trae `text`: entonces no hubo transcripción. */
function readSTTResult(raw: unknown): STTResult | null {
  const row = asRecord(raw)
  if (!row || typeof row.text !== 'string') return null
  return {
    text: row.text,
    language: typeof row.language === 'string' ? row.language : null,
    duration_ms: typeof row.duration_ms === 'number' ? row.duration_ms : null,
    segments: Array.isArray(row.segments)
      ? row.segments
          .map(normalizeSTTSegment)
          .filter((segment): segment is STTSegment => segment !== null)
      : [],
    data_source: typeof row.data_source === 'string' ? row.data_source : null,
    detail: typeof row.detail === 'string' ? row.detail : transportDetail(raw),
  }
}

/**
 * `null` cuando el cuerpo no identifica ni una voz ni un audio. La voz puede
 * estar identificada y el audio ausente (`audio_base64` es `Optional[str]`), así
 * que cualquiera de las dos basta para conservar la fila y su `data_source`.
 */
function readTTSResult(raw: unknown): TTSResult | null {
  const row = asRecord(raw)
  if (!row) return null
  const hasVoice = typeof row.voice === 'string'
  const hasAudio = typeof row.audio_base64 === 'string'
  if (!hasVoice && !hasAudio) return null
  return {
    audio_base64: hasAudio ? (row.audio_base64 as string) : null,
    sample_rate: typeof row.sample_rate === 'number' ? row.sample_rate : null,
    duration_ms: typeof row.duration_ms === 'number' ? row.duration_ms : null,
    latency_ms: typeof row.latency_ms === 'number' ? row.latency_ms : null,
    voice: hasVoice ? (row.voice as string) : null,
    data_source: typeof row.data_source === 'string' ? row.data_source : null,
    detail: typeof row.detail === 'string' ? row.detail : transportDetail(raw),
  }
}

/**
 * Puente de hardware info, si algún día existe.
 *
 * HOY NO EXISTE: `preload.ts` y `vite-env.d.ts` no declaran `aiHardwareInfo`.
 * Se lee con un cast defensivo —el mismo truco que `readBridgeApiKey()` en
 * `lib/ariaBackend.ts`— para que, si alguien añade el canal, este hook lo use
 * sin cambios. No se añade el canal IPC aquí a propósito.
 */
function readHardwareBridge(): (() => Promise<unknown>) | undefined {
  if (typeof window === 'undefined') return undefined
  const bridge = (window as unknown as { electronAPI?: Record<string, unknown> }).electronAPI
  const candidate = bridge?.aiHardwareInfo
  return typeof candidate === 'function' ? (candidate as () => Promise<unknown>) : undefined
}

/** `fetch` con verificación de estado; devuelve `unknown`, no `any`. */
async function fetchJson(url: string): Promise<unknown> {
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`${url} -> ${response.status} ${response.statusText}`)
  }
  return response.json()
}

/** Hook for local LLM inference via Ollama or Candle.rs */
export function useLocalLLM() {
  const [isGenerating, setIsGenerating] = useState(false)

  const inference = useCallback(async (req: {
    model: string
    prompt: string
    max_tokens?: number
    temperature?: number
    top_p?: number
    system_prompt?: string
  }): Promise<LocalInferenceResult> => {
    setIsGenerating(true)
    try {
      const api = window.electronAPI
      if (api?.aiLocalInference) {
        const raw: unknown = await api.aiLocalInference(req)
        const row = asRecord(raw)
        if (row && typeof row.text === 'string') {
          return {
            text: row.text,
            tokens_generated:
              typeof row.tokens_generated === 'number' ? row.tokens_generated : null,
            latency_ms: typeof row.latency_ms === 'number' ? row.latency_ms : null,
            model: typeof row.model === 'string' ? row.model : req.model,
            device: typeof row.device === 'string' ? row.device : 'unavailable',
            data_source: typeof row.data_source === 'string' ? row.data_source : null,
            detail: typeof row.detail === 'string' ? row.detail : transportDetail(raw),
          }
        }
        // El IPC devolvió `{ error }`: no hubo inferencia. Se dice, en vez de
        // fabricar `tokens_generated: 0` y `latency_ms: 0`.
        return {
          text: '[Offline] Conecte con ARIA OS v5.0',
          tokens_generated: null,
          latency_ms: null,
          model: req.model,
          device: 'offline',
          data_source: 'unavailable',
          detail: transportDetail(raw) ?? 'el backend no devolvió `text`',
        }
      }
      return {
        text: '[Offline] Conecte con ARIA OS v5.0',
        tokens_generated: null,
        latency_ms: null,
        model: req.model,
        device: 'offline',
        data_source: 'unavailable',
        detail: 'no hay puente de Electron (`window.electronAPI.aiLocalInference`)',
      }
    } finally {
      setIsGenerating(false)
    }
  }, [])

  /**
   * Lista de modelos con su envoltura intacta: el llamante puede distinguir
   * `measured` de `unavailable` de `mock`, cosa imposible con un `[]`.
   */
  const getModelsDetailed = useCallback(async (): Promise<LocalModelsEnvelope> => {
    const api = window.electronAPI
    if (!api?.aiLocalModels) {
      return {
        models: null,
        data_source: null,
        detail: 'no hay puente de Electron (`window.electronAPI.aiLocalModels`)',
      }
    }
    return readModelsEnvelope(await api.aiLocalModels())
  }, [])

  /**
   * Solo el array, para quien no necesita el origen del dato. `[]` cuando el
   * servidor respondió con `models: null` o sin la clave: es la misma decisión
   * que ya se tomaba, pero ahora pasando por el desenvoltado correcto en vez de
   * un assertion a un array que nunca llega.
   */
  const getModels = useCallback(async (): Promise<ModelInfo[]> => {
    const envelope = await getModelsDetailed()
    return envelope.models ?? []
  }, [getModelsDetailed])

  const getHardwareInfo = useCallback(async (): Promise<HardwareInfo> => {
    const bridge = readHardwareBridge()
    const raw = bridge
      ? await bridge()
      : await fetchJson(`${PYTHON_BACKEND_ORIGIN}/api/ai/hardware/info`)
    const row = asRecord(raw)
    if (!row) {
      throw new Error('hardware info: el cuerpo no es un objeto JSON')
    }
    // Cada campo ausente queda en `null`, que es "no medido". Nunca se
    // sustituye por un 0, un [] ni un "" que el servidor no envió.
    return {
      cpu: isRecord(row.cpu) ? row.cpu : null,
      gpu: Array.isArray(row.gpu) ? row.gpu.filter(isRecord) : null,
      memory_gb: typeof row.memory_gb === 'number' ? row.memory_gb : null,
      compute_devices: Array.isArray(row.compute_devices)
        ? row.compute_devices.filter((d): d is string => typeof d === 'string')
        : null,
      recommended_backend:
        typeof row.recommended_backend === 'string' ? row.recommended_backend : null,
      data_source: typeof row.data_source === 'string' ? row.data_source : undefined,
    }
  }, [])

  const transcribe = useCallback(async (
    audioBase64: string,
    model: string = 'base'
  ): Promise<STTResult> => {
    const api = window.electronAPI
    if (api?.aiSttTranscribe) {
      const raw: unknown = await api.aiSttTranscribe(audioBase64, model)
      const parsed = readSTTResult(raw)
      if (parsed) return parsed
      // Sin `text` no hubo transcripción: `language` se queda en `null` porque
      // no se detectó ningún idioma, y `duration_ms` en `null` porque no corrió
      // nada. Antes se devolvía `'es'` y `0`, que son datos fabricados.
      return {
        text: '[Offline]',
        language: null,
        duration_ms: null,
        segments: [],
        data_source: 'unavailable',
        detail: transportDetail(raw) ?? 'el backend no devolvió `text`',
      }
    }
    return {
      text: '[Offline]',
      language: null,
      duration_ms: null,
      segments: [],
      data_source: 'unavailable',
      detail: 'no hay puente de Electron (`window.electronAPI.aiSttTranscribe`)',
    }
  }, [])

  const synthesize = useCallback(async (req: {
    voice: string
    text: string
    speed?: number
  }): Promise<TTSResult> => {
    const api = window.electronAPI
    if (api?.aiTtsSynthesize) {
      const raw: unknown = await api.aiTtsSynthesize({ ...req, output_format: 'wav' })
      const parsed = readTTSResult(raw)
      if (parsed) return parsed
      // `sample_rate: 22050` era un valor inventado: sin audio no hay tasa de
      // muestreo medida, así que va `null`.
      return {
        audio_base64: null,
        sample_rate: null,
        duration_ms: null,
        latency_ms: null,
        voice: null,
        data_source: 'unavailable',
        detail: transportDetail(raw) ?? 'el backend no devolvió ni `voice` ni audio',
      }
    }
    return {
      audio_base64: null,
      sample_rate: null,
      duration_ms: null,
      latency_ms: null,
      voice: null,
      data_source: 'unavailable',
      detail: 'no hay puente de Electron (`window.electronAPI.aiTtsSynthesize`)',
    }
  }, [])

  return {
    inference,
    getModels,
    getModelsDetailed,
    transcribe,
    synthesize,
    getHardwareInfo,
    isGenerating,
  }
}