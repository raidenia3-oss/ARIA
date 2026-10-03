/**
 * Cliente tipado del backend ARIA v6.0 en Axum (Rust).
 *
 * Puerto 8002 — corre en paralelo al backend FastAPI legacy (8000) durante
 * la migración gradual. El servidor expone CORS permisivo (`CorsLayer::permissive`),
 * por lo que el renderer puede llamar directamente sin proxy de Vite.
 *
 * Contratos verificados contra `v6/axum-poc/src` y contra el servidor en vivo:
 *   GET  /health                       -> core.rs
 *   POST /api/chat                     -> chat.rs
 *   POST /api/pc/state                 -> daemon.rs
 *   POST /api/daemon/heartbeat         -> daemon.rs
 *   GET  /api/control/status           -> control.rs (status)
 *   GET  /api/control/services         -> control.rs (services)
 *   GET  /api/control/progress         -> control.rs (progress)
 *   WS   /api/control/progress/stream  -> control.rs (progress_stream)
 *   GET  /api/agents/status            -> agents.rs (swarm_status)
 *
 * AUTH: todo `/api/*` pasa por el middleware `RequireAuth` de
 * `v6/axum-poc/src/auth.rs` salvo `/api/auth/login|register|refresh`.
 * `request()` inyecta el encabezado de credencial en cada llamada.
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

/* ------------------------------------------------------------------ *
 * Plano de control — contratos de `v6/axum-poc/src/control.rs`
 * ------------------------------------------------------------------ */

/**
 * Vocabulario REAL de `ServiceStatus::as_str()` (control.rs:346-354).
 *
 * El panel anterior	typeaba 'online'|'degraded'|'offline', que el servidor
 * nunca emite: `statusConfig[svc.status]` daba `undefined` y `cfg.icon`
 * lanzaba en tiempo de ejecución con datos reales.
 */
export type ServiceStatusName = 'running' | 'stopped' | 'unknown'

/** Fila de `GET /api/control/services` y de `status.services`. */
export interface ControlService {
  name: string
  description: string
  status: ServiceStatusName
  pid: number | null
  /** Puerto numérico. El servidor NO envía `latency`. */
  port: number | null
}

/** `GET /api/control/status` (control.rs:1242-1300). No incluye cpu/mem/disk. */
export interface ControlStatusResponse {
  aria_version: string
  channel: string
  uptime_seconds: number
  /** Ya viene formateado por el servidor (`format_uptime`). */
  uptime: string
  services: ControlService[]
  services_total: number
  services_healthy: number
  last_update_check: string | null
  config: Record<string, string> | null
  config_path: string | null
  auth: unknown
  checked_at: string
  server: string
}

/** `GET /api/control/services` (control.rs:1309-1336). */
export interface ControlServicesResponse {
  services: ControlService[]
  count: number
  checked_at: string
  server: string
}

/**
 * Fases que emite `apply_frame` (control.rs:533-579). Es un conjunto
 * DOCUMENTADO, no cerrado: el aviso de lag del WebSocket y cualquier fase
 * futura llegan como `string` y el cliente debe tolerarlas.
 */
export type ProgressPhase = 'idle' | 'running' | 'ok' | 'failed'

/**
 * `current` de `ProgressSnapshot`, armado por `pick_fields(frame, ["name","tier","index"])`.
 * Solo se copian las claves presentes en el frame NDJSON: cualquier subconjunto.
 */
export interface ProgressStep {
  name?: string
  tier?: string
  index?: number
}

/**
 * `last` de `ProgressSnapshot`, armado por
 * `pick_fields(frame, ["name","tier","index","status","message","elapsed_s"])`.
 * Igual que `current`: cualquier subconjunto puede faltar.
 */
export interface ProgressLastStep extends ProgressStep {
  status?: string
  message?: string
  elapsed_s?: number
}

