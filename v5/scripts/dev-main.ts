import { spawn } from 'child_process'
import { platform } from 'process'

// Run main process with Electron + tsx for TypeScript support
const isWindows = platform === 'win32'
const electronCmd = isWindows ? 'npx.cmd' : 'npx'

const child = spawn(electronCmd, ['electron', '--import=tsx', 'electron/main.ts'], {
  cwd: process.cwd(),
  stdio: 'inherit',
  env: { ...process.env, NODE_ENV: 'development' },
  shell: isWindows, // Use shell on Windows to find npx.cmd
})

child.on('error', (err) => {
  console.error('Failed to start main process:', err)
  process.exit(1)
})

child.on('exit', (code) => {
  process.exit(code ?? 0)
})