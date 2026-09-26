"use client";
// BLOQUE 88 - Cognitive graph panel (100% local/offline).
import { useCallback, useEffect, useState } from "react";

async function jget(url: string) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error(`GET ${url} -> ${r.status}`);
  return r.json();
}

export default function CognitiveGraphPanel() {
  const [status, setStatus] = useState<any>(null);
  const [clusters, setClusters] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setError(null);
      const [s, c] = await Promise.all([
        jget("/api/memory/cognitive/status"),
        jget("/api/memory/cognitive/clusters"),
      ]);
      setStatus(s);
      setClusters(c.clusters ?? []);
    } catch (e: any) {
      setError(e?.message ?? "cognitive offline");
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 8000);
    return () => clearInterval(id);
  }, [refresh]);

  return (
    <section aria-label="Cognitive graph" data-offline-only="true">
      <h2>Cognitive Graph (local)</h2>
      {error && <p role="alert">offline: {error}</p>}
      <p>nodes: {status?.nodes ?? 0} · clusters: {clusters.length}</p>
      <ul>
        {clusters.slice(0, 10).map((c: any, i: number) => (
          <li key={i}>[{c.size}] {(c.members ?? []).join(" · ")}</li>
        ))}
      </ul>
    </section>
  );
}