/**
 * `ProgressSnapshot` (control.rs:449-464).
 *
 * IMPORTANTE: en Rust los campos `Option` llevan
 * `#[serde(skip_serializing_if = "Option::is_none")]`, así que se OMITEN
 * cuando se desconoce. Nunca llegan como `null` ni como `0`. Por eso todos
 * son opcionales aquí y el cliente convierte la ausencia en `null`/"—",
 * nunca en un cero inventado.
 *
 * `phase` se tipa como `string` y no como `ProgressPhase` a propósito: el
 * servidor es la autoridad y puede emitir un valor fuera del conjunto.
 */
export interface ProgressSnapshot {
  phase: string
  run_id?: string
  total?: number
  steps_done?: number
  current?: ProgressStep
  last?: ProgressLastStep
  updated_at: string
}

/** Envoltura de `GET /api/control/progress` (control.rs:1428-1443). */
export interface ProgressResponse {
  progress: ProgressSnapshot
  /** `PROGRESS_POLL_INTERVAL_SECS` = 2 (control.rs:84). */
  poll_interval_seconds: number
  stream: string
  note: string
  server: string
}

/* ------------------------------------------------------------------ *
 * Enjambre de agentes — contrato de `v6/axum-poc/src/agents.rs`
 * ------------------------------------------------------------------ */

/**
 * Vocabulario de estado NORMALIZADO para consumo en UI.
 *
 * No es un enum del servidor: `AgentRow.status` es un `String` sin restringir
 * (agents.rs:52), así que el cliente es la autoridad de la normalización. Este
 * es el mismo conjunto que ya usa `AgentStatusDashboard.tsx`; vive aquí para
 * que un tercer consumidor no invente un cuarto vocabulario.
 */
export type AgentStatusName = 'idle' | 'busy' | 'error' | 'stalled' | 'offline'

const AGENT_STATUS_NAMES: ReadonlySet<string> = new Set([
  'idle',
  'busy',
  'error',
  'stalled',
  'offline',
])

/**
 * Normaliza el estado crudo del servidor. Desconocido ⇒ `offline`, nunca
 * `busy`: un valor no reconocido no puede affirmar que el agente trabaja.
 * `stale === true` ⇒ `stalled`, que es lo que el servidor sí midió
 * (`last_heartbeat` más viejo que `HEARTBEAT_STALE_SECS`, agents.rs:28).
 */
export function normalizeAgentStatus(raw: unknown, stale?: boolean): AgentStatusName {
  if (stale === true) return 'stalled'
  const value = typeof raw === 'string' ? raw.toLowerCase() : ''
  return AGENT_STATUS_NAMES.has(value) ? (value as AgentStatusName) : 'offline'
}

/**
 * `AgentRow` (agents.rs:49-65).
 *
 * IMPORTANTE: en Rust los cuatro campos de telemetría son `Option` con
 * `#[serde(skip_serializing_if = "Option::is_none")]`, así que se OMITEN
 * cuando no se midieron: nunca llegan como `null` ni como `0`. Por eso los
 * cuatro son opcionales aquí, y una clave ausente significa "NO MEDIDO", no
 * cero. El cliente convierte la ausencia en `null`/"untracked", nunca en un
 * `0` inventado.
 *
 * `status` es `string` a propósito: el servidor es la autoridad y puede emitir
 * un valor fuera del conjunto documentado.
 *
 * El servidor NO emite `task_count`, `error_count` ni `pipeline_ready`: no
 * existen contadores por agente (véase `STATUS_NOTE`, agents.rs:32).
 */
export interface SwarmAgentRow {
  id: string
  name: string
  role: string
  status: string
  /** `"daemon"` para agentes que hacen heartbeat; `"declared"` para el roster. */
  source: 'daemon' | 'declared'
  last_heartbeat?: number
  heartbeat_age_seconds?: number
  current_task?: string | null
  stale?: boolean
}

