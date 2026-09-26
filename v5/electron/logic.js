// Logic process - handles chat, skills, system status IPC
// Runs as a separate Node.js process (no electron dependencies)

const { spawn } = require('child_process');
const { join } = require('path');
const { existsSync } = require('fs');

const BACKEND_PORT = parseInt(process.env.BACKEND_PORT) || 8000;
const workspaceRoot = join(__dirname, '..', '..');

let backendProcess = null;

function backendDir() {
  return join(workspaceRoot, 'ARIA_APP', 'backend');
}

function pythonExecutable() {
  const venv = join(workspaceRoot, '.venv', 'Scripts', 'python.exe');
  if (existsSync(venv)) return venv;
  return process.platform === 'win32' ? 'python' : 'python3';
}

function startBackend() {
  const dir = backendDir();
  if (!existsSync(join(dir, 'app.py'))) {
    console.warn('[Backend] app.py no encontrado en', dir, '→ modo offline');
    return;
  }

  const executable = pythonExecutable();
  const args = ['-m', 'uvicorn', 'app:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)];
  console.log('[Backend] Iniciando:', executable, args.join(' '));

  backendProcess = spawn(executable, args, {
    cwd: dir,
    env: { ...process.env, BACKEND_PORT: String(BACKEND_PORT), PYTHONUNBUFFERED: '1' },
    stdio: 'pipe',
  });

  backendProcess.stdout?.on('data', (chunk) => process.stdout.write(`[Backend] ${chunk.toString()}`));
  backendProcess.stderr?.on('data', (chunk) => process.stderr.write(`[Backend] ${chunk.toString()}`));
  backendProcess.on('error', (error) => console.error('[Backend] spawn error:', error));
}

function stopBackend() {
  if (backendProcess) {
    try { backendProcess.kill(); } catch (e) { console.error('[Backend] kill error:', e); }
    backendProcess = null;
  }
}

// IPC handlers
async function handleChatSend(message) {
  try {
    const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    });
    return await response.json();
  } catch (error) {
    return { error: String(error) };
  }
}

async function handleSkillsLoad() {
  try {
    const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/skills`);
    return await response.json();
  } catch {
    return [];
  }
}

async function handleSystemStatus() {
  try {
    const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/system/status`);
    return await response.json();
  } catch {
    return { status: 'offline' };
  }
}

// Message handler
process.on('message', async (message) => {
  if (!message || !message.type) return;

  let result;
  try {
    switch (message.type) {
      case 'chat:send':
        result = await handleChatSend(message.payload);
        break;
      case 'skills:load':
        result = await handleSkillsLoad();
        break;
      case 'system:status':
        result = await handleSystemStatus();
        break;
      default:
        result = { error: `Unknown message type: ${message.type}` };
    }
  } catch (error) {
    result = { error: String(error) };
  }

  // Send response back to main process
  process.send({
    type: 'ipc-response',
    id: message.id,
    result,
  });
});

// Start backend
startBackend();

console.log('[Logic] Process started, waiting for messages...');

// Handle shutdown
process.on('SIGTERM', () => {
  stopBackend();
  process.exit(0);
});

process.on('SIGINT', () => {
  stopBackend();
  process.exit(0);
});