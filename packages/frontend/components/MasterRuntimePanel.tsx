"use client";
// BLOQUE 100 - Master Super-Agent Runtime panel (100% local/offline).
import { useEffect, useState } from "react";

interface MasterStatus {
  state: string;
  session_id: string | null;
  started_at: string | null;
  heartbeat_count: number;
  total_blocks: number;
  engines_registered: number;
  offline_only: boolean;
}

interface EcoReport {
  engines: { engine: string; ok: boolean; error?: string }[];
  engines_total: number;
  engines_ok: number;
  total_blocks: number;
  offline_only: boolean;
}

export default function MasterRuntimePanel() {
  const [status, setStatus] = useState<MasterStatus | null>(null);
  const [eco, setEco] = useState<EcoReport | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const base = "";

  const refresh = async () => {
    try {
      setStatus(await (await fetch(`${base}/api/aura/master/status`)).json());
    } catch { /* ignore */ }
  };

  const probe = async () => {
    try {
      const r = await fetch(`${base}/api/aura/master/ecosystem`);
      setEco(await r.json());
    } catch { /* ignore */ }
  };

  useEffect(() => {
    refresh();
    probe();
    const id = setInterval(() => { refresh(); probe(); }, 5000);
    return () => clearInterval(id);
  }, []);

  const launch = async () => {
    const d = await (await fetch(`${base}/api/aura/master/launch`, { method: "POST" })).json();
    setLog((l) => [...l, `launch -> ${JSON.stringify(d)}`].slice(-20));
    refresh();
  };
  const shutdown = async () => {
    const d = await (await fetch(`${base}/api/aura/master/shutdown`, { method: "POST" })).json();
    setLog((l) => [...l, `shutdown -> ${JSON.stringify(d)}`].slice(-20));
    refresh();
  };
  const reset = async () => {
    await fetch(`${base}/api/aura/master/reset`, { method: "POST" });
    setLog((l) => [...l, "reset -> ok"].slice(-20));
    refresh();
  };

  const color = (s: string) =>
    s === "ready" ? "text-green-400" : s === "degraded" ? "text-yellow-400" : "text-white/50";

  return (
    <div className="p-4 rounded-lg bg-black/40 border border-white/10 space-y-3 max-w-2xl">
      <h3 className="text-sm font-semibold text-white">Master Super-Agent Runtime</h3>
      {status && (
        <div className="text-xs text-white/70 space-y-1">
          <div>state: <span className={color(status.state)}>{status.state}</span></div>
          <div>session: {status.session_id ?? "—"}</div>
          <div>started: {status.started_at ?? "—"}</div>
          <div>heartbeat: {status.heartbeat_count}</div>
          <div>blocks: {status.total_blocks} engines: {status.engines_registered}</div>
          <div>offline_only: {String(status.offline_only)}</div>
        </div>
      )}
      {eco && (
        <div className="text-xs text-white/70 space-y-1">
          <div>engines: {eco.engines_ok}/{eco.engines_total}</div>
          <div className="max-h-24 overflow-auto text-[10px] text-white/40">
            {eco.engines.map((e, i) => <div key={i}>{e.engine}: {e.ok ? "ok" : "FAIL" + (e.error ? " " + e.error : "")}</div>)}
          </div>
        </div>
      )}
      <div className="flex gap-2">
        <button onClick={launch}
          className="text-xs bg-green-600 hover:bg-green-500 text-white px-2 py-1 rounded">Launch</button>
        <button onClick={shutdown}
          className="text-xs bg-orange-600 hover:bg-orange-500 text-white px-2 py-1 rounded">Shutdown</button>
        <button onClick={reset}
          className="text-xs bg-red-600 hover:bg-red-500 text-white px-2 py-1 rounded">Reset</button>
      </div>
      <div className="text-[10px] text-white/40 max-h-24 overflow-auto">
        {log.map((l, i) => <div key={i}>{l}</div>)}
      </div>
    </div>
  );
}