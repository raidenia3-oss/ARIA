import { useCallback, useRef, useState } from 'react'
import type { OrbPhase } from './useOrbState'
import { invoke } from '@tauri-apps/api/core'

export interface ChatMessage {
  id: string
  text: string
  sender: 'user' | 'aria'
  timestamp: string
  source?: string
  confidence?: number
  latency?: number
}

export interface ChatController {
  messages: ChatMessage[]
  isStreaming: boolean
  currentStreaming: string
  sendMessage: (text: string) => Promise<void>
}

interface BackendResponse {
  response?: string
  provider?: string
  latency?: number
  tokens?: number
  confidence?: number
  error?: string
}

interface ChatOptions {
  stream?: boolean
}

/**
 * Chat con el backend FastAPI (vía Tauri invoke).
 * Reporta fases al orbe: thinking → responding → idle.
 */
export function useChat(
  onPhase?: (phase: OrbPhase) => void,
  options?: ChatOptions
): ChatController {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [currentStreaming, setCurrentStreaming] = useState('')

  const phaseRef = useRef(onPhase)
  phaseRef.current = onPhase
  const optionsRef = useRef(options)
  optionsRef.current = options

  const addMessage = useCallback((message: Omit<ChatMessage, 'id'>) => {
    setMessages((prev) => [
      ...prev,
      { ...message, id: `msg-${Date.now()}-${Math.random().toString(36).slice(2, 9)}` },
    ])
  }, [])

  const sendMessage = useCallback(
    async (text: string) => {
      const message = text.trim()
      if (!message) return

      addMessage({ text: message, sender: 'user', timestamp: new Date().toLocaleTimeString() })
      setIsStreaming(true)
      setCurrentStreaming('')
      phaseRef.current?.('thinking')

      let reply = ''
      let source = 'local'
      let confidence = 85
      let latency = 0

      try {
        const started = performance.now()
        const result = (await invoke('chat_send', { message })) as BackendResponse
        latency = result?.latency ?? Math.round((performance.now() - started)) / 1000
        if (result?.response) {
          reply = result.response
          source = result.provider || 'ollama'
          confidence = result.confidence ?? 85
        } else if (result?.error) {
          reply = `No pude conectar con el backend Python.\n\n\`\`\`\n${result.error}\n\`\`\``
          source = 'offline'
          confidence = 0
        }
      } catch (error) {
        reply = `Error de conexión con el backend: ${String(error)}`
        source = 'offline'
        confidence = 0
      }

      if (!reply) reply = 'Sin respuesta del modelo.'

      const streaming = optionsRef.current?.stream !== false
      phaseRef.current?.('responding')
      if (streaming) {
        for (let i = 1; i <= reply.length; i++) {
          setCurrentStreaming(reply.slice(0, i))
          if (i % 4 === 0) await new Promise((resolve) => requestAnimationFrame(() => resolve(null)))
        }
      }

      addMessage({
        text: reply,
        sender: 'aria',
        timestamp: new Date().toLocaleTimeString(),
        source,
        confidence,
        latency,
      })
      setIsStreaming(false)
      setCurrentStreaming('')
      phaseRef.current?.('idle')
    },
    [addMessage]
  )

  return { messages, isStreaming, currentStreaming, sendMessage }
}