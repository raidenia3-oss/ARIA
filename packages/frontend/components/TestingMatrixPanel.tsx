"use client";
// BLOQUE 103 - Testing Matrix + Swarm Stress panel (100% local/offline).
import { useEffect, useState } from "react";

interface StepRow { step: string; ok: boolean; latency_ms: number; error: string }
interface MatrixReport {
  report_id: string; status: string; passed: number; failed: number;
  coverage_blocks: number; steps: StepRow[]; offline_only: boolean;
}
interface StressReport {
  report_id: string; status: string; agents: number; ops_per_agent: number;
  total_ops: number; ok_ops: number; failed_ops: number; deadlocks: number;
  avg_latency_ms: number; p95_latency_ms: number; throughput_ops: number;
  faults_injected: number; offline_only: boolean;
}

export default function TestingMatrixPanel() {
  const [matrix, setMatrix] = useState<MatrixReport | null>(null);
  const [stress, setStress] = useState<StressReport | null>(null);
  const [agents, setAgents] = useState(8);
  const [ops, setOps] = useState(10);
  const [faults, setFaults] = useState(false);
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<string[]>([]);
  const base = "";
  const push = (m: string) => setLog((l) => [...l, m].slice(-20));

  const refresh = async () => {
    try {
      const r = await fetch(`${base}/api/testing/matrix/status`);
      const j = await r.json();
      if (j.last_matrix) setMatrix(j.last_matrix);
      if (j.last_stress) setStress(j.last_stress);
    } catch { /* ignore */ }
  };

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, []);

  const runMatrix = async () => {
    setBusy(true);
    try {
      const r = await fetch(`${base}/api/testing/matrix/run`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const j = await r.json();
      setMatrix(j);
      push(`matrix -> ${j.status} ${j.passed}/${j.passed + j.failed}`);
    } catch (e) { push(`matrix error: ${String(e)}`); }
    setBusy(false);
  };

  const runStress = async () => {
    setBusy(true);
    try {
      const r = await fetch(`${base}/api/testing/matrix/stress`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agents, ops_per_agent: ops, inject_faults: faults }),
      });
      const j = await r.json();
      setStress(j);
      push(`stress -> ${j.status} ok=${j.ok_ops} fail=${j.failed_ops} deadlocks=${j.deadlocks}`);
    } catch (e) { push(`stress error: ${String(e)}`); }
    setBusy(false);
  };

  return (
    <div className="p-4 rounded-lg bg-black/40 border border-white/10 space-y-3 max-w-3xl">
      <h3 className="text-sm font-semibold text-white">Testing Matrix E2E + Swarm Stress (Bloque 103)</h3>
      <div className="flex flex-wrap gap-2 items-center text-xs">
        <button onClick={runMatrix} disabled={busy} className="px-3 py-1 rounded bg-emerald-600 text-white disabled:opacity-50">Run matrix</button>
        <button onClick={runStress} disabled={busy} className="px-3 py-1 rounded bg-sky-600 text-white disabled:opacity-50">Run stress</button>
        <label className="text-white/70">agents <input type="number" value={agents} min={1} max={64} onChange={(e) => setAgents(Number(e.target.value))} className="w-16 px-1 rounded bg-white/10 text-white" /></label>
        <label className="text-white/70">ops <input type="number" value={ops} min={1} max={50} onChange={(e) => setOps(Number(e.target.value))} className="w-16 px-1 rounded bg-white/10 text-white" /></label>
        <label className="text-white/70"><input type="checkbox" checked={faults} onChange={(e) => setFaults(e.target.checked)} /> faults</label>
        <span className="text-white/40">offline_only: true</span>
      </div>
      {matrix && (
        <div className="text-xs text-white/70">
          <div>matrix: <span className={matrix.status === "passed" ? "text-green-400" : "text-yellow-400"}>{matrix.status}</span> passed={matrix.passed} failed={matrix.failed} coverage={matrix.coverage_blocks}/102</div>
          <div className="mt-1 space-y-0.5 max-h-40 overflow-auto">
            {matrix.steps.map((s) => (
              <div key={s.step}>{s.ok ? "\u2705" : "\u274C"} {s.step} {s.latency_ms.toFixed(1)}ms {s.error}</div>
            ))}
          </div>
        </div>
      )}
      {stress && (
        <div className="text-xs text-white/70">
          <div>stress: <span className={stress.status === "passed" ? "text-green-400" : "text-yellow-400"}>{stress.status}</span> ok={stress.ok_ops} fail={stress.failed_ops} deadlocks={stress.deadlocks} avg={stress.avg_latency_ms.toFixed(1)}ms p95={stress.p95_latency_ms.toFixed(1)}ms tput={stress.throughput_ops.toFixed(1)}/s faults={stress.faults_injected}</div>
        </div>
      )}
      <div className="text-[11px] text-white/40 space-y-0.5">{log.map((l, i) => <div key={i}>{l}</div>)}</div>
    </div>
  );
}
