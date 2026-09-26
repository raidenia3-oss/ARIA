/// <reference types="vite/client" />

export interface ElectronAPI {
  chatSend: (message: string) => Promise<unknown>
  skillsLoad: () => Promise<unknown>
  settingsGet: () => Promise<Record<string, unknown>>
  settingsSet: (settings: unknown) => Promise<{ ok: boolean }>
  systemStatus: () => Promise<unknown>
  windowMinimize: () => Promise<void>
  windowMaximize: () => Promise<void>
  windowClose: () => Promise<void>
  windowSetOpacity: (opacity: number) => Promise<void>
  onChatStream: (cb: (event: unknown, data: unknown) => void) => void
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI
  }
}
