// AURA UI service layer.
// Punto único de conexión con el backend de producción (FastAPI en Render).
// La URL base se resuelve en este orden:
//   1. import.meta.env.NEXT_PUBLIC_BACKEND_URL (define en .env)
//   2. variable de entorno del navegador (window)
//   3. fallback a la URL de producción conocida
//   4. localhost:8000 (solo para desarrollo local)

function resolveBase(): string {
    const fromEnv = (import.meta as any).env?.NEXT_PUBLIC_BACKEND_URL;
    if (fromEnv && typeof fromEnv === "string" && fromEnv.trim()) {
        return fromEnv.replace(/\/+$/, "");
    }
    if (typeof window !== "undefined") {
        const w = window as any;
        if (w.NEXT_PUBLIC_BACKEND_URL) return String(w.NEXT_PUBLIC_BACKEND_URL).replace(/\/+$/, "");
    }
    // Producción: mismo origen si se sirve desde el backend, o URL fija de Render.
    if (typeof window !== "undefined" && window.location && window.location.hostname !== "localhost") {
        return "";
    }
    return "http://localhost:8000";
}

const BASE = resolveBase();

function url(path: string): string {
    if (!BASE) return path; // mismo origen (servido por FastAPI)
    return `${BASE}${path}`;
}

export interface HealthStatus {
    status: string;
    ai?: Record<string, { ok: boolean; latency_ms?: number; status?: number; error?: string }>;
}

export interface ChatResult {
    reply: string;
    provider?: string;
    intent?: Record<string, unknown> | null;
    task_status?: unknown;
}

export interface BotStatus {
    id: string;
    name: string;
    status: string;
}

export interface ActivityLog {
    ts: string;
    level: string;
    message: string;
}

export interface BalanceResponse {
    total_balance: number;
    currency: string;
}

export interface SuccessRateResponse {
    rate: number;
    total_tasks: number;
    successful_tasks: number;
}

export async function getHealth(): Promise<HealthStatus> {
    const res = await fetch(url("/health"));
    if (!res.ok) throw new Error(`health ${res.status}`);
    return res.json();
}

export async function sendChat(
    message: string,
    context?: string,
): Promise<ChatResult> {
    const res = await fetch(url("/api/chat"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: message, context: context ?? null }),
    });
    if (!res.ok) throw new Error(`chat ${res.status}`);
    return res.json();
}

export async function getStatus(): Promise<BotStatus[]> {
    const res = await fetch(url("/api/status"));
    if (!res.ok) throw new Error(`status ${res.status}`);
    return res.json();
}

export async function getActivity(limit = 5): Promise<ActivityLog[]> {
    const res = await fetch(url(`/api/activity?limit=${limit}`));
    if (!res.ok) throw new Error(`activity ${res.status}`);
    return res.json();
}

export async function getBalance(): Promise<BalanceResponse> {
    const res = await fetch(url("/api/balance"));
    if (!res.ok) throw new Error(`balance ${res.status}`);
    return res.json();
}

export async function getSuccessRate(): Promise<SuccessRateResponse> {
    const res = await fetch(url("/api/success-rate"));
    if (!res.ok) throw new Error(`success-rate ${res.status}`);
    return res.json();
}

export interface NeuralStatus {
    neural: {
        weights: number[];
        bias: number;
        learning_rate: number;
        iterations: number;
        last_stability: number | null;
        last_error: number | null;
        keep_alive_fired: number;
        threshold: number;
    };
    last_tick: {
        stability: number;
        instability: boolean;
        real_inactivity: boolean;
        keep_alive_fired: number;
        train_error: number;
    };
    sys_vitals: {
        latency_ms: number;
        memory_percent: number;
        cpu_percent: number;
        health_pings: number;
        msg_rate: number;
    };
}

export async function getNeuralStatus(): Promise<NeuralStatus> {
    const res = await fetch(url("/neural/status"));
    if (!res.ok) throw new Error(`neural-status ${res.status}`);
    return res.json();
}

export interface ChatHistory {
    messages: {
        id: number;
        role: string;
        content: string;
        provider: string | null;
        session_id: string | null;
        created_at: string | null;
    }[];
    total: number;
}

export async function getChatHistory(limit = 50): Promise<ChatHistory> {
    const res = await fetch(url(`/api/chat/history?limit=${limit}`));
    if (!res.ok) throw new Error(`chat-history ${res.status}`);
    return res.json();
}

export interface MemoryItem {
    id: number;
    content: string;
    kind: string;
    timestamp: string | null;
}

export interface SemanticMemory {
    memories: MemoryItem[];
    total: number;
}

export async function getMemory(limit = 20): Promise<SemanticMemory> {
    const res = await fetch(url(`/api/memory?limit=${limit}`));
    if (!res.ok) throw new Error(`memory ${res.status}`);
    return res.json();
}

