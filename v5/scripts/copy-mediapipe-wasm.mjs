/**
 * Copia el runtime WASM de MediaPipe al `public/` del renderer.
 *
 * `FilesetResolver.forVisionTasks()` carga el WASM desde una ruta servida por
 * el renderer, no desde `node_modules`. Se copia en cada build en vez de
 * versionar el binario en el repo: así el runtime siempre corresponde a la
 * versión instalada de `@mediapipe/tasks-vision` y no queda desactualizado.
 */
import { cp, mkdir, readdir, stat } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const root = join(here, '..')
const source = join(root, 'node_modules', '@mediapipe', 'tasks-vision', 'wasm')
const target = join(root, 'public', 'mediapipe', 'wasm')

async function main() {
  try {
    await stat(source)
  } catch {
    console.error(
      `[mediapipe] no existe ${source}\n` +
        '[mediapipe] ejecuta "npm install" antes de compilar.',
    )
    process.exit(1)
  }

  await mkdir(dirname(target), { recursive: true })
  await cp(source, target, { recursive: true })

  const files = await readdir(target)
  console.log(`[mediapipe] runtime WASM copiado a public/mediapipe/wasm (${files.length} archivos)`)
}

main().catch((error) => {
  console.error('[mediapipe] fallo al copiar el runtime WASM:', error)
  process.exit(1)
})
