/**
 * Cliente tipado del backend ARIA v6.0 en Axum (Rust).
 *
 * Puerto 8002 — corre en paralelo al backend FastAPI legacy (8000) durante
 * la migración gradual. El servidor expone CORS permisivo (`CorsLayer::permissive`),
 * por lo que el renderer puede llamar directamente sin proxy de Vite.
 *
 * Contratos verificados contra `v6/axum-poc/src` y contra el servidor en vivo:
 *   GET  /health                -> core.rs
 *   POST /api/chat              -> chat.rs
 *   POST /api/pc/state          -> daemon.rs
 *   POST /api/daemon/heartbeat  -> daemon.rs
 */

export const ARIA_BACKEND_ORIGIN = 'http://127.0.0.1:8002'

function resolveOrigin(): string {
  const override = import.meta.env?.VITE_ARIA_BACKEND_URL
  if (typeof override === 'string' && override.length > 0) {
    return override.replace(/\/+$/, '')
  }
  return ARIA_BACKEND_ORIGIN
}

export interface HealthResponse {
  status: string
  framework: string
  version: string
  uptime_ms: number
}

export interface ChatResponse {
  response: string
  provider: string
  latency_ms: number
  session_id: string | null
}

export interface PcStateResponse {
  active: boolean
  idle_seconds: number
  session_user: string
  timestamp: number
}

export interface HeartbeatResponse {
  status: string
  timestamp: number
}

export interface ChatRequest {
  message: string
  session_id?: string | null
  provider?: string | null
}

/** `DaemonRequest` de daemon.rs — todos los campos son opcionales. */
export interface DaemonRequest {
  agent_id?: string
  action?: string
  status?: string
  task?: unknown
  result?: unknown
  pc_state?: unknown
}

export type BackendConnectionState = 'connecting' | 'online' | 'offline'

export interface AriaBackendClient {
  origin: string
  health: (signal?: AbortSignal) => Promise<HealthResponse>
  chat: (req: ChatRequest, signal?: AbortSignal) => Promise<ChatResponse>
  pcState: (req?: DaemonRequest, signal?: AbortSignal) => Promise<PcStateResponse>
  heartbeat: (req?: DaemonRequest, signal?: AbortSignal) => Promise<HeartbeatResponse>
}

const DEFAULT_TIMEOUT_MS = 8000
const CHAT_TIMEOUT_MS = 120000

export class AriaBackendError extends Error {
  readonly status?: number
  readonly path: string

  constructor(message: string, path: string, status?: number) {
    super(message)
    this.name = 'AriaBackendError'
    this.path = path
    this.status = status
  }
}

async function request<T>(
  path: string,
  init: RequestInit,
  timeoutMs: number,
  signal?: AbortSignal,
): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  const onAbort = () => controller.abort()
  signal?.addEventListener('abort', onAbort)

  try {
    const response = await fetch(`${resolveOrigin()}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...(init.headers ?? {}),
      },
    })

    if (!response.ok) {
      const body = await response.text().catch(() => '')
      throw new AriaBackendError(
        `${init.method ?? 'GET'} ${path} -> ${response.status} ${response.statusText}${body ? `: ${body}` : ''}`,
        path,
        response.status,
      )
    }

    return (await response.json()) as T
  } catch (error) {
    if (error instanceof AriaBackendError) throw error
    if (signal?.aborted) throw error
    const reason = error instanceof Error ? error.message : String(error)
    throw new AriaBackendError(`${init.method ?? 'GET'} ${path} -> ${reason}`, path)
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', onAbort)
  }
}

function postJson(body: unknown) {
  return JSON.stringify(body)
}

export const ariaBackend: AriaBackendClient = {
  origin: ARIA_BACKEND_ORIGIN,

  health: (signal) =>
    request<HealthResponse>('/health', { method: 'GET' }, DEFAULT_TIMEOUT_MS, signal),

  chat: (req, signal) =>
    request<ChatResponse>(
      '/api/chat',
      { method: 'POST', body: postJson(req) },
      CHAT_TIMEOUT_MS,
      signal,
    ),

  pcState: (req = {}, signal) =>
    request<PcStateResponse>(
      '/api/pc/state',
      { method: 'POST', body: postJson(req) },
      DEFAULT_TIMEOUT_MS,
      signal,
    ),

  heartbeat: (req = {}, signal) =>
    request<HeartbeatResponse>(
      '/api/daemon/heartbeat',
      { method: 'POST', body: postJson(req) },
      DEFAULT_TIMEOUT_MS,
      signal,
    ),
}
