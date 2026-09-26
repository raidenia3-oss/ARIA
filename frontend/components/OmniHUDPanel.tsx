"use client";
// BLOQUE 97 - Omni-Interaction HUD panel (100% local/offline).
import { useEffect, useState } from "react";

interface Status {
  offline_only: boolean;
  hud: {
    mode: string;
    position: string;
    opacity: number;
    visible: boolean;
    cognitive_state: string;
    quick_actions_count: number;
    subscribers: number;
    alerts: Array<{ title: string; severity: string }>;
  };
  synthesizer: { buffered_inputs: number; buffered_commands: number };
  ws_connections: number;
}

export default function OmniHUDPanel() {
  const [status, setStatus] = useState<Status | null>(null);
  const [channel, setChannel] = useState("text");
  const [text, setText] = useState("");
  const [wsMsg, setWsMsg] = useState("");
  const [log, setLog] = useState<string[]>([]);

  const base = "";

  const refresh = async () => {
    try {
      const r = await fetch(`${base}/api/hud/omni/status`);
      setStatus(await r.json());
    } catch { /* ignore */ }
  };

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 4000);
    return () => clearInterval(id);
  }, []);

  const ingest = async () => {
    if (!text.trim()) return;
    const r = await fetch(`${base}/api/hud/omni/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ channel, text, confidence: 0.9 }),
    });
    const d = await r.json();
    setLog((l) => [...l, `ingest -> ${JSON.stringify(d)}`].slice(-20));
    setText("");
    refresh();
  };

  const hudAction = async (action: string, params: any = {}) => {
    const r = await fetch(`${base}/api/hud/omni/hud/action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, params }),
    });
    const d = await r.json();
    setLog((l) => [...l, `hud_action -> ${JSON.stringify(d)}`].slice(-20));
    refresh();
  };

  return (
    <div className="p-4 rounded-lg bg-black/40 border border-white/10 space-y-3 max-w-md">
      <h3 className="text-sm font-semibold text-white">Omni HUD</h3>
      {status && (
        <div className="text-xs text-white/70 space-y-1">
          <div>mode: {status.hud.mode}</div>
          <div>position: {status.hud.position}</div>
          <div>opacity: {status.hud.opacity}</div>
          <div>cognitive: {status.hud.cognitive_state}</div>
          <div>ws: {status.ws_connections}</div>
          <div>alerts: {status.hud.alerts.length}</div>
        </div>
      )}
      <div className="flex gap-2">
        <select value={channel} onChange={(e) => setChannel(e.target.value)}
          className="bg-white/10 text-white text-xs rounded px-2 py-1">
          <option value="text">text</option>
          <option value="voice">voice</option>
          <option value="gesture">gesture</option>
          <option value="hotkey">hotkey</option>
          <option value="screen_context">screen_context</option>
        </select>
        <input value={text} onChange={(e) => setText(e.target.value)}
          placeholder="input..."
          className="flex-1 bg-white/10 text-white text-xs rounded px-2 py-1"
          onKeyDown={(e) => e.key === "Enter" && ingest()} />
      </div>
      <div className="flex flex-wrap gap-2">
        <button onClick={ingest}
          className="text-xs bg-blue-600 hover:bg-blue-500 text-white px-2 py-1 rounded">Send</button>
        <button onClick={() => hudAction("toggle")}
          className="text-xs bg-white/10 hover:bg-white/20 text-white px-2 py-1 rounded">Toggle</button>
        <button onClick={() => hudAction("mode", { mode: "minimal" })}
          className="text-xs bg-white/10 hover:bg-white/20 text-white px-2 py-1 rounded">Minimal</button>
        <button onClick={() => hudAction("opacity", { opacity: 0.5 })}
          className="text-xs bg-white/10 hover:bg-white/20 text-white px-2 py-1 rounded">50%</button>
      </div>
      <div className="text-[10px] text-white/40 max-h-24 overflow-auto">
        {log.map((l, i) => <div key={i}>{l}</div>)}
      </div>
    </div>
  );
}