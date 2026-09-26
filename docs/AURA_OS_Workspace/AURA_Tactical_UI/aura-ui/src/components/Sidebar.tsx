import { useEffect, useState } from "react";
import {
    getHealth,
    getStatus,
    getActivity,
    getBalance,
    getSuccessRate,
    getNeuralStatus,
    getMemory,
    type HealthStatus,
    type BotStatus,
    type ActivityLog,
    type BalanceResponse,
    type SuccessRateResponse,
    type NeuralStatus,
    type SemanticMemory,
} from "../services/api";
import KnowledgeBase from "./KnowledgeBase";

export default function Sidebar({
    persona,
    onPersonaChange,
    provider,
    onProviderChange,
}: {
    persona: string;
    onPersonaChange: (v: string) => void;
    provider: string;
    onProviderChange: (v: string) => void;
}) {
    const [bots, setBots] = useState<BotStatus[]>([]);
    const [health, setHealth] = useState<HealthStatus | null>(null);
    const [activity, setActivity] = useState<ActivityLog[]>([]);
    const [balance, setBalance] = useState<BalanceResponse | null>(null);
    const [success, setSuccess] = useState<SuccessRateResponse | null>(null);
    const [neural, setNeural] = useState<NeuralStatus | null>(null);
    const [memory, setMemory] = useState<SemanticMemory | null>(null);
    const [showKb, setShowKb] = useState(false);

    useEffect(() => {
        getHealth()
            .then(setHealth)
            .catch(() => setHealth(null));
        getStatus()
            .then(setBots)
            .catch(() => setBots([]));
        getActivity(5)
            .then(setActivity)
            .catch(() => setActivity([]));
        getBalance()
            .then(setBalance)
            .catch(() => setBalance(null));
        getSuccessRate()
            .then(setSuccess)
            .catch(() => setSuccess(null));
        getNeuralStatus()
            .then(setNeural)
            .catch(() => setNeural(null));
        getMemory(10)
            .then(setMemory)
            .catch(() => setMemory(null));
    }, []);

    // Refresco en vivo del Núcleo Evolutivo (cada 5 s).
    useEffect(() => {
        const id = setInterval(() => {
            getNeuralStatus()
                .then(setNeural)
                .catch(() => {});
            getMemory(10)
                .then(setMemory)
                .catch(() => {});
        }, 5000);
        return () => clearInterval(id);
    }, []);

    const aiOk = health?.ai ? Object.values(health.ai).filter((v) => v.ok).length : 0;
    const aiTotal = health?.ai ? Object.keys(health.ai).length : 0;

    return (
        <aside className="bg-aura-panel border-r border-white/5 flex flex-col h-full overflow-y-auto">
            <div className="p-4 border-b border-white/5">
                <h2 className="text-sm font-semibold uppercase tracking-widest text-aura-muted">
                    AURA Control
                </h2>
            </div>

            <div className="p-4 space-y-6">
                {/* Persona */}
                <div>
                    <label className="block text-xs text-aura-muted mb-1">Persona / Agente</label>
                    <select
                        value={persona}
                        onChange={(e) => onPersonaChange(e.target.value)}
                        className="w-full bg-aura-bg border border-white/10 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-aura-cyan/50"
                    >
                        <option>AURA Standard</option>
                        <option>Senior Architect</option>
                        <option>Creative</option>
                    </select>
                </div>

                {/* Provider mode */}
                <div>
                    <label className="block text-xs text-aura-muted mb-1">Modo</label>
                    <div className="flex gap-1">
                        {["Automático", "Solo Local", "Solo Nube"].map((opt) => (
                            <button
                                key={opt}
                                onClick={() => onProviderChange(opt)}
                                className={`flex-1 text-xs py-1.5 rounded ${
                                    provider === opt
                                        ? "bg-aura-cyan/20 text-aura-cyan border border-aura-cyan/40"
                                        : "bg-aura-bg text-aura-muted border border-white/5"
                                }`}
                            >
                                {opt === "Automático"
                                    ? "Auto"
                                    : opt === "Solo Local"
                                      ? "Local"
                                      : "Nube"}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Server status */}
                <div className="border-t border-white/5 pt-4">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-aura-muted mb-2">
                        🌐 Estado del Servidor
                    </h3>
                    <div className="space-y-1 text-xs">
                        <p className="flex justify-between">
                            <span className="text-aura-muted">API</span>
                            <span
                                className={
                                    health?.status === "ok" ? "text-aura-green" : "text-red-400"
                                }
                            >
                                {health?.status === "ok" ? "🟢 Online" : "🔴 Offline"}
                            </span>
                        </p>
                        <p className="flex justify-between">
                            <span className="text-aura-muted">IA disponibles</span>
                            <span className="text-white">
                                {aiOk}/{aiTotal}
                            </span>
                        </p>
                        {balance && (
                            <p className="flex justify-between">
                                <span className="text-aura-muted">Balance</span>
                                <span className="text-white">
                                    {balance.total_balance.toFixed(2)} {balance.currency}
                                </span>
                            </p>
                        )}
                        {success && (
                            <p className="flex justify-between">
                                <span className="text-aura-muted">Tasa éxito</span>
                                <span className="text-white">
                                    {(success.rate * 100).toFixed(1)}%
                                </span>
                            </p>
                        )}
                    </div>
                </div>

                {/* Bots / Módulos */}
                <div className="border-t border-white/5 pt-4">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-aura-muted mb-2">
                        🤖 Módulos
                    </h3>
                    <div className="space-y-1 max-h-32 overflow-y-auto">
                        {bots.length === 0 && (
                            <p className="text-xs text-aura-muted">Sin módulos aún</p>
                        )}
                        {bots.map((b) => (
                            <div
                                key={b.id}
                                className="text-xs text-aura-muted bg-aura-bg rounded px-2 py-1 flex justify-between"
                            >
                                <span className="truncate">{b.name}</span>
                                <span
                                    className={
                                        b.status === "Running"
                                            ? "text-aura-green"
                                            : b.status === "Blocked"
                                              ? "text-red-400"
                                              : "text-aura-muted"
                                    }
                                >
                                    {b.status}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Actividad */}
                <div className="border-t border-white/5 pt-4">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-aura-muted mb-2">
                        📡 Actividad
                    </h3>
                    <div className="space-y-1 max-h-40 overflow-y-auto">
                        {activity.length === 0 && (
                            <p className="text-xs text-aura-muted">Sin eventos</p>
                        )}
                        {activity.map((log, i) => (
                            <div
                                key={`${log.ts}-${i}`}
                                className="text-xs bg-aura-bg rounded px-2 py-1"
                            >
                                <span className="text-aura-cyan">[{log.level}]</span>{" "}
                                <span className="text-aura-muted">{log.message}</span>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Núcleo Evolutivo */}
                {neural && (
                    <div className="border-t border-white/5 pt-4">
                        <h3 className="text-xs font-semibold uppercase tracking-wider text-aura-muted mb-2">
                            🧠 Núcleo Evolutivo
                        </h3>
                        <div className="space-y-1 text-xs">
                            <p className="flex justify-between">
                                <span className="text-aura-muted">Estabilidad</span>
                                <span
                                    className={
                                        neural.last_tick.stability >= neural.neural.threshold
                                            ? "text-aura-green"
                                            : "text-red-400"
                                    }
                                >
                                    {(neural.last_tick.stability * 100).toFixed(1)}%
                                </span>
                            </p>
                            <p className="flex justify-between">
                                <span className="text-aura-muted">Iteraciones</span>
                                <span className="text-white">{neural.neural.iterations}</span>
                            </p>
                            <p className="flex justify-between">
                                <span className="text-aura-muted">Keep-alive</span>
                                <span className="text-white">{neural.neural.keep_alive_fired}</span>
                            </p>
                            <p className="flex justify-between">
                                <span className="text-aura-muted">Memoria</span>
                                <span className="text-white">
                                    {neural.sys_vitals.memory_percent.toFixed(0)}%
                                </span>
                            </p>
                            {neural.last_tick.real_inactivity && (
                                <p className="text-red-400 text-[10px]">
                                    ⚠️ Inactividad detectada → keep-alive
                                </p>
                            )}
                        </div>
                    </div>
                )}

                {/* Memoria Semántica (RAG) */}
                {memory && (
                    <div className="border-t border-white/5 pt-4">
                        <h3 className="text-xs font-semibold uppercase tracking-wider text-aura-muted mb-2">
                            🧠 Memoria Semántica
                        </h3>
                        <p className="text-xs text-aura-muted mb-2">
                            {memory.total} recuerdo(s) vectoriales
                        </p>
                        <div className="space-y-1 max-h-32 overflow-y-auto">
                            {memory.memories.length === 0 && (
                                <p className="text-xs text-aura-muted">Sin recuerdos aún</p>
                            )}
                            {memory.memories.map((m) => (
                                <div
                                    key={m.id}
                                    className="text-xs text-aura-muted bg-aura-bg rounded px-2 py-1 truncate"
                                    title={m.content}
                                >
                                    <span className="text-aura-purple">[{m.kind}]</span>{" "}
                                    {m.content}
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Knowledge Base toggle */}
                <div className="border-t border-white/5 pt-4">
                    <button
                        onClick={() => setShowKb(!showKb)}
                        className="w-full py-2 text-xs bg-aura-green/15 border border-aura-green/30 text-aura-green rounded-lg"
                    >
                        {showKb ? "▾ Ocultar KB" : "▸ Base de Conocimiento"}
                    </button>
                    {showKb && <KnowledgeBase />}
                </div>

                {/* Nueva Sesión */}
                <div>
                    <button
                        onClick={() => window.location.reload()}
                        className="w-full py-2 text-sm bg-aura-purple/20 border border-aura-purple/40 text-aura-purple rounded-lg hover:bg-aura-purple/30 transition"
                    >
                        + Nueva Sesión
                    </button>
                </div>
            </div>
        </aside>
    );
}
