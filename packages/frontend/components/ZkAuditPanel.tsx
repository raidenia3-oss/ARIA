/// BLOQUE 94 - Local Zero-Knowledge Proof & Sovereign Audit Trail panel.
/// Uses native fetch + WebSocket (no external client dependency).

import { useEffect, useState } from 'react';

interface ZKStatus {
  status: string;
  groups: number;
  proofs: number;
  audit: {
    status: string;
    entries: number;
    verified: boolean;
    tampered: boolean;
    last_sequence: number;
  };
  offline_only: boolean;
}

interface AuditEntry {
  entry_id: string;
  sequence: number;
  timestamp: number;
  event_type: string;
  actor: string;
  target: string;
  detail: Record<string, unknown>;
  prev_hash: string;
  entry_hash: string;
}

export default function ZkAuditPanel() {
  const [status, setStatus] = useState<ZKStatus | null>(null);
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [chain, setChain] = useState<{ verified: boolean; tampered: boolean; total_entries: number } | null>(null);
  const [statement, setStatement] = useState('has_role:admin');
  const [witness, setWitness] = useState('42');
  const [proof, setProof] = useState<Record<string, unknown> | null>(null);
  const [verifyResult, setVerifyResult] = useState<boolean | null>(null);

  const refresh = async () => {
    try {
      const r = await fetch('/api/security/zkp/status');
      setStatus(await r.json());
    } catch { /* offline */ }
  };

  const loadAudit = async () => {
    try {
      const r = await fetch('/api/security/zkp/audit/entries?limit=20');
      const data = await r.json();
      setEntries(data.entries || []);
    } catch { /* offline */ }
  };

  const checkChain = async () => {
    try {
      const r = await fetch('/api/security/zkp/audit/verify', { method: 'POST' });
      setChain(await r.json());
    } catch { /* offline */ }
  };

  const issueProof = async () => {
    try {
      const r = await fetch('/api/security/zkp/proofs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ statement, witness: Number(witness) || 0, prover_node: 'local' }),
      });
      const p = await r.json();
      setProof(p);
      const v = await fetch('/api/security/zkp/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ proof_id: p.proof_id }),
      });
      const vr = await v.json();
      setVerifyResult(vr.verified);
    } catch { /* offline */ }
  };

  useEffect(() => {
    refresh();
    loadAudit();
    checkChain();
    const ws = new WebSocket(
      (location.protocol === 'https:' ? 'wss' : 'ws') + '://' + location.host + '/api/security/zkp/ws'
    );
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === 'zk_proof_issued' || msg.type === 'zk_proof_verified') {
          refresh();
          loadAudit();
          checkChain();
        }
      } catch { /* ignore */ }
    };
    return () => ws.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="zk-audit-panel">
      <h3>Zero-Knowledge Proof &amp; Sovereign Audit Trail</h3>
      <p className="offline-badge">{status?.offline_only ? 'offline-only' : 'online'}</p>

      <div className="zk-status">
        <span>Groups: {status?.groups ?? '-'}</span>
        <span>Proofs: {status?.proofs ?? '-'}</span>
        <span>Audit entries: {status?.audit?.entries ?? '-'}</span>
        <span className={status?.audit?.tampered ? 'tampered' : 'ok'}>
          Chain: {status?.audit?.verified ? 'verified' : 'pending'}
        </span>
      </div>

      <div className="zk-prover">
        <input
          value={statement}
          onChange={(e) => setStatement(e.target.value)}
          placeholder="statement"
        />
        <input value={witness} onChange={(e) => setWitness(e.target.value)} placeholder="witness" />
        <button onClick={issueProof}>Issue ZKP</button>
      </div>

      {proof && (
        <div className="zk-proof">
          <strong>Proof:</strong> {String(proof.proof_id)} — statement: {String(proof.statement)}
          <br />
          commitment: {String(proof.commitment_b64).slice(0, 16)}…
          <br />
          <strong>Verified:</strong> {verifyResult === null ? 'pending' : verifyResult ? 'true' : 'false'}
        </div>
      )}

      <div className="zk-chain">
        <button onClick={checkChain}>Verify chain</button>
        {chain && (
          <span className={chain.verified ? 'ok' : 'tampered'}>
            {chain.verified ? 'Chain valid' : 'TAMPERED'} ({chain.total_entries} entries)
          </span>
        )}
      </div>

      <table className="zk-audit-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Type</th>
            <th>Actor</th>
            <th>Time</th>
            <th>Hash</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => (
            <tr key={e.entry_id}>
              <td>{e.sequence}</td>
              <td>{e.event_type}</td>
              <td>{e.actor}</td>
              <td>{new Date(e.timestamp * 1000).toLocaleString()}</td>
              <td className="hash">{e.entry_hash.slice(0, 12)}…</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}