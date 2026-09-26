"use client";
// BLOQUE 90 - Sovereign Identity & Zero-Trust Auth panel (100% local/offline).
// Solo consume /api/security/identity (REST) y su WS. Sin dependencias cloud.
import { useCallback, useEffect, useState } from "react";

type Node = {
  node_id: string;
  label: string;
  role: string;
  pubkey_b64: string;
  created_at: number;
  last_seen: number;
  trust_score: number;
  offline_only: boolean;
};

type Cert = {
  cert_id: string;
  signing_node: string;
  subject_node: string;
  issued_at: number;
  expires_at: number;
  role: string;
  rotation_count: number;
  serial: string;
  offline_only: boolean;
};

type SignedP = {
  payload_id: string;
  sender: string;
  payload: Record<string, any>;
  signature_base64: string;
  created_at: number;
  verified: boolean;
  offline_only: boolean;
};

type Status = { nodes: number; certs: number; ephemeral: number; offline_only: boolean; algorithm: string };

async function jget(url: string) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error(`GET ${url} -> ${r.status}`);
  return r.json();
}

async function jpost(url: string, body: any) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`POST ${url} -> ${r.status}`);
  return r.json();
}

export default function IdentityZeroTrustPanel() {
  const [status, setStatus] = useState<Status | null>(null);
  const [nodes, setNodes] = useState<Node[]>([]);
  const [certs, setCerts] = useState<Cert[]>([]);
  const [lastSign, setLastSign] = useState<SignedP | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [registerLabel, setRegisterLabel] = useState("");
  const [signPayload, setSignPayload] = useState(JSON.stringify({ task: "ping", seq: 1 }, null, 2));

  const refresh = useCallback(async () => {
    try {
      setError(null);
      const [s, n, c] = await Promise.all([
        jget("/api/security/identity/status"),
        jget("/api/security/identity/nodes?limit=20"),
        jget("/api/security/identity/certs?limit=20"),
      ]);
      setStatus(s);
      setNodes((n as any).nodes ?? []);
      setCerts((c as any).certs ?? []);
    } catch (e: any) {
      setError(e?.message ?? "identity offline");
    }
  }, []);

  const registerNode = useCallback(async () => {
    if (!registerLabel.trim()) return;
    try {
      setError(null);
      await jpost("/api/security/identity/register", { label: registerLabel, role: "peer" });
      setRegisterLabel("");
      refresh();
    } catch (e: any) {
      setError(e?.message ?? "register failed");
    }
  }, [registerLabel, refresh]);

  const doSign = useCallback(async () => {
    let payload: any;
    try { payload = JSON.parse(signPayload); } catch { payload = { task: "ping" }; }
    try {
      const firstNode = nodes[0];
      if (!firstNode) { setError("no registered nodes to sign with"); return; }
      const signed = await jpost("/api/security/identity/sign", {
        node_id: firstNode.node_id,
        payload,
      });
      setLastSign(signed);
    } catch (e: any) {
      setError(e?.message ?? "sign failed");
    }
  }, [nodes, signPayload]);

  const doVerify = useCallback(async () => {
    if (!lastSign) return;
    try {
      const ok = await jpost("/api/security/identity/verify", lastSign);
      setLastSign((prev) => (prev ? { ...prev, verified: ok.verified } : null));
    } catch (e: any) {
      setError(e?.message ?? "verify failed");
    }
  }, [lastSign]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 8000);
    return () => clearInterval(id);
  }, [refresh]);

  return (
    <section aria-label="Sovereign identity & zero-trust" data-offline-only="true">
      <h2>Sovereign Identity (local)</h2>
      {error && <p role="alert">offline: {error}</p>}
      <p>
        nodes: {status?.nodes ?? 0} · certs: {status?.certs ?? 0} · ephemeral: {status?.ephemeral ?? 0} · algo: {status?.algorithm}
      </p>

      <h3>Register node</h3>
      <input
        value={registerLabel}
        onChange={(e) => setRegisterLabel(e.target.value)}
        placeholder="node label"
        aria-label="node label"
      />
      <button onClick={registerNode}>register</button>

      <h3>Nodes ({nodes.length})</h3>
      <ul>
        {nodes.map((n) => (
          <li key={n.node_id}>
            {n.label || n.node_id} — {n.role} · trust={n.trust_score} · {n.pubkey_b64.slice(0, 12)}…
          </li>
        ))}
      </ul>

      <h3>Certs ({certs.length})</h3>
      <ul>
        {certs.map((c) => (
          <li key={c.cert_id}>
            {c.subject_node} ← {c.signing_node} [{c.role}] expired={c.expires_at < Date.now() ? "YES" : "no"}
          </li>
        ))}
      </ul>

      <h3>Sign / Verify (zero-trust roundtrip)</h3>
      <textarea
        value={signPayload}
        onChange={(e) => setSignPayload(e.target.value)}
        rows={3}
        aria-label="payload to sign"
      />
      <button onClick={doSign}>sign</button>
      {lastSign && (
        <>
          <p>
            signed: {lastSign.payload_id} · sender: {lastSign.sender} · verified: {String(lastSign.verified)}
          </p>
          <button onClick={doVerify}>verify</button>
        </>
      )}
    </section>
  );
}
