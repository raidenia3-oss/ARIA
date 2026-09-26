"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
const child_process_1 = require("child_process");
const path_1 = require("path");
const fs_1 = require("fs");
let win = null;
let tray = null;
let backendProcess = null;
let isQuitting = false;
const BACKEND_PORT = 8000;
// const DEV_URL = 'http://localhost:5173'
/** Raíz del repo en dev: v5/dist-electron → AURA */
const workspaceRoot = (0, path_1.join)(__dirname, '..', '..');
function backendDir() {
    return electron_1.app.isPackaged
        ? (0, path_1.join)(process.resourcesPath, 'backend')
        : (0, path_1.join)(workspaceRoot, 'ARIA_APP', 'backend');
}
function pythonExecutable() {
    if (electron_1.app.isPackaged) {
        const bundled = (0, path_1.join)(process.resourcesPath, 'python', 'python.exe');
        if ((0, fs_1.existsSync)(bundled))
            return bundled;
        // Sin runtime embebido: se usa el Python del sistema si existe
        console.warn('[Backend] runtime embebido ausente → usando Python del sistema');
        return process.platform === 'win32' ? 'python' : 'python3';
    }
    const venv = (0, path_1.join)(workspaceRoot, '.venv', 'Scripts', 'python.exe');
    if ((0, fs_1.existsSync)(venv))
        return venv;
    return process.platform === 'win32' ? 'python' : 'python3';
}
/** Arranca el backend FastAPI v4 (ARIA_APP/backend/app.py) con uvicorn */
function startBackend() {
    const dir = backendDir();
    if (!(0, fs_1.existsSync)((0, path_1.join)(dir, 'app.py'))) {
        console.warn('[Backend] app.py no encontrado en', dir, '→ modo offline');
        return;
    }
    const executable = pythonExecutable();
    const args = ['-m', 'uvicorn', 'app:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)];
    console.log('[Backend] Iniciando:', executable, args.join(' '));
    backendProcess = (0, child_process_1.spawn)(executable, args, {
        cwd: dir,
        env: { ...process.env, BACKEND_PORT: String(BACKEND_PORT), PYTHONUNBUFFERED: '1' },
        stdio: 'pipe',
    });
    backendProcess.stdout?.on('data', (chunk) => process.stdout.write(`[Backend] ${chunk.toString()}`));
    backendProcess.stderr?.on('data', (chunk) => process.stderr.write(`[Backend] ${chunk.toString()}`));
    backendProcess.on('error', (error) => console.error('[Backend] spawn error:', error));
}
function stopBackend() {
    if (!backendProcess)
        return;
    try {
        backendProcess.kill();
    }
    catch (error) {
        console.error('[Backend] kill error:', error);
    }
    backendProcess = null;
}
function createWindow() {
    win = new electron_1.BrowserWindow({
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
            preload: (0, path_1.join)(__dirname, 'preload.js'),
            nodeIntegration: false,
            contextIsolation: true,
            sandbox: false,
            backgroundThrottling: false,
        },
        icon: (0, path_1.join)(__dirname, '..', 'assets', 'icon.png'),
    });
    win.once('ready-to-show', () => win?.show());
    const devServerUrl = process.env.VITE_DEV_SERVER_URL;
    if (devServerUrl) {
        void win.loadURL(devServerUrl);
        win.webContents.openDevTools({ mode: 'detach' });
    }
    else {
        void win.loadFile((0, path_1.join)(__dirname, '..', 'dist', 'index.html'));
    }
    // Puente de logs del renderer → consola principal (debug)
    win.webContents.on('console-message', (_event, level, message) => {
        console.log(`[Renderer:${level}] ${message}`);
    });
    // Enlaces externos → navegador del sistema
    win.webContents.setWindowOpenHandler(({ url }) => {
        void electron_1.shell.openExternal(url);
        return { action: 'deny' };
    });
    // Cerrar = ocultar a bandeja
    win.on('close', (event) => {
        if (!isQuitting) {
            event.preventDefault();
            win?.hide();
        }
    });
    win.on('closed', () => {
        win = null;
    });
}
function createTray() {
    const icon = electron_1.nativeImage.createFromDataURL('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAFklEQVR42mNk+M9QzwAFGC8A2QCqgH9zAAAAAElFTkSuQmCC');
    const menu = electron_1.Menu.buildFromTemplate([
        { label: 'Mostrar ARIA', click: () => win?.show() },
        { type: 'separator' },
        {
            label: 'Salir',
            click: () => {
                isQuitting = true;
                electron_1.app.quit();
            },
        },
    ]);
    tray = new electron_1.Tray(icon);
    tray.setToolTip('ARIA OS v5.0');
    tray.setContextMenu(menu);
    tray.on('click', () => win?.show());
}
/* ------------------------------------------------------------------
   Persistencia de settings (userData/settings.json)
   ------------------------------------------------------------------ */
