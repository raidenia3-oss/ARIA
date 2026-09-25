import { useCallback, useState } from 'react'

export interface ModelInfo {
  name: string
  type: string
  path: string
  size_gb: number
  context_length: number
  loaded: boolean
}

export interface LocalInferenceResult {
  text: string
  tokens_generated: number
  latency_ms: number
  model: string
  device: string
}

export interface STTResult {
  text: string
  language: string
  duration_ms: number
  segments: Array<{ start_ms: number; end_ms: number; text: string }>
}

export interface TTSResult {
  audio_base64: string
  sample_rate: number
  duration_ms: number
  latency_ms: number
  voice: string
}

export interface HardwareInfo {
  cpu: Record<string, unknown>
  gpu: Array<Record<string, unknown>>
  memory_gb: number
  compute_devices: string[]
  recommended_backend: string
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
        return await api.aiLocalInference(req) as LocalInferenceResult
      }
      return {
        text: '[Offline] Conecte con ARIA OS v5.0',
        tokens_generated: 0,
        latency_ms: 0,
        model: req.model,
        device: 'offline'
      }
    } finally {
      setIsGenerating(false)
    }
  }, [])

  const getModels = useCallback(async (): Promise<ModelInfo[]> => {
    const api = window.electronAPI
    if (api?.aiLocalModels) {
      return await api.aiLocalModels() as ModelInfo[]
    }
    return []
  }, [])

  const getHardwareInfo = useCallback(async (): Promise<HardwareInfo> => {
    const response = await fetch('/api/ai/hardware/info')
    return await response.json()
  }, [])

  const transcribe = useCallback(async (
    audioBase64: string,
    model: string = 'base'
  ): Promise<STTResult> => {
    const api = window.electronAPI
    if (api?.aiSttTranscribe) {
      return await api.aiSttTranscribe(audioBase64, model) as STTResult
    }
    return { text: '[Offline]', language: 'es', duration_ms: 0, segments: [] }
  }, [])

  const synthesize = useCallback(async (req: {
    voice: string
    text: string
    speed?: number
  }): Promise<TTSResult> => {
    const api = window.electronAPI
    if (api?.aiTtsSynthesize) {
      return await api.aiTtsSynthesize({ ...req, output_format: 'wav' }) as TTSResult
    }
    return {
      audio_base64: '',
      sample_rate: 22050,
      duration_ms: 0,
      latency_ms: 0,
      voice: req.voice
    }
  }, [])

  return { inference, getModels, transcribe, synthesize, getHardwareInfo, isGenerating }
}