/**
 * `GET /api/agents/status` (struct en agents.rs:34-42, handler en 142-171).
 *
 * Los cinco campos de primer nivel no llevan `skip_serializing_if`, así que
 * siempre viajan. `queue_depth` es el único agregado MEDIDO: pendientes de
 * `SharedState.task_queue`. No es un "total de tareas" y no debe rotularse
 * como tal.
 */
export interface SwarmStatusResponse {
  name: string
  agent_count: number
  agents: SwarmAgentRow[]
  /** Tareas PENDIENTES medidas, no "tareas totales ejecutadas". */
  queue_depth: number
  /** `STATUS_NOTE` verbatim: documenta en la propia respuesta qué no se mide. */
  note: string
}

export interface AriaBackendClient {
  origin: string
  health: (signal?: AbortSignal) => Promise<HealthResponse>
  chat: (req: ChatRequest, signal?: AbortSignal) => Promise<ChatResponse>
  pcState: (req?: DaemonRequest, signal?: AbortSignal) => Promise<PcStateResponse>
  heartbeat: (req?: DaemonRequest, signal?: AbortSignal) => Promise<HeartbeatResponse>
  controlStatus: (signal?: AbortSignal) => Promise<ControlStatusResponse>
  controlServices: (signal?: AbortSignal) => Promise<ControlServicesResponse>
  agentsStatus: (signal?: AbortSignal) => Promise<SwarmStatusResponse>
  progress: (signal?: AbortSignal) => Promise<ProgressSnapshot>
  progressStreamUrl: () => string
}

const DEFAULT_TIMEOUT_MS = 8000
const CHAT_TIMEOUT_MS = 120000

/** Límite duro de sondeo de progreso: nunca más rápido que esto (ver abajo). */
export const PROGRESS_POLL_INTERVAL_MS = 2000

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

/* ------------------------------------------------------------------ *
 * Credenciales
 * ------------------------------------------------------------------ */

/** Usuario fijo del último recurso. El servidor no valida contraseñas. */
const FALLBACK_LOGIN_USERNAME = 'aria-control-center'

/**
 * La clave resuelta, o `null` si no se pudo obtener. `null` también se
 * memoriza a propósito: dentro de un bucle de sondeo de 2s, un login fallido
 * sin memorizar quemaría 30 req/min de las 100/min del rate limit
 * (`RATE_LIMIT_MAX` en state.rs:20) sólo en re-logins.
 */
let apiKeyPromise: Promise<string | null> | null = null

/**
 * Puente de Electron, si algún día existe.
 *
 * HOY NO EXISTE: `v5/electron/preload.ts` expone 53 métodos y ninguno es
 * `ariaApiKey` ni `axumApiKey` (tampoco en `main.ts`), y `vite-env.d.ts` no
 * los declara. Se lee con un cast defensivo para que, si alguien lo añade
 * después, este cliente lo use sin tocar nada más. No se añade el canal IPC
 * aquí a propósito.
 */
function readBridgeApiKey(): string | null {
  if (typeof window === 'undefined') return null
  const bridge = (window as unknown as { electronAPI?: Record<string, unknown> }).electronAPI
  if (!bridge || typeof bridge !== 'object') return null
  for (const channel of ['ariaApiKey', 'axumApiKey'] as const) {
    const value = (bridge as Record<string, unknown>)[channel]
    if (typeof value === 'string' && value.length > 0) return value
  }
  return null
}

/**
 * Último recurso: `POST /api/auth/login`.
 *
 * ADVERTENCIA DE SEGURIDAD, dicha con todas sus letras: esto hace que el
 * renderer se autentique PIDIENDO la clave AL PROPIO SERVIDOR. El handler
 * `login` (auth.rs:312-329) devuelve `state.api_key()` para CUALQUIER nombre
 * de usuario y NO verifica ninguna contraseña. Es una debilidad PREEXISTENTE
 * del backend, no algo que este cliente introduzca ni que pueda arreglar; no
 * debe entenderse como un esquema de autenticación sólido, y por eso queda
 * aquí, al final de la cadena, y no antes.
 */
