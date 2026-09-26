"use client";
// BLOQUE 89 - Swarm consensus panel (100% local/offline).
import { useCallback, useEffect, useState } from "react";

async function jget(url: string) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error(`GET ${url} -> ${r.status}`);
  return r.json();
}

export default function SwarmConsensusPanel() {
  const [status, setStatus] = useState<any>(null);
  const [rounds, setRounds] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setError(null);
      const [s, r] = await Promise.all([
        jget("/api/mesh/consensus/status"),
        jget("/api/mesh/consensus/rounds?limit=10"),
      ]);
      setStatus(s);
      setRounds(r.rounds ?? []);
    } catch (e: any) {
      setError(e?.message ?? "consensus offline");
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 8000);
    return () => clearInterval(id);
  }, [refresh]);

  return (
    <section aria-label="Swarm consensus" data-offline-only="true">
      <h2>Swarm Consensus (local)</h2>
      {error && <p role="alert">offline: {error}</p>}
      <p>rounds: {status?.rounds ?? 0} · tasks: {status?.tasks ?? 0}</p>
      <ul>
        {rounds.map((r: any) => (
          <li key={r.round_id}>{r.topic}: {r.proposal} [{r.status}/{r.result}]</li>
        ))}
      </ul>
    </section>
  );
}
