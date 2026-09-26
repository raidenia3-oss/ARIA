"use client";
// BLOQUE 96 - Resilience & Self-Healing panel (100% local/offline).
// Consumes /api/resilience/healing REST + WebSocket. No cloud dependencies.
import { useEffect, useState } from "react";

interface Status {
  auto_heal: boolean;
  faults_total: number;
  actions_total: number;
  last_scan_ts: number;
  memory_mb: number;
  cpu_percent: number;
  thread_count: number;
  platform: string;
  offline_only: boolean;
}

interface Fault {
  event_id: string;
  kind: string;
  severity: string;
  detail: string;
  memory_mb: number;
  cpu_percent: number;
  thread_count: number;
  timestamp: number;
  iso: string;
}

interface Action {
  action_id: string;
  fault_id: string;
  action: string;
  status: string;
  detail: string;
  timestamp: number;
  iso: string;
}

export default function SelfHealingPanel() {
  const [status, setStatus] = useState<Status | null>(null);
  const [faults, setFaults] = useState<Fault[]>([]);
  const [actions, setActions] = useState<Action[]>([]);
  const [faultKind, setFaultKind] = useState("memory_pressure");
  const [faultDetail, setFaultDetail] = useState("");
  const [remediateAction, setRemediateAction] = useState("gc_collect");
  const [lastEvent, setLastEvent] = useState("");

  const refresh = async () => {
    try {
      const r = await fetch("/api/resilience/healing/status", { cache: "no-store" });
      setStatus(await r.json());
    } catch { /* offline */ }
  };

  const loadFaults = async () => {
    try {
      const r = await fetch("/api/resilience/healing/faults?limit=20", { cache: "no-store" });
      const data = await r.json();
      setFaults(data.faults || []);
    } catch { /* offline */ }
  };

  const loadActions = async () => {
    try {
      const r = await fetch("/api/resilience/healing/actions?limit=20", { cache: "no-store" });
      const data = await r.json();
      setActions(data.actions || []);
    } catch { /* offline */ }
  };

  const injectFault = async () => {
    try {
      const r = await fetch("/api/resilience/healing/faults/inject", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind: faultKind, detail: faultDetail, severity: "warning" }),
      });
      setLastEvent(JSON.stringify(await r.json(), null, 2));
      loadFaults();
      loadActions();
    } catch { /* offline */ }
  };

  const doRemediate = async () => {
    try {
      const r = await fetch("/api/resilience/healing/remediate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: remediateAction, detail: "manual" }),
      });
      setLastEvent(JSON.stringify(await r.json(), null, 2));
      loadActions();
    } catch { /* offline */ }
  };

  useEffect(() => {
    refresh();
    loadFaults();
    loadActions();
    const ws = new WebSocket(
      (location.protocol === "https:" ? "wss" : "ws") + "://" + location.host + "/api/resilience/healing/ws"
    );
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.event === "heartbeat") {
          setStatus(msg.status);
        } else if (msg.type === "fault_detected") {
          setLastEvent(JSON.stringify(msg, null, 2));
          loadFaults();
        } else if (msg.type === "remediation_applied") {
          setLastEvent(JSON.stringify(msg, null, 2));
          loadActions();
        }
      } catch { /* ignore */ }
    };
    const id = setInterval(refresh, 5000);
    return () => { clearInterval(id); ws.close(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <section aria-label="Self-healing" data-offline-only="true">
      <h2>Resilience &amp; Self-Healing</h2>
      <p className="offline-badge">{status?.offline_only ? "offline-only" : "online"}</p>

      <div className="healing-status">
        <span>Auto-heal: {status?.auto_heal ? "on" : "off"}</span>
        <span>Faults: {status?.faults_total ?? 0}</span>
        <span>Actions: {status?.actions_total ?? 0}</span>
        <span>Mem: {status?.memory_mb ?? 0}MB</span>
        <span>CPU: {status?.cpu_percent ?? 0}%</span>
        <span>Threads: {status?.thread_count ?? 0}</span>
        <span>Platform: {status?.platform ?? "-"}</span>
      </div>

      <div className="healing-controls">
        <button onClick={refresh}>Refresh</button>
        <button onClick={() => { setLastEvent(JSON.stringify(status, null, 2)); }}>Status JSON</button>
      </div>

      <div className="fault-inject">
        <h3>Inject Fault</h3>
        <input value={faultKind} onChange={(e) => setFaultKind(e.target.value)} placeholder="kind" />
        <input value={faultDetail} onChange={(e) => setFaultDetail(e.target.value)} placeholder="detail" />
        <button onClick={injectFault}>Inject</button>
      </div>

      <div className="remediate">
        <h3>Force Remediation</h3>
        <input value={remediateAction} onChange={(e) => setRemediateAction(e.target.value)} placeholder="action" />
        <button onClick={doRemediate}>Remediate</button>
      </div>

      <div className="faults-list">
        <h3>Faults ({faults.length})</h3>
        <table>
          <thead>
            <tr><th>ID</th><th>Kind</th><th>Severity</th><th>Detail</th><th>Time</th></tr>
          </thead>
          <tbody>
            {faults.map((f) => (
              <tr key={f.event_id}>
                <td>{f.event_id}</td>
                <td>{f.kind}</td>
                <td className={f.severity}>{f.severity}</td>
                <td>{f.detail}</td>
                <td>{new Date(f.timestamp * 1000).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="actions-list">
        <h3>Actions ({actions.length})</h3>
        <table>
          <thead>
            <tr><th>ID</th><th>Fault</th><th>Action</th><th>Status</th><th>Detail</th><th>Time</th></tr>
          </thead>
          <tbody>
            {actions.map((a) => (
              <tr key={a.action_id}>
                <td>{a.action_id}</td>
                <td>{a.fault_id}</td>
                <td>{a.action}</td>
                <td>{a.status}</td>
                <td>{a.detail}</td>
                <td>{new Date(a.timestamp * 1000).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {lastEvent && <pre className="healing-log">{lastEvent}</pre>}
    </section>
  );
}