async function loginForApiKey(): Promise<string | null> {
  try {
    const response = await fetch(`${resolveOrigin()}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: FALLBACK_LOGIN_USERNAME }),
    })
    if (!response.ok) return null
    const payload = (await response.json()) as { token?: unknown }
    return typeof payload.token === 'string' && payload.token.length > 0 ? payload.token : null
  } catch {
    return null
  }
}

async function resolveAriaApiKey(): Promise<string | null> {
  const fromBridge = readBridgeApiKey()
  if (fromBridge) return fromBridge

  const fromEnv = import.meta.env?.VITE_ARIA_API_KEY
  if (typeof fromEnv === 'string' && fromEnv.length > 0) return fromEnv

  return loginForApiKey()
}

/**
 * Resuelve la clave del backend una sola vez (incluido el resultado `null`).
 * Nunca se registra ni se renderiza la clave.
 */
export function getAriaApiKey(): Promise<string | null> {
  if (!apiKeyPromise) {
    apiKeyPromise = resolveAriaApiKey().catch(() => null)
  }
  return apiKeyPromise
}

/** Encabezados de credencial para `extract_bearer()` (auth.rs:161-176). */
async function authHeaders(): Promise<Record<string, string>> {
  const key = await getAriaApiKey()
  return key ? { Authorization: `Bearer ${key}` } : {}
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
    const auth = await authHeaders()
    const response = await fetch(`${resolveOrigin()}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...auth,
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

function toWebSocketOrigin(origin: string): string {
  return origin.replace(/^https:/, 'wss:').replace(/^http:/, 'ws:')
}

/**
 * URL del WebSocket de progreso. AFFORDANCE DOCUMENTADA Y DELIBERADAMENTE
 * NO USADA: el constructor `WebSocket` del navegador NO admite cabeceras, y
 * `extract_bearer()` sólo lee `Authorization`/`x-api-key` en la petición de
 * upgrade, así que un socket abierto desde el renderer recibiría 401 al
 * upgrade. El sondeo HTTP es por eso el transporte real (`useScanProgress`).
 * Cuando exista un canal de Electron o una cookie de sesión, esta función
 * pasa a ser utilizable sin más cambios.
 */
function progressStreamUrl(): string {
  return `${toWebSocketOrigin(resolveOrigin())}/api/control/progress/stream`
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

  controlStatus: (signal) =>
    request<ControlStatusResponse>('/api/control/status', { method: 'GET' }, DEFAULT_TIMEOUT_MS, signal),

  controlServices: (signal) =>
    request<ControlServicesResponse>(
      '/api/control/services',
      { method: 'GET' },
      DEFAULT_TIMEOUT_MS,
      signal,
    ),

  agentsStatus: async (signal) => {
    const payload = await request<SwarmStatusResponse>(
      '/api/agents/status',
      { method: 'GET' },
      DEFAULT_TIMEOUT_MS,
      signal,
    )
    // El servidor siempre envía `agents` como array. Si algún día no llegara,
    // esto lanza en vez de devolver `[]`: un array vacío se lee en pantalla
    // como "no hay agentes registrados", y eso sería un dato inventado.
    if (!payload || !Array.isArray(payload.agents)) {
      throw new AriaBackendError(
        'GET /api/agents/status -> respuesta sin `agents` (unavailable)',
        '/api/agents/status',
      )
    }
    return payload
  },

  progress: async (signal) => {
    const payload = await request<ProgressResponse>(
      '/api/control/progress',
      { method: 'GET' },
      DEFAULT_TIMEOUT_MS,
      signal,
    )
    // El servidor siempre envía `progress`, pero si algún día no lo hace,
    // esto es un reposo honesto en vez de un `undefined` que rompería el render.
    return payload.progress ?? { phase: 'idle', updated_at: '' }
  },

  progressStreamUrl,
}
