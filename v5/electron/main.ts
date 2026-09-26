import { app, BrowserWindow, ipcMain, shell, Tray, Menu, nativeImage, powerMonitor, globalShortcut } from 'electron'
import { spawn, type ChildProcess } from 'child_process'
import { join } from 'path'
import { existsSync, readFileSync, writeFileSync } from 'fs'

let win: BrowserWindow | null = null
let tray: Tray | null = null
let backendProcess: ChildProcess | null = null
let isQuitting = false

const BACKEND_PORT = 8000
// const DEV_URL = 'http://localhost:5173'

/** Raíz del repo en dev: v5/dist-electron → AURA */
const workspaceRoot = join(__dirname, '..', '..')

function backendDir(): string {
  return app.isPackaged
    ? join(process.resourcesPath, 'backend')
    : join(workspaceRoot, 'ARIA_APP', 'backend')
}

function pythonExecutable(): string {
  if (app.isPackaged) {
    const bundled = join(process.resourcesPath, 'python', 'python.exe')
    if (existsSync(bundled)) return bundled
    // Sin runtime embebido: se usa el Python del sistema si existe
    console.warn('[Backend] runtime embebido ausente → usando Python del sistema')
    return process.platform === 'win32' ? 'python' : 'python3'
  }
  const venv = join(workspaceRoot, '.venv', 'Scripts', 'python.exe')
  if (existsSync(venv)) return venv
  return process.platform === 'win32' ? 'python' : 'python3'
}

/** Arranca el backend FastAPI v4 (ARIA_APP/backend/app.py) con uvicorn */
function startBackend(): void {
  const dir = backendDir()
  if (!existsSync(join(dir, 'app.py'))) {
    console.warn('[Backend] app.py no encontrado en', dir, '→ modo offline')
    return
  }

  const executable = pythonExecutable()
  const args = ['-m', 'uvicorn', 'app:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)]
  console.log('[Backend] Iniciando:', executable, args.join(' '))

  backendProcess = spawn(executable, args, {
    cwd: dir,
    env: { ...process.env, BACKEND_PORT: String(BACKEND_PORT), PYTHONUNBUFFERED: '1' },
    stdio: 'pipe',
  })

  backendProcess.stdout?.on('data', (chunk: Buffer) => process.stdout.write(`[Backend] ${chunk.toString()}`))
  backendProcess.stderr?.on('data', (chunk: Buffer) => process.stderr.write(`[Backend] ${chunk.toString()}`))
  backendProcess.on('error', (error: Error) => console.error('[Backend] spawn error:', error))
}

function stopBackend(): void {
  if (!backendProcess) return
  try {
    backendProcess.kill()
  } catch (error) {
    console.error('[Backend] kill error:', error)
  }
  backendProcess = null
}

function createWindow(): void {
  win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 620,
    show: false,
    title: 'ARIA OS v5.0',
    frame: false,
    titleBarStyle: 'hidden',
    backgroundColor: '#0a0e27',
    vibrancy: 'under-window',
    visualEffectState: 'active',
    webPreferences: {
      preload: join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false,
      backgroundThrottling: false,
    },
    icon: join(__dirname, '..', 'assets', 'icon.png'),
  })

  win.once('ready-to-show', () => win?.show())

  const devServerUrl = process.env.VITE_DEV_SERVER_URL
  if (devServerUrl) {
    void win.loadURL(devServerUrl)
    win.webContents.openDevTools({ mode: 'detach' })
  } else {
    void win.loadFile(join(__dirname, '..', 'dist', 'index.html'))
  }

  // Puente de logs del renderer → consola principal (debug)
  win.webContents.on('console-message', (_event, level, message) => {
    console.log(`[Renderer:${level}] ${message}`)
  })

  // Enlaces externos → navegador del sistema
  win.webContents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url)
    return { action: 'deny' }
  })

  // Cerrar = ocultar a bandeja
  win.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault()
      win?.hide()
    }
  })

  win.on('closed', () => {
    win = null
  })
}

function createTray(): void {
  const icon = nativeImage.createFromDataURL(
    'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAFklEQVR42mNk+M9QzwAFGC8A2QCqgH9zAAAAAElFTkSuQmCC'
  )
  const menu = Menu.buildFromTemplate([
    { label: 'Mostrar ARIA', click: () => win?.show() },
    { type: 'separator' },
    {
      label: 'Salir',
      click: () => {
        isQuitting = true
        app.quit()
      },
    },
  ])
  tray = new Tray(icon)
  tray.setToolTip('ARIA OS v5.0')
  tray.setContextMenu(menu)
  tray.on('click', () => win?.show())
}

