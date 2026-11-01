/**
 * Cliente del runtime autónomo de ARIA para los escenarios (Minecraft, y
 * por el mismo motivo cualquier otro mundo).
 *
 * Va separado del bot a propósito: así se puede probar sin servidor de
 * juego. El bot sólo implementa "qué hacer" con lo que llega.
 */

const DEFAULT_BASE_URL = 'http://127.0.0.1:8002'

/**
 * Crea un cliente del runtime.
 *
 * @param {object} options
 * @param {string} [options.baseUrl]  dónde vive el runtime
 * @param {string} options.token      token Bearer
 * @param {string} options.source      nombre del escenario (`minecraft`, ...)
 * @param {(event: object) => void} options.onEvent  qué hacer con cada evento
 */
export function createRuntime({ baseUrl = DEFAULT_BASE_URL, token, source = 'minecraft', onEvent }) {
  const base = baseUrl.replace(/\/$/, '')

  async function ariaFetch(path, init = {}) {
    const response = await fetch(`${base}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
        ...(init.headers ?? {}),
      },
    })
    if (!response.ok) {
      const body = await response.text().catch(() => '')
      throw new Error(`${init.method ?? 'GET'} ${path} -> ${response.status} ${body}`)
    }
    return response.json()
  }

  /** Informa al runtime de algo que pasa en el mundo. */
  async function report(kind, text, payload = {}) {
    return ariaFetch('/api/autonomy/events', {
      method: 'POST',
      body: JSON.stringify({ kind, source, text, payload }),
    })
  }

  /**
   * Escucha el flujo de eventos sin parar.
   *
   * Si la conexión se cae, se reintenta: un runtime que no está en pie un
   * rato no puede dejar mudo al bot.
   */
  async function listen({ shouldStop = () => false, retryMs = 4000 } = {}) {
    while (!shouldStop()) {
      try {
        const response = await fetch(`${base}/api/autonomy/stream`, {
          headers: { Accept: 'text/event-stream', Authorization: `Bearer ${token}` },
        })
        if (!response.ok || !response.body) throw new Error(`stream -> ${response.status}`)

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (!shouldStop()) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })

          let boundary = buffer.indexOf('\n\n')
          while (boundary >= 0) {
            const frame = buffer.slice(0, boundary)
            buffer = buffer.slice(boundary + 2)
            const line = frame.split('\n').find((entry) => entry.startsWith('data:'))
            if (line) {
              try {
                onEvent?.(JSON.parse(line.slice(5).trim()))
              } catch {
                // Un fragmento ilegible no corta el flujo.
              }
            }
            boundary = buffer.indexOf('\n\n')
          }
        }
      } catch (error) {
        if (shouldStop()) break
        console.error(`[aria] se cayó el flujo: ${error.message}`)
      }
      if (shouldStop()) break
      await new Promise((resolve) => setTimeout(resolve, retryMs))
    }
  }

  return { ariaFetch, report, listen }
}
