"use client";
// BLOQUE 98 - Sovereign Boot panel (100% local/offline).
import { useEffect, useState } from "react";

interface Status {
  booted: boolean;
  boot_ts: number;
  offline_only: boolean;
  hardening: {
    level: number;
    checks_total: number;
    checks_passed: number;
    secrets_exposed: number;
    plaintext_tokens: number;
    cloud_endpoints: number;
  };
  health: {
    blocks_total: number;
    blocks_ok: number;
    blocks_failed: number;
    critical_failures: number;
    ready: boolean;
  };
}

export default function SovereignBootPanel() {
  const [status, setStatus] = useState<Status | null>(null);
  const [level, setLevel] = useState("strict");
  const [log, setLog] = useState<string[]>([]);

  const base = "";

  const refresh = async () => {
    try {
      const r = await fetch(`${base}/api/core/sovereign-boot/status`);
      setStatus(await r.json());
    } catch { /* ignore */ }
  };

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, []);

  const boot = async () => {
    const r = await fetch(`${base}/api/core/sovereign-boot/boot`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ force: true }),
    });
    const d = await r.json();
    setLog((l) => [...l, `boot -> ${JSON.stringify(d)}`].slice(-20));
    refresh();
  };

  const harden = async () => {
    const r = await fetch(`${base}/api/core/sovereign-boot/hardening`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ level }),
    });
    const d = await r.json();
    setLog((l) => [...l, `harden -> ${JSON.stringify(d)}`].slice(-20));
    refresh();
  };

  return (
    <div className="p-4 rounded-lg bg-black/40 border border-white/10 space-y-3 max-w-md">
      <h3 className="text-sm font-semibold text-white">Sovereign Boot</h3>
      {status && (
        <div className="text-xs text-white/70 space-y-1">
          <div>booted: {String(status.booted)}</div>
          <div>blocks: {status.health.blocks_ok}/{status.health.blocks_total}</div>
          <div>critical_failures: {status.health.critical_failures}</div>
          <div>ready: {String(status.health.ready)}</div>
          <div>hardening level: {status.hardening.level}</div>
          <div>checks: {status.hardening.checks_passed}/{status.hardening.checks_total}</div>
          <div>secrets_exposed: {status.hardening.secrets_exposed}</div>
        </div>
      )}
      <div className="flex gap-2">
        <button onClick={boot}
          className="text-xs bg-green-600 hover:bg-green-500 text-white px-2 py-1 rounded">
          Boot
        </button>
        <select value={level} onChange={(e) => setLevel(e.target.value)}
          className="bg-white/10 text-white text-xs rounded px-2 py-1">
          <option value="off">off</option>
          <option value="standard">standard</option>
          <option value="strict">strict</option>
          <option value="paranoid">paranoid</option>
        </select>
        <button onClick={harden}
          className="text-xs bg-blue-600 hover:bg-blue-500 text-white px-2 py-1 rounded">
          Harden
        </button>
      </div>
      <div className="text-[10px] text-white/40 max-h-24 overflow-auto">
        {log.map((l, i) => <div key={i}>{l}</div>)}
      </div>
    </div>
  );
}