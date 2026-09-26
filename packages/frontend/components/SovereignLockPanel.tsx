"use client";
// BLOQUE 104 - Sovereign Lock + Smoke Hardshell panel (100% local/offline).
import { useEffect, useState } from "react";

interface LockStatus {
  status: string;
  locked_at: number;
  runtime_signature: string;
  env_local_sha256: string;
  sovereign_ready: boolean;
  offline_only: boolean;
  report: { status: string; modules_total: number; modules_ok: number; smoke_passed: boolean; e2e_passed: boolean; e2e_report_id: string } | null;
}
interface DaemonRow { name: string; alive: boolean; detail: string }
interface Audit { blocks_total: number; contracts_ok: number; contracts_total: number; checks: Record<string, boolean>; routes_total: number; sovereign_ready: boolean }

export default function SovereignLockPanel() {
  const [status, setStatus] = useState<LockStatus | null>(null);
  const [daemons, setDaemons] = useState<DaemonRow[]>([]);
  const [audit, setAudit] = useState<Audit | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const base = "";
  const push = (m: string) => setLog((l) => [...l, m].slice(-20));

  const refresh = async () => {
    try {
      setStatus(await (await fetch(`${base}/api/core/sovereign-lock/status`)).json());
      const d = await (await fetch(`${base}/api/core/sovereign-lock/daemons`)).json();
      setDaemons(d.daemons ?? []);
      setAudit(await (await fetch(`${base}/api/core/sovereign-lock/audit104`)).json());
    } catch { /* ignore */ }
  };

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, []);

  const lock = async () => {
    setBusy(true);
    try {
      const r = await fetch(`${base}/api/core/sovereign-lock/lock`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
      push(`lock -> ${JSON.stringify(await r.json()).slice(0, 160)}`);
    } catch (e) { push(`lock error: ${String(e)}`); }
    setBusy(false); refresh();
  };
  const unlock = async () => {
    setBusy(true);
    try {
      const r = await fetch(`${base}/api/core/sovereign-lock/unlock`, { method: "POST" });
      push(`unlock -> ${JSON.stringify(await r.json())}`);
    } catch (e) { push(`unlock error: ${String(e)}`); }
    setBusy(false); refresh();
  };
  const smoke = async () => {
    try {
      const r = await fetch(`${base}/api/core/sovereign-lock/smoke`);
      const j = await r.json();
      push(`smoke -> ${j.status} ports_ok=${j.ports_ok} modules_ok=${j.modules_ok} daemons_ok=${j.daemons_ok}`);
    } catch (e) { push(`smoke error: ${String(e)}`); }
  };

  const color = status?.status === "locked" ? "text-green-400" : "text-white/50";
  return (
    <div className="p-4 rounded-lg bg-black/40 border border-white/10 space-y-3 max-w-3xl">
      <h3 className="text-sm font-semibold text-white">Sovereign Lock-In + Smoke Hardshell (Bloque 104)</h3>
      {status && (
        <div className="text-xs text-white/70 space-y-1">
          <div>status: <span className={color}>{status.status}</span> sovereign_ready: {String(status.sovereign_ready)}</div>
          <div>runtime_sig: {status.runtime_signature} env_local: {status.env_local_sha256}</div>
          <div>offline_only: {String(status.offline_only)}</div>
        </div>
      )}
      {audit && <div className="text-xs text-white/70">audit104: blocks={audit.blocks_total} contracts={audit.contracts_ok}/{audit.contracts_total} routes={audit.routes_total} ready={String(audit.sovereign_ready)}</div>}
      {daemons.length > 0 && (
        <div className="text-xs text-white/70 space-y-0.5 max-h-32 overflow-auto">
          {daemons.map((d) => <div key={d.name}>{d.alive ? "\u2705" : "\u274C"} {d.name} {d.detail}</div>)}
        </div>
      )}
      <div className="flex gap-2 text-xs">
        <button onClick={smoke} className="px-3 py-1 rounded bg-sky-600 text-white">Smoke</button>
        <button onClick={lock} disabled={busy} className="px-3 py-1 rounded bg-emerald-600 text-white disabled:opacity-50">Lock</button>
        <button onClick={unlock} disabled={busy} className="px-3 py-1 rounded bg-zinc-600 text-white disabled:opacity-50">Unlock</button>
      </div>
      <div className="text-[11px] text-white/40 space-y-0.5">{log.map((l, i) => <div key={i}>{l}</div>)}</div>
    </div>
  );
}