/* ------------------------------------------------------------------
   Persistencia de settings (userData/settings.json)
   ------------------------------------------------------------------ */
function settingsFile(): string {
  return join(app.getPath('userData'), 'settings.json')
}

function readSettings(): Record<string, unknown> {
  try {
    const file = settingsFile()
    if (!existsSync(file)) return {}
    return JSON.parse(readFileSync(file, 'utf8')) as Record<string, unknown>
  } catch (error) {
    console.error('[Settings] read error:', error)
    return {}
  }
}

function writeSettings(settings: unknown): { ok: boolean } {
  try {
    writeFileSync(settingsFile(), JSON.stringify(settings, null, 2), 'utf8')
    return { ok: true }
  } catch (error) {
    console.error('[Settings] write error:', error)
    return { ok: false }
  }
}

/* ------------------------------------------------------------------
    IPC: backend FastAPI
    ------------------------------------------------------------------ */
ipcMain.handle('chat:send', async (_event, message: string) => {
  try {
    const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    })
    return await response.json()
  } catch (error) {
    return { error: String(error) }
  }
})

ipcMain.handle('chat:send-stream', async (_event, message: string) => {
  try {
    const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
      signal: AbortSignal.timeout(120000),
    })
    const chunks: string[] = []
    const reader = response.body?.getReader()
    if (!reader) return { error: 'No streaming available' }
    const decoder = new TextDecoder()
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      chunks.push(decoder.decode(value))
    }
    return { response: chunks.join('') }
  } catch (error) {
    return { error: String(error) }
  }
})

ipcMain.handle('skills:load', async () => {
  try {
    const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/skills`)
    return await response.json()
  } catch {
    return []
  }
})

ipcMain.handle('skills:run', async (_event, skillName: string, params: Record<string, unknown>) => {
  try {
    const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/skills/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ skill: skillName, params }),
    })
    return await response.json()
  } catch (error) {
    return { error: String(error) }
  }
})

ipcMain.handle('system:status', async () => {
  try {
    const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/system/status`)
    return await response.json()
  } catch {
    return { status: 'offline' }
  }
})

/* ------------------------------------------------------------------
    IPC: AI Infrastructure (local LLM, STT, TTS)
    ------------------------------------------------------------------ */
ipcMain.handle('ai:local:inference', async (_event, req: {
  model: string
  prompt: string
  max_tokens?: number
  temperature?: number
  top_p?: number
  system_prompt?: string
}) => {
  try {
    const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/ai/local/inference`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
      signal: AbortSignal.timeout(120000),
    })
    return await response.json()
  } catch (error) {
    return { error: String(error) }
  }
})

ipcMain.handle('ai:local:models', async () => {
  try {
    const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/ai/local/models`)
    return await response.json()
  } catch (error) {
    return { error: String(error) }
  }
})

ipcMain.handle('ai:stt:transcribe', async (_event, audioBase64: string, model: string = 'base') => {
  try {
    const audioBuffer = Buffer.from(audioBase64, 'base64')
    const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/ai/stt/transcribe?model=${model}`, {
      method: 'POST',
      body: audioBuffer,
      headers: {
        'Content-Type': 'application/octet-stream',
      },
      signal: AbortSignal.timeout(60000),
    })
    return await response.json()
  } catch (error) {
    return { error: String(error) }
  }
})

ipcMain.handle('ai:tts:synthesize', async (_event, req: {
  voice: string
  text: string
  speed?: number
  output_format?: string
}) => {
  try {
    const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/ai/tts/synthesize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
      signal: AbortSignal.timeout(30000),
    })
    return await response.json()
  } catch (error) {
    return { error: String(error) }
  }
})

/* ------------------------------------------------------------------
    IPC: Memory & RAG
    ------------------------------------------------------------------ */
ipcMain.handle('memory:vector:add', async (_event, documents: Array<{
  content: string
  metadata?: Record<string, unknown>
  collection?: string
}>) => {
  try {
    const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/memory/vector/add`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(documents),
    })
    return await response.json()
  } catch (error) {
    return { error: String(error) }
  }
})

ipcMain.handle('memory:rag:query', async (_event, query: string, collection: string = 'default') => {
  try {
    const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/memory/vector/rag`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, collection, top_k: 5 }),
      signal: AbortSignal.timeout(60000),
    })
    return await response.json()
  } catch (error) {
    return { error: String(error) }
  }
})

/* ------------------------------------------------------------------
    IPC: Computer Use
    ------------------------------------------------------------------ */
ipcMain.handle('computer:screenshot', async () => {
  try {
    const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/computer/screenshot`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    })
    return await response.json()
  } catch (error) {
    return { error: String(error) }
  }
})

