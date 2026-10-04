/**
 * Data layer. Six probes, one per element core, each bound to a real ARIA
 * endpoint that exists in this repository:
 *
 *   fire   -> GET /health                     (backend/main.py)
 *   water  -> GET /health/detailed            (backend/main.py)
 *   earth  -> GET /api/swarm/agents/status    (backend/swarm_routes.py)
 *   wind   -> GET /api/swarm/metrics          (backend/swarm_routes.py)
 *   light  -> GET /api/swarm/roles            (backend/swarm_routes.py)
 *   shadow -> GET /api/swarm/status           (backend/swarm_routes.py)
 *
 * Contract taken from the handlers, not from guesswork:
 *   /health              -> {status, service, data_source, detail}
 *   /health/detailed     -> {status, service, checks:{database,redis,local_model}}
 *   /api/swarm/roles     -> {server, count, roles:[{role,name,color,icon,...}]}
 *   /api/swarm/agents/*  -> {server, count, agents:[{id,status,color,icon,...}]}
 *   /api/swarm/metrics   -> {server, ...counters}
 *   /api/swarm/status    -> {swarm, orchestrator, self_healing, process_monitor}
 *
 * Nothing here fabricates a value. A probe that cannot be measured resolves to
 * state "unavailable" with the reason, and the UI renders that reason.
 */

const DEFAULT_BASE = "http://localhost:8000";
const STORAGE_KEY = "aria.raphael.apiBase";
const TIMEOUT_MS = 2500;

export const AXUM_BASE = "http://localhost:8002";

export function resolveBase() {
  const fromQuery = new URLSearchParams(location.search).get("api");
  if (fromQuery) {
    try {
      localStorage.setItem(STORAGE_KEY, fromQuery);
    } catch {
      /* storage unavailable: keep the query value for this page only */
    }
    return fromQuery;
  }
  let stored = null;
  try {
    stored = localStorage.getItem(STORAGE_KEY);
  } catch {
    stored = null;
  }
  return stored || DEFAULT_BASE;
}

export function storeBase(value) {
  try {
    localStorage.setItem(STORAGE_KEY, value);
  } catch {
    /* ignore: the HUD still works for this page load */
  }
}