function settingsFile() {
    return (0, path_1.join)(electron_1.app.getPath('userData'), 'settings.json');
}
function readSettings() {
    try {
        const file = settingsFile();
        if (!(0, fs_1.existsSync)(file))
            return {};
        return JSON.parse((0, fs_1.readFileSync)(file, 'utf8'));
    }
    catch (error) {
        console.error('[Settings] read error:', error);
        return {};
    }
}
function writeSettings(settings) {
    try {
        (0, fs_1.writeFileSync)(settingsFile(), JSON.stringify(settings, null, 2), 'utf8');
        return { ok: true };
    }
    catch (error) {
        console.error('[Settings] write error:', error);
        return { ok: false };
    }
}
/* ------------------------------------------------------------------
   IPC: backend FastAPI
   ------------------------------------------------------------------ */
electron_1.ipcMain.handle('chat:send', async (_event, message) => {
    try {
        const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message }),
        });
        return await response.json();
    }
    catch (error) {
        return { error: String(error) };
    }
});
electron_1.ipcMain.handle('skills:load', async () => {
    try {
        const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/skills`);
        return await response.json();
    }
    catch {
        return [];
    }
});
electron_1.ipcMain.handle('system:status', async () => {
    try {
        const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/system/status`);
        return await response.json();
    }
    catch {
        return { status: 'offline' };
    }
});
/* ------------------------------------------------------------------
   IPC: settings
   ------------------------------------------------------------------ */
electron_1.ipcMain.handle('settings:get', async () => readSettings());
electron_1.ipcMain.handle('settings:set', async (_event, settings) => writeSettings(settings));
/* ------------------------------------------------------------------
   IPC: ventana
   ------------------------------------------------------------------ */
electron_1.ipcMain.handle('window:minimize', () => win?.minimize());
electron_1.ipcMain.handle('window:maximize', () => {
    if (win?.isMaximized())
        win.unmaximize();
    else
        win?.maximize();
});
electron_1.ipcMain.handle('window:close', () => win?.close());
electron_1.ipcMain.handle('window:show', () => win?.show());
electron_1.ipcMain.handle('window:opacity', (_event, value) => {
    const clamped = Math.min(100, Math.max(20, Number(value) || 100));
    win?.setOpacity(clamped / 100);
});
/* ------------------------------------------------------------------
   Ciclo de vida
   ------------------------------------------------------------------ */
electron_1.app.whenReady().then(() => {
    startBackend();
    createWindow();
    createTray();
    // powerMonitor solo puede usarse tras 'ready'
    electron_1.powerMonitor.on('suspend', () => console.log('[System] Suspended'));
    electron_1.powerMonitor.on('resume', () => console.log('[System] Resumed'));
    electron_1.app.on('activate', () => {
        if (electron_1.BrowserWindow.getAllWindows().length === 0)
            createWindow();
    });
});
electron_1.app.on('window-all-closed', () => {
    // La app vive en la bandeja hasta que el usuario elige "Salir"
    if (isQuitting) {
        stopBackend();
        electron_1.app.quit();
    }
});
electron_1.app.on('before-quit', () => {
    isQuitting = true;
    stopBackend();
});
