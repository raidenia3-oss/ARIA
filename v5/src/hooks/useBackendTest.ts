import { useCallback, useState } from 'react'

interface ChatResponse {
  response?: string
  error?: string
  provider?: string
  latency?: number
  tokens?: number
}

interface MemoryResponse {
  ok: boolean
  error?: string
  systemStatus?: unknown
  memoryRecent?: unknown
}

interface AIResponse {
  ok: boolean
  error?: string
  enabled?: boolean
  providers?: Record<string, { available: boolean }>
}

interface VectorAddResponse {
  status: string
  added?: number
  error?: string
  detail?: string
}

interface RAGResponse {
  results?: Array<{ content: string }>
  error?: string
}

export interface BackendTestResult {
  name: string
  success: boolean
  data?: unknown
  error?: string
  latency?: number
}

export interface BackendTestController {
  results: BackendTestResult[]
  testing: boolean
  testAll: () => Promise<void>
  testChat: () => Promise<void>
  testMemory: () => Promise<void>
  testAI: () => Promise<void>
  testVectorMemory: () => Promise<void>
  testRAG: () => Promise<void>
  clear: () => void
}

/**
 * Hook para testear el IPC bridge entre Electron y el backend FastAPI.
 * Expone funciones que llaman a los handlers de main.ts y reportan resultados.
 */
export function useBackendTest(): BackendTestController {
  const [results, setResults] = useState<BackendTestResult[]>([])
  const [testing, setTesting] = useState(false)

  const addResult = useCallback((result: BackendTestResult) => {
    setResults((prev) => [...prev.slice(-20), result])
  }, [])

  const clear = useCallback(() => setResults([]), [])

  const api = window.electronAPI

  const testChat = useCallback(async () => {
    if (!api) return
    const started = Date.now()
    try {
      if (api.backendTestChat) {
        const result = (await api.backendTestChat()) as MemoryResponse
        addResult({
          name: 'backend:test:chat',
          success: result.ok,
          data: result,
          latency: Date.now() - started,
          error: result.error,
        })
      } else if (api.chatSend) {
        const result = (await api.chatSend('ping')) as ChatResponse
        const latency = Date.now() - started
        addResult({
          name: 'chat:send',
          success: !!result?.response,
          data: result,
          latency,
          error: result?.error,
        })
      }
    } catch (error) {
      addResult({
        name: 'chat:send',
        success: false,
        error: String(error),
        latency: Date.now() - started,
      })
    }
  }, [api, addResult])

  const testMemory = useCallback(async () => {
    if (!api?.backendTestMemory) return
    const started = Date.now()
    try {
      const result = (await api.backendTestMemory()) as MemoryResponse
      addResult({
        name: 'backend:test:memory',
        success: result.ok,
        data: result,
        latency: Date.now() - started,
        error: result.error,
      })
    } catch (error) {
      addResult({
        name: 'backend:test:memory',
        success: false,
        error: String(error),
        latency: Date.now() - started,
      })
    }
  }, [api, addResult])

  const testAI = useCallback(async () => {
    if (!api?.backendTestAI) return
    const started = Date.now()
    try {
      const result = (await api.backendTestAI()) as AIResponse
      addResult({
        name: 'backend:test:ai',
        success: result.ok,
        data: result,
        latency: Date.now() - started,
        error: result.error,
      })
    } catch (error) {
      addResult({
        name: 'backend:test:ai',
        success: false,
        error: String(error),
        latency: Date.now() - started,
      })
    }
  }, [api, addResult])

  const testVectorMemory = useCallback(async () => {
    if (!api?.memoryVectorAdd) return
    const started = Date.now()
    try {
      const result = (await api.memoryVectorAdd([
        { content: 'Test document from IPC bridge', metadata: { test: true } },
      ])) as VectorAddResponse
      addResult({
        name: 'memory:vector:add',
        success: result.status === 'ok',
        data: result,
        latency: Date.now() - started,
        error: result.error ?? result.detail,
      })
    } catch (error) {
      addResult({
        name: 'memory:vector:add',
        success: false,
        error: String(error),
        latency: Date.now() - started,
      })
    }
  }, [api, addResult])

  const testRAG = useCallback(async () => {
    if (!api?.memoryRagQuery) return
    const started = Date.now()
    try {
      const result = (await api.memoryRagQuery('Test document from IPC bridge')) as RAGResponse
      addResult({
        name: 'memory:rag:query',
        success: !!result?.results?.length,
        data: result,
        latency: Date.now() - started,
        error: result?.error,
      })
    } catch (error) {
      addResult({
        name: 'memory:rag:query',
        success: false,
        error: String(error),
        latency: Date.now() - started,
      })
    }
  }, [api, addResult])

  const testAll = useCallback(async () => {
    setTesting(true)
    setResults([])
    await testChat()
    await testMemory()
    await testAI()
    await testVectorMemory()
    await testRAG()
    setTesting(false)
  }, [testChat, testMemory, testAI, testVectorMemory, testRAG])

  return {
    results,
    testing,
    testAll,
    testChat,
    testMemory,
    testAI,
    testVectorMemory,
    testRAG,
    clear,
  }
}
