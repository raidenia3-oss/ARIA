"use client";
// BLOQUE 84 - Predictive Intent & Proactive Scheduler panel (100% local/offline).
// Solo consume /api/scheduler/predictive (REST) y su WS. Sin telemetria cloud.
import { useCallback, useEffect, useState } from "react";

type Hypothesis = { hypothesis_id: string; intent: string; confidence: number; impact: string; suggested_action: string };
type Task = { task_id: string; action: string; impact: string; status: string };

async function jget(url: string) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error(`GET ${url} -> ${r.status}`);
  return r.json();
}

export default function PredictiveSchedulerPanel() {
  const [status, setStatus] = useState<any>(null);
  const [hyps, setHyps] = useState<Hypothesis[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setError(null);
      const [s, h, t] = await Promise.all([
        jget("/api/scheduler/predictive/status"),
        jget("/api/scheduler/predictive/hypotheses?limit=20"),
        jget("/api/scheduler/predictive/tasks?limit=20"),
      ]);
      setStatus(s);
      setHyps(h.hypotheses ?? []);
      setTasks(t.tasks ?? []);
    } catch (e: any) {
      setError(e?.message ?? "predictive offline");
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, [refresh]);

  return (
    <section aria-label="Predictive intent scheduler" data-offline-only="true">
      <h2>Predictive Intent (local)</h2>
      {error && <p role="alert">offline: {error}</p>}
      <p>hypotheses: {hyps.length} · tasks: {tasks.length} · offline_only: {String(status?.offline_only ?? true)}</p>
      <ul>
        {hyps.map((h) => (
          <li key={h.hypothesis_id}>{h.intent} ({h.confidence}) [{h.impact}] → {h.suggested_action}</li>
        ))}
      </ul>
      <ul>
        {tasks.map((t) => (
          <li key={t.task_id}>{t.action} [{t.impact}] — {t.status}</li>
        ))}
      </ul>
    </section>
  );
}
