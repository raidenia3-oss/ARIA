import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { getActivity, type ActivityLog } from "../services/api";

export default function KnowledgeBase() {
    const [logs, setLogs] = useState<ActivityLog[] | null>(null);
    const [loading, setLoading] = useState(false);

    const fetchActivity = async () => {
        setLoading(true);
        try {
            const data = await getActivity(10);
            setLogs(data);
        } catch {
            setLogs([]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchActivity();
    }, []);

    return (
        <div className="px-4 py-3 space-y-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-aura-green mb-1">
                🧠 Base de Conocimiento
            </h3>

            <button
                onClick={fetchActivity}
                disabled={loading}
                className="w-full py-2 text-xs bg-aura-green/20 border border-aura-green/40 text-aura-green rounded-lg disabled:opacity-40 transition hover:bg-aura-green/30"
            >
                {loading ? "Sincronizando..." : "🔄 Sincronizar con AURA"}
            </button>

            <div className="space-y-1 max-h-48 overflow-y-auto">
                {logs === null && (
                    <p className="text-xs text-aura-muted">Cargando memoria de AURA...</p>
                )}
                {logs !== null && logs.length === 0 && (
                    <p className="text-xs text-aura-muted">Sin eventos registrados.</p>
                )}
                {logs?.map((log, i) => (
                    <div key={`${log.ts}-${i}`} className="text-xs bg-aura-bg rounded px-2 py-1 border border-white/5">
                        <span className="text-aura-cyan">[{log.level}]</span>{" "}
                        <span className="text-aura-muted break-words">{log.message}</span>
                    </div>
                ))}
            </div>

            <AnimatePresence>
                {logs !== null && (
                    <motion.p
                        initial={{ opacity: 0, y: -8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0 }}
                        className="text-xs text-aura-muted"
                    >
                        {logs.length} evento(s) en la memoria de producción.
                    </motion.p>
                )}
            </AnimatePresence>
        </div>
    );
}
