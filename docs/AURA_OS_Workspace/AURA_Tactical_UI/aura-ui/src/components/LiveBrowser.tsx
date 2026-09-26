import { useEffect, useRef, useState } from "react";

function backendWsUrl(): string {
    const fromEnv = (import.meta as any).env?.NEXT_PUBLIC_BACKEND_URL;
    let base = "";
    if (fromEnv && typeof fromEnv === "string" && fromEnv.trim()) {
        base = fromEnv.replace(/\/+$/, "");
    } else if (typeof window !== "undefined" && window.location.hostname !== "localhost") {
        base = `${window.location.protocol}//${window.location.host}`;
    } else {
        base = "http://localhost:8000";
    }
    return base.replace(/^http/, "ws") + "/ws/bridge";
}

export default function LiveBrowser() {
    const [connected, setConnected] = useState(false);
    const [log, setLog] = useState<string[]>([]);
    const wsRef = useRef<WebSocket | null>(null);

    const connect = () => {
        try {
            const ws = new WebSocket(backendWsUrl());
            wsRef.current = ws;
            ws.onopen = () => {
                setConnected(true);
                setLog((l) => [...l, "🔗 Conectado al puente AURA (ws/bridge)"]);
            };
            ws.onmessage = (e) => {
                try {
                    const data = JSON.parse(e.data);
                    const text =
                        data.type === "chat"
                            ? `AURA: ${data.reply ?? ""}`
                            : JSON.stringify(data);
                    setLog((l) => [...l.slice(-8), text]);
                } catch {
                    setLog((l) => [...l.slice(-8), e.data]);
                }
            };
            ws.onclose = () => {
                setConnected(false);
                setLog((l) => [...l, "🔴 Desconectado"]);
            };
            ws.onerror = () => setConnected(false);
        } catch {
            setConnected(false);
        }
    };

    useEffect(() => {
        connect();
        return () => wsRef.current?.close();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    return (
        <div className="live-browser">
            <div className="live-browser-header">
                <span className="live-browser-title">Live Bridge</span>
                <span className="live-browser-status" aria-label="Estado del stream">
                    {connected ? "🟢 conectado" : "desconectado"}
                </span>
            </div>
            <div className="live-browser-viewport">
                {log.length === 0 ? (
                    <div className="live-browser-placeholder">Iniciando puente con AURA...</div>
                ) : (
                    <div className="w-full space-y-1 text-xs text-aura-muted">
                        {log.map((line, i) => (
                            <div key={i} className="bg-aura-bg rounded px-2 py-1 break-words">
                                {line}
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