ipcMain.handle('computer:execute', async (_event, command: string, args: string[] = []) => {
  try {
    const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/computer/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command, args, timeout: 30 }),
    })
    return await response.json()
  } catch (error) {
    return { error: String(error) }
  }
})

/* ------------------------------------------------------------------
    IPC: Self-Improvement
    ------------------------------------------------------------------ */
ipcMain.handle('self-improvement:cycle', async () => {
  try {
    const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/skills/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ skill: 'self-improvement', params: { action: 'cycle' } }),
      signal: AbortSignal.timeout(120000),
    })
    return await response.json()
  } catch (error) {
    return { error: String(error) }
  }
})

ipcMain.handle('self-improvement:status', async () => {
  try {
    const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/skills/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ skill: 'self-improvement', params: { action: 'status' } }),
    })
    return await response.json()
  } catch (error) {
    return { error: String(error) }
  }
})

/* ------------------------------------------------------------------
    IPC: Backend Test Hooks
    ------------------------------------------------------------------ */
ipcMain.handle('backend:test:chat', async () => {
  try {
    const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: 'ping', mode: 'text' }),
      signal: AbortSignal.timeout(30000),
    })
    const data = await response.json()
    return { ok: true, response: data }
  } catch (error) {
    return { ok: false, error: String(error) }
  }
})

ipcMain.handle('backend:test:memory', async () => {
  try {
    const [statusRes, memoryRes] = await Promise.all([
      fetch(`http://127.0.0.1:${BACKEND_PORT}/api/system/status`),
      fetch(`http://127.0.0.1:${BACKEND_PORT}/api/memory/recent?limit=5`),
    ])
    const statusData = await statusRes.json()
    const memoryData = await memoryRes.json()
    return { ok: true, systemStatus: statusData, memoryRecent: memoryData }
  } catch (error) {
    return { ok: false, error: String(error) }
  }
})

ipcMain.handle('backend:test:ai', async () => {
  try {
    const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/ai/status`)
    const data = await response.json()
    return { ok: true, ...data }
  } catch (error) {
    return { ok: false, error: String(error) }
  }
})

/* ------------------------------------------------------------------
    IPC: settings
    ------------------------------------------------------------------ */
ipcMain.handle('settings:get', async () => readSettings())
ipcMain.handle('settings:set', async (_event, settings: unknown) => writeSettings(settings))

/* ------------------------------------------------------------------
   IPC: ventana
   ------------------------------------------------------------------ */
ipcMain.handle('window:minimize', () => win?.minimize())
ipcMain.handle('window:maximize', () => {
  if (win?.isMaximized()) win.unmaximize()
  else win?.maximize()
})
ipcMain.handle('window:close', () => win?.close())
ipcMain.handle('window:show', () => win?.show())
ipcMain.handle('window:opacity', (_event, value: number) => {
  const clamped = Math.min(100, Math.max(20, Number(value) || 100))
  win?.setOpacity(clamped / 100)
})

/* ------------------------------------------------------------------
    IPC: Notifications
    ------------------------------------------------------------------ */
ipcMain.handle('notification:show', (_event, title: string, body: string) => {
  if (win) {
    win.setTitle(title)
  }
  // Use Electron Notification API
  const { Notification } = require('electron')
  if (Notification.isSupported()) {
    const notification = new Notification({ title, body })
    notification.show()
  }
})

/* ------------------------------------------------------------------
   Ciclo de vida
   ------------------------------------------------------------------ */
app.whenReady().then(() => {
  startBackend()
  createWindow()
  createTray()

  // Global hotkey: Ctrl+Space to toggle window
  globalShortcut.register('CommandOrControl+Space', () => {
    if (win) {
      if (win.isVisible()) {
        win.hide()
      } else {
        win.show()
        win.focus()
      }
    }
  })

  // powerMonitor solo puede usarse tras 'ready'
  powerMonitor.on('suspend', () => console.log('[System] Suspended'))
  powerMonitor.on('resume', () => console.log('[System] Resumed'))

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  // La app vive en la bandeja hasta que el usuario elige "Salir"
  if (isQuitting) {
    stopBackend()
    app.quit()
  }
})

app.on('before-quit', () => {
  isQuitting = true
  stopBackend()
})


