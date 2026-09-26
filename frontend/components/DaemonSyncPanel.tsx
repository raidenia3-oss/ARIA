"use client";
// BLOQUE 95 - Cross-Device Sync & Daemon Orchestration panel (100% local/offline).
// Consumes /api/daemon/sync REST + WebSocket. No cloud dependencies.
import { useEffect, useState } from "react";

interface SyncStatus {
  sync: {
    local_node_id: string;
    peers_count: number;
    snapshots_count: number;
    events_count: number;
    platform: string;
    offline_only: boolean;
  };
  daemon: {
    running: boolean;
    uptime_seconds: number;
    restart_count: number;
    auto_restart: boolean;
    max_restarts: number;
    last_error: string;
    platform: string;
    offline_only: boolean;
  };
  health: {
    healthy: boolean;
    uptime_seconds: number;
    restarts: number;
    last_error: string;
    memory_mb: number;
    cpu_percent: number;
    platform: string;
    timestamp: number;
  };
  offline_only: boolean;
}

interface Peer {
  node_id: string;
  display_name: string;
  platform: string;
  ip_address: string;
  port: number;
  last_seen: number;
  capabilities: string[];
  trusted: boolean;
  offline_only: boolean;
}

export default function DaemonSyncPanel() {
  const [status, setStatus] = useState<SyncStatus | null>(null);
  const [peers, setPeers] = useState<Peer[]>([]);
  const [peerId, setPeerId] = useState("");
  const [peerName, setPeerName] = useState("");
  const [peerIp, setPeerIp] = useState("");
  const [peerPort, setPeerPort] = useState("8000");
  const [peerCaps, setPeerCaps] = useState("");
  const [stateData, setStateData] = useState('{"key": "value"}');
  const [lastEvent, setLastEvent] = useState<string>("");

  const refresh = async () => {
    try {
      const r = await fetch("/api/daemon/sync/status", { cache: "no-store" });
      setStatus(await r.json());
    } catch { /* offline */ }
  };

  const loadPeers = async () => {
    try {
      const r = await fetch("/api/daemon/sync/peers", { cache: "no-store" });
      const data = await r.json();
      setPeers(data.peers || []);
    } catch { /* offline */ }
  };

  const registerPeer = async () => {
    try {
      const r = await fetch("/api/daemon/sync/peers/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          peer_id: peerId,
          display_name: peerName,
          ip_address: peerIp,
          port: Number(peerPort) || 8000,
          capabilities: peerCaps.split(",").map((c) => c.trim()).filter(Boolean),
        }),
      });
      if (r.ok) {
        setPeerId("");
        setPeerName("");
        setPeerIp("");
        setPeerPort("8000");
        setPeerCaps("");
        loadPeers();
      }
    } catch { /* offline */ }
  };

  const doSync = async () => {
    try {
      const r = await fetch("/api/daemon/sync/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ peer_id: peerId, state_data: JSON.parse(stateData || "{}") }),
      });
      const data = await r.json();
      setLastEvent(JSON.stringify(data, null, 2));
    } catch { /* offline */ }
  };

  const daemonStart = async () => {
    await fetch("/api/daemon/sync/daemon/start", { method: "POST" });
    refresh();
  };
  const daemonStop = async () => {
    await fetch("/api/daemon/sync/daemon/stop", { method: "POST" });
    refresh();
  };
  const daemonRestart = async () => {
    await fetch("/api/daemon/sync/daemon/restart", { method: "POST" });
    refresh();
  };

  useEffect(() => {
    refresh();
    loadPeers();
    const ws = new WebSocket(
      (location.protocol === "https:" ? "wss" : "ws") + "://" + location.host + "/api/daemon/sync/ws"
    );
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.event === "heartbeat") {
          setStatus(msg.status);
          loadPeers();
        }
      } catch { /* ignore */ }
    };
    const id = setInterval(refresh, 5000);
    return () => { clearInterval(id); ws.close(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <section aria-label="Daemon sync" data-offline-only="true">
      <h2>Cross-Device Sync &amp; Daemon Orchestration</h2>
      <p className="offline-badge">{status?.offline_only ? "offline-only" : "online"}</p>

      <div className="daemon-health">
        <span className={status?.daemon?.running ? "ok" : "stopped"}>Daemon running: {status?.daemon?.running ? "yes" : "no"}</span>
        <span>Uptime: {status?.daemon?.uptime_seconds ?? 0}s</span>
        <span>Restarts: {status?.daemon?.restart_count ?? 0}</span>
        <span>Health: {status?.health?.healthy ? "OK" : "DEGRADED"}</span>
        <span>Mem: {status?.health?.memory_mb ?? 0}MB</span>
        <span>CPU: {status?.health?.cpu_percent ?? 0}%</span>
      </div>

      <div className="daemon-controls">
        <button onClick={daemonStart}>Start</button>
        <button onClick={daemonStop}>Stop</button>
        <button onClick={daemonRestart}>Restart</button>
      </div>

      <div className="peer-register">
        <h3>Register Peer</h3>
        <input value={peerId} onChange={(e) => setPeerId(e.target.value)} placeholder="peer_id" />
        <input value={peerName} onChange={(e) => setPeerName(e.target.value)} placeholder="display name" />
        <input value={peerIp} onChange={(e) => setPeerIp(e.target.value)} placeholder="ip_address" />
        <input value={peerPort} onChange={(e) => setPeerPort(e.target.value)} placeholder="port" />
        <input value={peerCaps} onChange={(e) => setPeerCaps(e.target.value)} placeholder="capabilities (comma-sep)" />
        <button onClick={registerPeer}>Register</button>
      </div>

      <div className="peer-list">
        <h3>Peers ({peers.length})</h3>
        <table>
          <thead>
            <tr><th>ID</th><th>Name</th><th>Platform</th><th>IP</th><th>Port</th><th>Trusted</th></tr>
          </thead>
          <tbody>
            {peers.map((p) => (
              <tr key={p.node_id}>
                <td>{p.node_id}</td>
                <td>{p.display_name}</td>
                <td>{p.platform}</td>
                <td>{p.ip_address}</td>
                <td>{p.port}</td>
                <td>{p.trusted ? "yes" : "no"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="sync-action">
        <h3>Sync State</h3>
        <input value={peerId} onChange={(e) => setPeerId(e.target.value)} placeholder="peer_id" />
        <textarea value={stateData} onChange={(e) => setStateData(e.target.value)} placeholder='{"key":"value"}' />
        <button onClick={doSync}>Sync</button>
        {lastEvent && <pre>{lastEvent}</pre>}
      </div>
    </section>
  );
}