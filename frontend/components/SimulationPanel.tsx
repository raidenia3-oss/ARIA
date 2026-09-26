"use client";
// BLOQUE 99 - Simulation / stress / infinite-horizon panel (100% local/offline).
import { useEffect, useState } from "react";

interface SimStatus {
  scenarios_run: number;
  offline_only: boolean;
  optimizer: { policy: number; converged: boolean; history_len: number };
}

interface SimResult {
  scenario_id: string;
  config: { name: string; agents: number; steps: number };
  consensus_accuracy: number;
  recovery_time_ms: number;
  throughput: number;
  resilience: number;
  faults_injected: number;
  recovered: number;
  status: string;
}

interface StressReport {
  scenarios: SimResult[];
  worst_resilience: number;
  fault_types: string[];
}

interface OptReport {
  converged: boolean;
  policy: number;
  iterations: number;
  history: { iteration: number; policy: number; discounted_return: number; delta: number | null }[];
}

export default function SimulationPanel() {
  const [status, setStatus] = useState<SimStatus | null>(null);
  const [results, setResults] = useState<SimResult[]>([]);
  const [agents, setAgents] = useState(8);
  const [steps, setSteps] = useState(100);
  const [seed, setSeed] = useState(42);
  const [log, setLog] = useState<string[]>([]);
  const [opt, setOpt] = useState<OptReport | null>(null);
  const base = "";

  const refresh = async () => {
    try {
      const r = await fetch(`${base}/api/simulation/infinite/status`);
      setStatus(await r.json());
      const res = await fetch(`${base}/api/simulation/infinite/results`);
      setResults((await res.json()).results ?? []);
    } catch { /* ignore */ }
  };

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, []);

  const runScenario = async () => {
    const r = await fetch(`${base}/api/simulation/infinite/scenario`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "manual", agents, steps, seed }),
    });
    const d = await r.json();
    setLog((l) => [...l, `scenario -> ${JSON.stringify(d)}`].slice(-20));
    refresh();
  };

  const runStress = async () => {
    const r = await fetch(`${base}/api/simulation/infinite/stress`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agents, seed }),
    });
    const d: StressReport = await r.json();
    setLog((l) => [...l, `stress -> worst_resilience=${d.worst_resilience}`].slice(-20));
    refresh();
  };

  const runOptimize = async () => {
    const r = await fetch(`${base}/api/simulation/infinite/optimize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ iterations: 50 }),
    });
    const d: OptReport = await r.json();
    setOpt(d);
    setLog((l) => [...l, `optimize -> converged=${d.converged} policy=${d.policy}`].slice(-20));
  };

  const reset = async () => {
    await fetch(`${base}/api/simulation/infinite/reset`, { method: "POST" });
    setOpt(null);
    setLog((l) => [...l, "reset -> ok"].slice(-20));
    refresh();
  };

  return (
    <div className="p-4 rounded-lg bg-black/40 border border-white/10 space-y-3 max-w-2xl">
      <h3 className="text-sm font-semibold text-white">Simulation &amp; Stress Engine</h3>
      {status && (
        <div className="text-xs text-white/70 space-y-1">
          <div>scenarios_run: {status.scenarios_run}</div>
          <div>optimizer policy: {status.optimizer.policy} converged: {String(status.optimizer.converged)}</div>
          <div>offline_only: {String(status.offline_only)}</div>
        </div>
      )}
      <div className="flex flex-wrap gap-2 items-center text-xs">
        <input className="bg-white/10 text-white rounded px-2 py-1 w-16" type="number"
          value={agents} onChange={(e) => setAgents(Number(e.target.value) || 1)} placeholder="agents" />
        <input className="bg-white/10 text-white rounded px-2 py-1 w-16" type="number"
          value={steps} onChange={(e) => setSteps(Number(e.target.value) || 1)} placeholder="steps" />
        <input className="bg-white/10 text-white rounded px-2 py-1 w-16" type="number"
          value={seed} onChange={(e) => setSeed(Number(e.target.value) || 0)} placeholder="seed" />
        <button onClick={runScenario}
          className="bg-green-600 hover:bg-green-500 text-white px-2 py-1 rounded">Scenario</button>
        <button onClick={runStress}
          className="bg-orange-600 hover:bg-orange-500 text-white px-2 py-1 rounded">Stress</button>
        <button onClick={runOptimize}
          className="bg-blue-600 hover:bg-blue-500 text-white px-2 py-1 rounded">Optimize</button>
        <button onClick={reset}
          className="bg-red-600 hover:bg-red-500 text-white px-2 py-1 rounded">Reset</button>
      </div>
      {opt && (
        <div className="text-xs text-white/70 space-y-1">
          <div>converged: {String(opt.converged)} policy: {opt.policy} iters: {opt.iterations}</div>
          <div className="max-h-24 overflow-auto text-[10px] text-white/40">
            {opt.history.slice(-10).map((h, i) => <div key={i}>it{h.iteration} p={h.policy} ret={h.discounted_return} d={h.delta}</div>)}
          </div>
        </div>
      )}
      <div className="text-[10px] text-white/40 max-h-24 overflow-auto">
        {results.map((r, i) => <div key={i}>{r.scenario_id} {r.config.name} res={r.resilience} cons={r.consensus_accuracy}</div>)}
      </div>
      <div className="text-[10px] text-white/40 max-h-24 overflow-auto">
        {log.map((l, i) => <div key={i}>{l}</div>)}
      </div>
    </div>
  );
}