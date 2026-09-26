"use client";
// BLOQUE 86 - Edge-AI Fine-Tune panel (100% local/offline).
import { useCallback, useEffect, useState } from "react";

async function jget(url: string) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error(`GET ${url} -> ${r.status}`);
  return r.json();
}

export default function EdgeFinetunePanel() {
  const [status, setStatus] = useState<any>(null);
  const [adapters, setAdapters] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setError(null);
      const [s, a] = await Promise.all([
        jget("/api/ai/finetune/status"),
        jget("/api/ai/finetune/adapters"),
      ]);
      setStatus(s);
      setAdapters(a.adapters ?? []);
    } catch (e: any) {
      setError(e?.message ?? "edge-ft offline");
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 8000);
    return () => clearInterval(id);
  }, [refresh]);

  return (
    <section aria-label="Edge fine-tune" data-offline-only="true">
      <h2>Edge Fine-Tune (local)</h2>
      {error && <p role="alert">offline: {error}</p>}
      <p>runs: {status?.runs ?? 0} · adapters: {adapters.length} · active: {status?.active_adapter ?? "none"}</p>
      <ul>
        {adapters.map((a: any) => (
          <li key={a.adapter_id}>{a.base_model} r={a.rank} loss={a.final_loss} active={String(a.active)}</li>
        ))}
      </ul>
    </section>
  );
}
