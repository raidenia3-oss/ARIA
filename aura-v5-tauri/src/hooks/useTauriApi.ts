import { invoke } from '@tauri-apps/api/core'

export function useTauriApi() {
  const chatSend = async (message: string): Promise<string> => {
    return await invoke('chat_send', { message })
  }

  const skillsLoad = async () => {
    return await invoke('skills_load')
  }

  const settingsGet = async (key: string) => {
    return await invoke('settings_get', { key })
  }

  const settingsSet = async (key: string, value: string) => {
    return await invoke('settings_set', { key, value })
  }

  const windowOpacity = async (opacity: number) => {
    return await invoke('window_opacity', { opacity })
  }

  return {
    chatSend,
    skillsLoad,
    settingsGet,
    settingsSet,
    windowOpacity
  }
}