async function probe(endpoint, base) {
  const url = `${base.replace(/\/+$/, "")}${endpoint}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  const startedAt = performance.now();
  try {
    const res = await fetch(url, {
      signal: controller.signal,
      cache: "no-store",
      headers: { accept: "application/json" },
    });
    const latency_ms = Math.round(performance.now() - startedAt);
    if (!res.ok) {
      return {
        state: "unavailable",
        http_status: res.status,
        detail: `respuesta ${res.status} ${res.statusText}`.trim(),
        latency_ms,
      };
    }
    const body = await res.json();
    return { state: "measured", http_status: res.status, body, latency_ms };
  } catch (err) {
    const aborted = err && err.name === "AbortError";
    return {
      state: "unavailable",
      detail: aborted
        ? `sin respuesta en ${TIMEOUT_MS} ms`
        : "sin red o bloqueado por CORS (el backend no expone este origen)",
      network_error: true,
    };
  } finally {
    clearTimeout(timer);
  }
}

function str(value, fallback = null) {
  if (value === undefined || value === null) return fallback;
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return fallback;
}

function num(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/** Collapse a probe into one of three states the nucleus knows how to draw. */
function classify(result, okWhen) {
  if (result.state !== "measured") return "unavailable";
  return okWhen(result.body) ? "ok" : "degraded";
}

function isHealthyCheck(value) {
  return typeof value === "string" && value.toLowerCase() === "ok";
}

export async function readCore(base) {
  const target = base || resolveBase();
  const [health, detailed, agents, metrics, roles, unified] = await Promise.all([
    probe("/health", target),
    probe("/health/detailed", target),
    probe("/api/swarm/agents/status", target),
    probe("/api/swarm/metrics", target),
    probe("/api/swarm/roles", target),
    probe("/api/swarm/status", target),
  ]);

  const detailedBody = detailed.state === "measured" ? detailed.body : {};
  const checks = detailedBody && typeof detailedBody.checks === "object" && detailedBody.checks ? detailedBody.checks : {};
  const checkList = Object.entries(checks).map(([key, value]) => ({
    key,
    value: str(value, "sin valor"),
    ok: isHealthyCheck(value),
  }));
  const healthyChecks = checkList.filter((c) => c.ok).length;

  const agentsBody = agents.state === "measured" ? agents.body : {};
  const agentList = Array.isArray(agentsBody.agents) ? agentsBody.agents : [];
  const roleList = Array.isArray(roles.state === "measured" ? roles.body.roles : null)
    ? roles.body.roles
    : [];

  const metricsBody = metrics.state === "measured" ? metrics.body : {};
  const counters = Object.entries(metricsBody)
    .filter(([, value]) => typeof value === "number" && Number.isFinite(value))
    .map(([key, value]) => ({ key, value }));

  const unifiedBody = unified.state === "measured" ? unified.body : {};
  // `/api/swarm/status` tiene dos handlers registrados: el de la linea 95
  // (swarm.get_status()) gana por orden de registro y el unificado de la linea
  // 327 es inalcanzable. El que manda devuelve un mapa de contadores del
  // enjambre, no {swarm, orchestrator, ...}, asi que se recorre tal cual sin
  // asumir nombres de campo.
  const signals = unifiedBody && typeof unifiedBody === "object"
    ? Object.entries(unifiedBody).map(([key, value]) => {
        if (value === null || value === undefined) return { key, value: "sin valor" };
        if (Array.isArray(value)) return { key, value: `${value.length} elementos` };
        if (typeof value === "object") return { key, value: `${Object.keys(value).length} claves` };
        return { key, value: str(value, String(value)) };
      })
    : [];

  return {
    base: target,
    measured_at: new Date().toISOString(),
    reachable: health.state === "measured" || detailed.state === "measured",
    cores: [
      {
        id: "fire",
        endpoint: "/health",
        state: classify(health, () => true),
        headline: health.state === "measured" ? str(health.body.status, "sin status") : "sin conexión",
        data_source: health.state === "measured" ? str(health.body.data_source, "unspecified") : "unavailable",
        detail:
          health.state === "measured"
            ? str(health.body.detail, str(health.body.service, ""))
            : health.detail,
        service: health.state === "measured" ? str(health.body.service, null) : null,
        latency_ms: num(health.latency_ms),
      },
      {
        id: "water",
        endpoint: "/health/detailed",
        state: classify(detailed, (body) => {
          const entries = Object.values(body.checks || {});
          return entries.length > 0 && entries.every(isHealthyCheck);
        }),
        headline:
          checkList.length === 0
            ? "sin datos"
            : `${healthyChecks}/${checkList.length} dependencias ok`,
        data_source: checkList.length === 0 ? "unavailable" : "measured",
        detail:
          checkList.length === 0
            ? detailed.state === "measured"
              ? "el backend no devolvió checks"
              : detailed.detail
            : null,
        service: str(detailedBody.service, null),
        checks: checkList,
        latency_ms: num(detailed.latency_ms),
      },
      {
        id: "earth",
        endpoint: "/api/swarm/agents/status",
        state: classify(agents, (body) => Array.isArray(body.agents)),
        headline:
          agents.state === "measured"
            ? `${num(agentsBody.count) ?? agentList.length} agentes registrados`
            : "sin datos",
        data_source: agents.state === "measured" ? "measured" : "unavailable",
        detail: agents.state === "measured" ? str(agentsBody.server, null) : agents.detail,
        agents: agentList.map((agent) => ({
          id: str(agent.id, "?"),
          name: str(agent.name, str(agent.role, "?")),
          role: str(agent.role, null),
          status: str(agent.status, "unknown"),
          color: str(agent.color, "#64748b"),
          icon: str(agent.icon, "•"),
          current_task: agent.current_task === undefined ? null : str(agent.current_task, null),
          tasks_completed: num(agent.tasks_completed),
          error_count: num(agent.error_count),
        })),
        latency_ms: num(agents.latency_ms),
      },
      {
        id: "wind",
        endpoint: "/api/swarm/metrics",
        state: classify(metrics, (body) =>
          Object.values(body).some((value) => typeof value === "number"),
        ),
        headline: counters.length === 0 ? "sin contadores" : `${counters.length} contadores`,
        data_source: counters.length === 0 ? "unavailable" : "measured",
        detail: metrics.state === "measured" ? str(metricsBody.server, null) : metrics.detail,
        counters,
        latency_ms: num(metrics.latency_ms),
      },
      {
        id: "light",
        endpoint: "/api/swarm/roles",
        state: classify(roles, (body) => Array.isArray(body.roles) && body.roles.length > 0),
        headline:
          roles.state === "measured"
            ? `${num(roles.body.count) ?? roleList.length} roles APEX`
            : "sin datos",
        data_source: roles.state === "measured" ? "measured" : "unavailable",
        detail: roles.state === "measured" ? str(roles.body.server, null) : roles.detail,
        roles: roleList.map((role) => ({
          role: str(role.role, "?"),
          name: str(role.name, "?"),
          color: str(role.color, "#64748b"),
          icon: str(role.icon, "•"),
          description: str(role.description, null),
        })),
        latency_ms: num(roles.latency_ms),
      },
      {
        id: "shadow",
        endpoint: "/api/swarm/status",
        state: classify(unified, (body) => Boolean(body) && typeof body === "object"),
        headline: signals.length === 0 ? "sin señales" : `${signals.length} señales`,
        data_source: signals.length === 0 ? "unavailable" : "measured",
        detail: unified.state === "measured" ? null : unified.detail,
        signals,
        latency_ms: num(unified.latency_ms),
      },
    ],
  };
}