"use client";
// BLOQUE 87 - Threat defense panel (100% local/offline).
import { useCallback, useEffect, useState } from "react";

async function jget(url: string) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error(`GET ${url} -> ${r.status}`);
  return r.json();
}

export default function ThreatDefensePanel() {
  const [status, setStatus] = useState<any>(null);
  const [quar, setQuar] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setError(null);
      const [s, q] = await Promise.all([
        jget("/api/security/defense/status"),
        jget("/api/security/defense/quarantine"),
      ]);
      setStatus(s);
      setQuar(q.items ?? []);
    } catch (e: any) {
      setError(e?.message ?? "defense offline");
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 8000);
    return () => clearInterval(id);
  }, [refresh]);

  return (
    <section aria-label="Threat defense" data-offline-only="true">
      <h2>Threat Defense (local)</h2>
      {error && <p role="alert">offline: {error}</p>}
      <p>events: {status?.events?.events ?? 0} · quarantined: {quar.length}</p>
      <ul>
        {quar.map((q: any) => (
          <li key={q.quarantine_id}>{q.target} — {q.reason} [{q.status}]</li>
        ))}
      </ul>
    </section>
  );
}
