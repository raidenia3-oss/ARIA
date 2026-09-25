import { contextBridge, ipcRenderer } from 'electron'

const api = {
  chatSend: (message: string) => ipcRenderer.invoke('chat:send', message),
  chatSendStream: (message: string) => ipcRenderer.invoke('chat:send-stream', message),
  skillsLoad: () => ipcRenderer.invoke('skills:load'),
  skillsRun: (skillName: string, params: Record<string, unknown>) => ipcRenderer.invoke('skills:run', skillName, params),
  settingsGet: () => ipcRenderer.invoke('settings:get'),
  settingsSet: (settings: unknown) => ipcRenderer.invoke('settings:set', settings),
  systemStatus: () => ipcRenderer.invoke('system:status'),
  windowMinimize: () => ipcRenderer.invoke('window:minimize'),
  windowMaximize: () => ipcRenderer.invoke('window:maximize'),
  windowClose: () => ipcRenderer.invoke('window:close'),
  windowSetOpacity: (opacity: number) => ipcRenderer.invoke('window:opacity', opacity),
  onChatStream: (callback: (event: unknown, data: unknown) => void) => {
    const listener = (_event: unknown, data: unknown) => callback(_event, data)
    ipcRenderer.on('chat:stream', listener)
    return () => ipcRenderer.removeListener('chat:stream', listener)
  },

  // AI Infrastructure
  aiLocalInference: (req: Record<string, unknown>) => ipcRenderer.invoke('ai:local:inference', req),
  aiLocalModels: () => ipcRenderer.invoke('ai:local:models'),
  aiSttTranscribe: (audioBase64: string, model?: string) => ipcRenderer.invoke('ai:stt:transcribe', audioBase64, model),
  aiTtsSynthesize: (req: Record<string, unknown>) => ipcRenderer.invoke('ai:tts:synthesize', req),

  // Memory & RAG
  memoryVectorAdd: (documents: Array<Record<string, unknown>>) => ipcRenderer.invoke('memory:vector:add', documents),
  memoryRagQuery: (query: string, collection?: string) => ipcRenderer.invoke('memory:rag:query', query, collection),

  // Computer Use
  computerScreenshot: () => ipcRenderer.invoke('computer:screenshot'),
  computerExecute: (command: string, args?: string[]) => ipcRenderer.invoke('computer:execute', command, args),

  // Self-Improvement
  selfImprovementCycle: () => ipcRenderer.invoke('self-improvement:cycle'),
  selfImprovementStatus: () => ipcRenderer.invoke('self-improvement:status'),

  // Notifications
  notificationShow: (title: string, body: string) => ipcRenderer.invoke('notification:show', title, body),
}

contextBridge.exposeInMainWorld('electronAPI', api)

export type PreloadApi = typeof api