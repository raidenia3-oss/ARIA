"use client";
// BLOQUE 85 - Recovery & Snapshot panel (100% local/offline).
// Solo consume /api/recovery (REST). Sin dependencias de backup cloud.
import { useCallback, useEffect, useState } from "react";

type Snap = { snapshot_id: string; label: string; kind: string; files: number; size_bytes: number; verified: boolean };

async function jget(url: string) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error(`GET ${url} -> ${r.status}`);
  return r.json();
}

export default function RecoverySnapshotPanel() {
  const [snaps, setSnaps] = useState<Snap[]>([]);
  const [recoveries, setRecoveries] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setError(null);
      const [l, r] = await Promise.all([jget("/api/recovery/snapshots"), jget("/api/recovery/recoveries")]);
      setSnaps(l.snapshots ?? []);
      setRecoveries(r.count ?? 0);
    } catch (e: any) {
      setError(e?.message ?? "recovery offline");
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 8000);
    return () => clearInterval(id);
  }, [refresh]);

  return (
    <section aria-label="Recovery snapshots" data-offline-only="true">
      <h2>Recovery Snapshots (local)</h2>
      {error && <p role="alert">offline: {error}</p>}
      <p>snapshots: {snaps.length} · recoveries: {recoveries}</p>
      <ul>
        {snaps.map((s) => (
          <li key={s.snapshot_id}>{s.label || s.snapshot_id} [{s.kind}] {s.files} files · {s.size_bytes}B · verified={String(s.verified)}</li>
        ))}
      </ul>
    </section>
  );
}
