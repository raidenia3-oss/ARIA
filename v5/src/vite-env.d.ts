/// <reference types="vite/client" />

export interface ElectronAPI {
  chatSend: (message: string) => Promise<unknown>
  chatSendStream: (message: string) => Promise<unknown>
  skillsLoad: () => Promise<unknown>
  skillsRun: (skillName: string, params: Record<string, unknown>) => Promise<unknown>
  settingsGet: () => Promise<Record<string, unknown>>
  settingsSet: (settings: unknown) => Promise<{ ok: boolean }>
  systemStatus: () => Promise<unknown>
  windowMinimize: () => Promise<void>
  windowMaximize: () => Promise<void>
  windowClose: () => Promise<void>
  windowSetOpacity: (opacity: number) => Promise<void>
  onChatStream: (cb: (event: unknown, data: unknown) => void) => void

  aiLocalInference: (req: {
    model: string
    prompt: string
    max_tokens?: number
    temperature?: number
    top_p?: number
    system_prompt?: string
  }) => Promise<unknown>
  aiLocalModels: () => Promise<unknown>
  aiSttTranscribe: (audioBase64: string, model?: string) => Promise<unknown>
  aiTtsSynthesize: (req: {
    voice: string
    text: string
    speed?: number
    output_format?: string
  }) => Promise<unknown>

  memoryVectorAdd: (documents: Array<{
    content: string
    metadata?: Record<string, unknown>
    collection?: string
  }>) => Promise<unknown>
  memoryRagQuery: (query: string, collection?: string) => Promise<unknown>

  computerScreenshot: () => Promise<unknown>
  computerExecute: (command: string, args?: string[]) => Promise<unknown>

  selfImprovementCycle: () => Promise<unknown>
  selfImprovementStatus: () => Promise<unknown>

  backendTestChat: () => Promise<{ ok: boolean; response?: unknown; error?: string }>
  backendTestMemory: () => Promise<{ ok: boolean; systemStatus?: unknown; memoryRecent?: unknown; error?: string }>
  backendTestAI: () => Promise<{ ok: boolean; enabled?: boolean; providers?: unknown; error?: string }>

  notificationShow: (title: string, body: string) => Promise<void>
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI
  }
}